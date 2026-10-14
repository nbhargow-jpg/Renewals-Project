import React, { useState, useEffect, useMemo } from 'react'
import { useDropzone } from 'react-dropzone'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Upload as UploadIcon,
  FileSpreadsheet,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Clock,
  ArrowRight,
  Database,
  Layers,
  Sparkles,
  Info,
  Calendar,
  ShieldCheck,
  RefreshCw,
  FileCheck2,
  AlertCircle,
  Trash2,
  Check,
  Eye,
  Lock,
  ArrowUpDown,
  Filter,
  CheckSquare,
  Square,
  Repeat,
} from 'lucide-react'
import {
  validateUpload,
  commitUpload,
  getUploadHistory,
  getSnapshotChecks,
  deleteSnapshot,
  setActiveSnapshot,
  getSnapshot,
  getHealth,
} from '@/api/client'
import { formatCurrency, formatNumber, formatDate } from '@/utils/format'
import { showToast } from '@/components/ui/Toast'
import { useAppStore } from '@/store/appStore'

export type FileSlot = 'comparison_tool' | 'renewals_summary' | string

interface UploadSlotState {
  file: File | null
  name: string
  size: number
}

function formatLocalDate(d: Date): string {
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${mm}-${dd}`
}

function getAutoYesterdayDate(asOfStr: string): string {
  if (!asOfStr) return ''
  const d = new Date(asOfStr + 'T00:00:00')
  const day = d.getDay() // 0 = Sun, 1 = Mon, ..., 6 = Sat
  let daysBack = 1
  if (day === 1) {
    daysBack = 3 // Monday -> Friday
  } else if (day === 0) {
    daysBack = 2 // Sunday -> Friday
  } else if (day === 6) {
    daysBack = 1 // Saturday -> Friday
  }
  const y = new Date(d)
  y.setDate(d.getDate() - daysBack)
  return formatLocalDate(y)
}

function detectSlotForFile(filename: string): string {
  const fn = filename.toLowerCase()
  if (fn.includes('comparison')) return 'comparison_tool'
  return 'renewals_summary'
}

export default function DataUploads() {
  const qc = useQueryClient()
  const { isAdmin } = useAppStore()

  // ── Date Configuration ───────────────────────────────────────────────────────
  const [dataAsOf, setDataAsOf] = useState(formatLocalDate(new Date()))
  const [yesterdayDate, setYesterdayDate] = useState(getAutoYesterdayDate(formatLocalDate(new Date())))
  const [manualYesterdayEdited, setManualYesterdayEdited] = useState(false)

  // ── Files / Slots ───────────────────────────────────────────────────────────
  // Primary comparison tool file + optional summary files list
  const [comparisonFile, setComparisonFile] = useState<UploadSlotState>({ file: null, name: '', size: 0 })
  const [summaryFiles, setSummaryFiles] = useState<UploadSlotState[]>([])

  // ── Validation & Commit State ───────────────────────────────────────────────
  const [isValidating, setIsValidating] = useState(false)
  const [previewData, setPreviewData] = useState<any>(null)
  const [isCommitting, setIsCommitting] = useState(false)
  const [makeActiveChecked, setMakeActiveChecked] = useState(true)
  const [userConfirmReplace, setUserConfirmReplace] = useState(false)

  // ── History Query & Filtering / Sorting ─────────────────────────────────────
  const { data: uploadHistory = [], refetch: refetchHistory, isLoading: loadingHistory } = useQuery({
    queryKey: ['uploadHistory'],
    queryFn: getUploadHistory,
  })

  const { data: healthData } = useQuery({
    queryKey: ['appHealth'],
    queryFn: getHealth,
    staleTime: 30000,
  })

  const [dateFilter, setDateFilter] = useState('')
  const [sortDirection, setSortDirection] = useState<'desc' | 'asc'>('desc')

  // ── Modals / Dialogs ────────────────────────────────────────────────────────
  // Source checks inspection modal
  const [selectedHistoryCheckSnap, setSelectedHistoryCheckSnap] = useState<any | null>(null)
  const [checksModalData, setChecksModalData] = useState<any[] | null>(null)
  const [loadingChecks, setLoadingChecks] = useState(false)

  // Snapshot details modal (read-only for everyone)
  const [detailSnapshot, setDetailSnapshot] = useState<any | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

  // Snapshot delete confirmation modal (admin only)
  const [snapshotToDelete, setSnapshotToDelete] = useState<any | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)

  // Setting active state
  const [settingActiveId, setSettingActiveId] = useState<string | null>(null)

  // ── Expandable table toggle in Preview ──────────────────────────────────────
  const [previewChecksExpanded, setPreviewChecksExpanded] = useState(true)

  // Auto-fill yesterday date when dataAsOf changes
  useEffect(() => {
    if (!manualYesterdayEdited) {
      setYesterdayDate(getAutoYesterdayDate(dataAsOf))
    }
  }, [dataAsOf, manualYesterdayEdited])

  const asOfDateObj = useMemo(() => new Date(dataAsOf + 'T00:00:00'), [dataAsOf])
  const weekdayName = useMemo(() => {
    return asOfDateObj.toLocaleDateString('en-US', { weekday: 'long' })
  }, [asOfDateObj])
  const isWeekend = asOfDateObj.getDay() === 0 || asOfDateObj.getDay() === 6
  const isMonday = asOfDateObj.getDay() === 1

  // Detect whether dataAsOf is older than the newest date in history (out-of-order backfill)
  const isBackfillDate = useMemo(() => {
    if (!uploadHistory || uploadHistory.length === 0) return false
    const latestHistoryDate = uploadHistory[0]?.snapshot_date
    if (!latestHistoryDate) return false
    return dataAsOf < latestHistoryDate
  }, [dataAsOf, uploadHistory])

  useEffect(() => {
    setMakeActiveChecked(!isBackfillDate)
  }, [isBackfillDate])

  // Multi-drop batch handler
  const assignUploadedFiles = (files: File[]) => {
    let comp: File | null = null
    const summaries: File[] = []

    files.forEach((f) => {
      const slot = detectSlotForFile(f.name)
      if (slot === 'comparison_tool') {
        comp = f
      } else {
        summaries.push(f)
      }
    })

    if (comp !== null) {
      const compFile: File = comp
      setComparisonFile({ file: compFile, name: compFile.name, size: compFile.size })
    }
    if (summaries.length > 0) {
      setSummaryFiles((prev) => {
        // avoid exact duplicates by name
        const existingNames = new Set(prev.map((p) => p.name))
        const added = summaries
          .filter((s) => !existingNames.has(s.name))
          .map((s) => ({ file: s, name: s.name, size: s.size }))
        return [...prev, ...added]
      })
    }
    setPreviewData(null)
    setUserConfirmReplace(false)
  }

  const { getRootProps: getBatchRootProps, getInputProps: getBatchInputProps, isDragActive: isBatchDragActive } =
    useDropzone({
      accept: { 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'] },
      disabled: !isAdmin,
      onDrop: (acceptedFiles) => assignUploadedFiles(acceptedFiles),
    })

  // Handle single slot drops
  const handleComparisonDrop = (f: File) => {
    setComparisonFile({ file: f, name: f.name, size: f.size })
    setPreviewData(null)
    setUserConfirmReplace(false)
  }

  const handleAddSummaryFiles = (files: File[]) => {
    setSummaryFiles((prev) => {
      const existingNames = new Set(prev.map((p) => p.name))
      const added = files
        .filter((s) => !existingNames.has(s.name))
        .map((s) => ({ file: s, name: s.name, size: s.size }))
      return [...prev, ...added]
    })
    setPreviewData(null)
    setUserConfirmReplace(false)
  }

  const handleRemoveSummaryFile = (index: number) => {
    setSummaryFiles((prev) => prev.filter((_, i) => i !== index))
    setPreviewData(null)
    setUserConfirmReplace(false)
  }

  // ── Validation Call ─────────────────────────────────────────────────────────
  const handleValidate = async () => {
    if (!comparisonFile.file) {
      showToast.error('Validation error', 'Renewal Comparison Tool is required.')
      return
    }

    setIsValidating(true)
    setPreviewData(null)
    setUserConfirmReplace(false)

    try {
      const formData = new FormData()
      formData.append('data_as_of_date', dataAsOf)
      formData.append('yesterday_date', yesterdayDate)
      formData.append('comparison_tool', comparisonFile.file)

      summaryFiles.forEach((sf, idx) => {
        if (sf.file) {
          formData.append(`summary_file_${idx}`, sf.file)
        }
      })

      const res = await validateUpload(formData)
      setPreviewData(res)

      if (res.can_commit) {
        showToast.success('Validation complete', 'Files parsed cleanly. Review the preview below.')
      } else {
        showToast.error('Validation failed', 'One or more blocking errors were found.')
      }
    } catch (err: any) {
      showToast.error('Validation error', err?.response?.data?.detail || err.message)
    } finally {
      setIsValidating(false)
    }
  }

  // ── Commit Call ─────────────────────────────────────────────────────────────
  const handleCommit = async (replace = false) => {
    if (!previewData?.session_id) return
    setIsCommitting(true)
    try {
      const res = await commitUpload(previewData.session_id, replace, makeActiveChecked)
      showToast.success(
        'Snapshot committed',
        `Saved ${res.row_count} total (${res.active_row_count} active) opportunities. Active today: ${
          res.is_active_today ? 'Yes' : 'No'
        }.`
      )
      setPreviewData(null)
      setUserConfirmReplace(false)
      setComparisonFile({ file: null, name: '', size: 0 })
      setSummaryFiles([])
      qc.invalidateQueries()
      refetchHistory()
    } catch (err: any) {
      showToast.error('Commit failed', err?.response?.data?.detail || err.message)
    } finally {
      setIsCommitting(false)
    }
  }

  // ── Set Active Snapshot Call ────────────────────────────────────────────────
  const handleSetActive = async (snapshotId: string) => {
    setSettingActiveId(snapshotId)
    try {
      await setActiveSnapshot(snapshotId)
      showToast.success('Active snapshot updated', 'Selected snapshot is now active across all dashboards.')
      qc.invalidateQueries()
      refetchHistory()
    } catch (err: any) {
      showToast.error('Action failed', err?.response?.data?.detail || err.message)
    } finally {
      setSettingActiveId(null)
    }
  }

  // ── Replace Action from History Row ─────────────────────────────────────────
  const handleInitiateReplace = (snap: any) => {
    setDataAsOf(snap.snapshot_date)
    if (snap.yesterday_date) {
      setYesterdayDate(snap.yesterday_date)
      setManualYesterdayEdited(true)
    }
    // Scroll smoothly to upload panel
    window.scrollTo({ top: 0, behavior: 'smooth' })
    showToast.info('Snapshot target selected', `Upload date set to ${snap.snapshot_date}. Select replacement files to validate.`)
  }

  // ── Delete Snapshot Call ────────────────────────────────────────────────────
  const handleConfirmDelete = async () => {
    if (!snapshotToDelete) return
    setIsDeleting(true)
    try {
      await deleteSnapshot(snapshotToDelete.id)
      showToast.success('Snapshot removed', `Deleted snapshot for ${snapshotToDelete.snapshot_date}.`)
      setSnapshotToDelete(null)
      qc.invalidateQueries()
      refetchHistory()
    } catch (err: any) {
      showToast.error('Delete failed', err?.response?.data?.detail || err.message)
    } finally {
      setIsDeleting(false)
    }
  }

  // ── Open Snapshot Detail Modal ──────────────────────────────────────────────
  const handleOpenDetail = async (snapshotId: string) => {
    setLoadingDetail(true)
    try {
      const snap = await getSnapshot(snapshotId)
      setDetailSnapshot(snap)
    } catch (err: any) {
      showToast.error('Failed to load snapshot details', err?.message)
    } finally {
      setLoadingDetail(false)
    }
  }

  // ── Filtered & Sorted History List ──────────────────────────────────────────
  const sortedAndFilteredHistory = useMemo(() => {
    let list = [...uploadHistory]
    if (dateFilter) {
      list = list.filter((h) => h.snapshot_date?.includes(dateFilter))
    }
    list.sort((a, b) => {
      const dateA = a.snapshot_date || ''
      const dateB = b.snapshot_date || ''
      return sortDirection === 'desc' ? dateB.localeCompare(dateA) : dateA.localeCompare(dateB)
    })
    return list
  }, [uploadHistory, dateFilter, sortDirection])

  // ── Working Day Calendar & Coverage Strip Calculation ──────────────────────
  const coverageData = useMemo(() => {
    if (!uploadHistory || uploadHistory.length === 0) return null

    // Extract sorted list of unique snapshot dates
    const snapDates = uploadHistory.map((h: any) => h.snapshot_date).filter(Boolean)
    const snapDateSet = new Set(snapDates)

    // Compute min and max dates
    const sortedDates = [...snapDates].sort()
    const minDateStr = sortedDates[0]
    const maxDateStr = sortedDates[sortedDates.length - 1]

    const startDate = new Date(minDateStr + 'T00:00:00')
    const endDate = new Date(maxDateStr + 'T00:00:00')

    const workingDaysInRange: string[] = []
    const cur = new Date(startDate)
    while (cur <= endDate) {
      const day = cur.getDay()
      if (day !== 0 && day !== 6) {
        workingDaysInRange.push(formatLocalDate(cur))
      }
      cur.setDate(cur.getDate() + 1)
    }

    const missingDays = workingDaysInRange.filter((d) => !snapDateSet.has(d))

    // Build map of each snapshot's resolved baselines
    const baselineMap: Record<string, { yesterday: string | null; lastWeek: string | null; isPartial: boolean; isActive: boolean }> = {}
    uploadHistory.forEach((h: any) => {
      baselineMap[h.snapshot_date] = {
        yesterday: h.yesterday_date || null,
        lastWeek: h.last_week_source === 'real_snapshot' ? 'Stored (-7d)' : 'File Bootstrap (Partial)',
        isPartial: !!h.last_week_is_partial,
        isActive: !!h.is_active_today,
      }
    })

    return {
      workingDaysInRange,
      missingDays,
      baselineMap,
      totalWorkingDays: workingDaysInRange.length,
      presentWorkingDays: workingDaysInRange.filter((d) => snapDateSet.has(d)).length,
    }
  }, [uploadHistory])

  const suggestedDateMismatch =
    previewData?.suggested_date && previewData.suggested_date !== dataAsOf

  return (
    <div className="space-y-6 w-full pb-12">
      {/* ── Page Header ──────────────────────────────────────────────────────── */}
      <motion.div initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-[var(--border)]">
          <div className="flex items-center gap-3.5">
            <div className="p-2.5 rounded-sm bg-[var(--bg-secondary)] border border-[var(--border)] text-[#00A3AD]">
              <UploadIcon className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-3xl font-black text-[var(--text-primary)] tracking-tight">
                Data Uploads
              </h1>
              <p className="text-xs text-[var(--text-muted)] mt-1 font-medium">
                Ingest daily workbook sets, verify control balances, and audit historical snapshot states.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            {isAdmin ? (
              <span className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-sm text-xs font-bold bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border border-emerald-500/30 shadow-sm">
                <ShieldCheck className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                Administrator Mode Active
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-sm text-xs font-semibold bg-amber-500/10 text-amber-700 dark:text-amber-300 border border-amber-500/25 shadow-sm">
                <Lock className="w-3.5 h-3.5 text-amber-500" />
                Read-Only Viewer
              </span>
            )}
          </div>
        </div>
      </motion.div>

      {/* ─────────────────────────────────────────────────────────────────────────
          SECTION 1: ADMIN UPLOAD PANEL
          Visible and usable ONLY when signed in as admin; for everyone else show read-only note
      ───────────────────────────────────────────────────────────────────────── */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-black uppercase tracking-wider text-[var(--text-muted)] flex items-center gap-2">
            <Layers className="w-4 h-4 text-teal-500" />
            1. Ingestion &amp; File Upload Panel
          </h2>
        </div>

        {!isAdmin ? (
          <div className="card p-6 border-l-4 border-l-amber-500 bg-[var(--bg-card)] rounded-md flex items-center gap-4.5">
            <div className="p-3.5 rounded-md bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30 flex-shrink-0">
              <Lock className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-amber-900 dark:text-amber-200">
                Uploads are restricted to the administrator
              </h3>
              <p className="text-xs text-[var(--text-muted)] mt-1">
                Viewing historical records and reconciliation sheets is open to all members. To ingest new data or replace existing snapshots, please authenticate as an administrator via the top navigation bar.
              </p>
            </div>
          </div>
        ) : (
          <div className="card p-6 bg-[var(--bg-card)] border border-[var(--border)] rounded-md shadow-sm space-y-6">
            {/* Date Configuration Strip */}
            <div className="space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] flex items-center gap-2">
                <Calendar className="w-4 h-4 text-teal-500" />
                Snapshot Date &amp; Resolution Parameters
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 items-end">
                <div>
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-[var(--text-secondary)]">Data as of Date</label>
                    <span className="text-[11px] font-bold text-teal-600 dark:text-teal-400">
                      {weekdayName}
                    </span>
                  </div>
                  <input
                    type="date"
                    value={dataAsOf}
                    onChange={(e) => {
                      setDataAsOf(e.target.value)
                      setManualYesterdayEdited(false)
                      setPreviewData(null)
                    }}
                    className="mt-1.5 w-full px-3 py-2 rounded-sm text-sm border outline-none bg-[var(--bg-secondary)] border-[var(--border)] text-[var(--text-primary)] focus:ring-2 focus:ring-teal-500"
                    id="upload-data-as-of"
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-[var(--text-secondary)]">
                      Yesterday Date (Prev Working Day)
                    </label>
                    {manualYesterdayEdited && (
                      <button
                        type="button"
                        onClick={() => {
                          setManualYesterdayEdited(false)
                          setYesterdayDate(getAutoYesterdayDate(dataAsOf))
                          setPreviewData(null)
                        }}
                        className="text-[10px] text-teal-600 dark:text-teal-400 hover:underline"
                      >
                        Reset Auto
                      </button>
                    )}
                  </div>
                  <input
                    type="date"
                    value={yesterdayDate}
                    onChange={(e) => {
                      setYesterdayDate(e.target.value)
                      setManualYesterdayEdited(true)
                      setPreviewData(null)
                    }}
                    className="mt-1.5 w-full px-3 py-2 rounded-sm text-sm border outline-none bg-[var(--bg-secondary)] border-[var(--border)] text-[var(--text-primary)] focus:ring-2 focus:ring-teal-500"
                    id="upload-yesterday-date"
                  />
                </div>

                <div className="text-xs text-[var(--text-muted)] p-2.5 rounded-sm bg-[var(--bg-secondary)] border border-[var(--border-subtle)]">
                  {isMonday && (
                    <span className="font-semibold text-teal-600 dark:text-teal-400 block mb-0.5">
                      ⚡ Monday rule: auto-set to Friday 3 days earlier
                    </span>
                  )}
                  {isWeekend && (
                    <span className="font-semibold text-amber-500 block mb-0.5 flex items-center gap-1">
                      <AlertTriangle className="w-3.5 h-3.5" /> Weekend date selected (warning will be flagged)
                    </span>
                  )}
                  {!isMonday && !isWeekend && (
                    <span>Previous calendar business day auto-computed. Editable for public holidays.</span>
                  )}
                </div>
              </div>

              {/* Date Mismatch Suggestion Banner */}
              {suggestedDateMismatch && (
                <div className="p-3.5 rounded-sm bg-amber-500/10 border border-amber-500/30 flex items-center justify-between text-xs text-amber-700 dark:text-amber-400">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                    <span>
                      Detected snapshot date from file content is{' '}
                      <strong className="underline">{previewData.suggested_date}</strong>, but entered date is{' '}
                      <strong>{dataAsOf}</strong>.
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setDataAsOf(previewData.suggested_date)
                      setYesterdayDate(getAutoYesterdayDate(previewData.suggested_date))
                      setPreviewData(null)
                    }}
                    className="px-3 py-1 rounded-lg bg-amber-600 hover:bg-amber-700 text-white font-bold text-[11px] transition-all"
                  >
                    Use Detected Date ({previewData.suggested_date})
                  </button>
                </div>
              )}
            </div>

            {/* Drag & Drop Area */}
            <div
              {...getBatchRootProps()}
              className={`border-2 border-dashed rounded-md p-6 text-center cursor-pointer transition-all ${
                isBatchDragActive
                  ? 'border-teal-500 bg-teal-500/5 scale-[1.01]'
                  : 'border-[var(--border)] bg-[var(--bg-secondary)]/50 hover:border-teal-400 hover:bg-[var(--bg-secondary)]'
              }`}
            >
              <input {...getBatchInputProps()} id="upload-batch-input" />
              <div className="flex flex-col items-center justify-center gap-2">
                <div className="w-12 h-12 rounded-md bg-teal-500/10 flex items-center justify-center text-teal-600 dark:text-teal-400">
                  <UploadIcon className="w-6 h-6" />
                </div>
                <p className="font-bold text-sm text-[var(--text-primary)]">
                  Drag &amp; drop your Excel workbooks here
                </p>
                <p className="text-xs text-[var(--text-muted)] max-w-lg">
                  Content-based signature detection automatically inspects every workbook to resolve its period coverage and slot assignment dynamically.
                </p>
              </div>
            </div>

            {/* Selected Files Staging List */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Mandatory Comparison Tool Box */}
              <div className="p-4 rounded-sm border border-[var(--border)] bg-[var(--bg-secondary)] space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded text-[10px] font-extrabold uppercase tracking-wider bg-teal-500/10 text-teal-700 dark:text-teal-400">
                      Mandatory
                    </span>
                    <h4 className="font-bold text-xs text-[var(--text-primary)]">Renewal Comparison Tool</h4>
                  </div>
                  {comparisonFile.file && (
                    <span className="text-emerald-500 text-xs flex items-center gap-1 font-bold">
                      <CheckCircle2 className="w-3.5 h-3.5" /> Staged
                    </span>
                  )}
                </div>

                {comparisonFile.file ? (
                  <div className="p-2.5 rounded-lg bg-[var(--bg-card)] border border-[var(--border)] flex items-center justify-between">
                    <div className="truncate pr-2">
                      <p className="text-xs font-semibold text-[var(--text-primary)] truncate">{comparisonFile.name}</p>
                      <p className="text-[10px] text-[var(--text-muted)]">{(comparisonFile.size / (1024 * 1024)).toFixed(2)} MB</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setComparisonFile({ file: null, name: '', size: 0 })
                        setPreviewData(null)
                      }}
                      className="p-1 rounded hover:bg-[var(--bg-secondary)] text-[var(--text-muted)] hover:text-rose-500"
                    >
                      <XCircle className="w-4 h-4" />
                    </button>
                  </div>
                ) : (
                  <label className="block p-3 border border-dashed rounded-sm border-[var(--border)] text-center cursor-pointer hover:border-teal-400 bg-[var(--bg-card)]">
                    <input
                      type="file"
                      accept=".xlsx"
                      className="hidden"
                      onChange={(e) => {
                        const f = e.target.files?.[0]
                        if (f) handleComparisonDrop(f)
                      }}
                    />
                    <FileSpreadsheet className="w-5 h-5 mx-auto text-[var(--text-muted)] mb-1 opacity-70" />
                    <span className="text-[11px] font-semibold text-teal-600 dark:text-teal-400">Select Comparison Tool Excel</span>
                  </label>
                )}
              </div>

              {/* Renewals Summary Files Box */}
              <div className="p-4 rounded-sm border border-[var(--border)] bg-[var(--bg-secondary)] space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded text-[10px] font-extrabold uppercase tracking-wider bg-slate-500/10 text-slate-700 dark:text-slate-400">
                      Optional Summaries
                    </span>
                    <h4 className="font-bold text-xs text-[var(--text-primary)]">Renewals Summary Files ({summaryFiles.length})</h4>
                  </div>
                  <label className="text-teal-600 dark:text-teal-400 text-xs font-bold cursor-pointer hover:underline">
                    + Add Files
                    <input
                      type="file"
                      multiple
                      accept=".xlsx"
                      className="hidden"
                      onChange={(e) => {
                        if (e.target.files) handleAddSummaryFiles(Array.from(e.target.files))
                      }}
                    />
                  </label>
                </div>

                {summaryFiles.length === 0 ? (
                  <p className="text-xs text-[var(--text-muted)] italic py-3 text-center">
                    No optional Renewals Summary files staged.
                  </p>
                ) : (
                  <div className="space-y-1.5 max-h-36 overflow-y-auto pr-1">
                    {summaryFiles.map((sf, idx) => (
                      <div
                        key={idx}
                        className="p-2 rounded-lg bg-[var(--bg-card)] border border-[var(--border)] flex items-center justify-between text-xs"
                      >
                        <div className="truncate pr-2">
                          <span className="font-semibold text-[var(--text-primary)] truncate block">{sf.name}</span>
                          <span className="text-[10px] text-[var(--text-muted)]">{(sf.size / (1024 * 1024)).toFixed(2)} MB</span>
                        </div>
                        <button
                          type="button"
                          onClick={() => handleRemoveSummaryFile(idx)}
                          className="p-1 rounded hover:bg-[var(--bg-secondary)] text-[var(--text-muted)] hover:text-rose-500"
                        >
                          <XCircle className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Validate Button Row */}
            <div className="flex items-center justify-between pt-2 border-t border-[var(--border)]">
              <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
                <Info className="w-4 h-4 text-teal-500 flex-shrink-0" />
                <span>Validation parses sheets, verifies signatures, and runs control balances without modifying the database.</span>
              </div>
              <button
                type="button"
                onClick={handleValidate}
                disabled={!comparisonFile.file || isValidating || isCommitting}
                className="px-5 py-2.5 rounded-sm font-bold text-xs text-white shadow-md disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 flex-shrink-0 transition-all"
                id="validate-preview-btn"
              >
                {isValidating ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    Validating Files...
                  </>
                ) : (
                  <>
                    <ShieldCheck className="w-4 h-4" />
                    Validate &amp; Preview
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </section>

      {/* ─────────────────────────────────────────────────────────────────────────
          SECTION 2: PREVIEW / CONFIRM AREA
          Shows Source check badge, expandable table, schema-drift warnings, and commit options
      ───────────────────────────────────────────────────────────────────────── */}
      <AnimatePresence>
        {previewData && (
          <motion.section
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="space-y-4"
            id="upload-preview-container"
          >
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-black uppercase tracking-wider text-[var(--text-muted)] flex items-center gap-2">
                <FileCheck2 className="w-4 h-4 text-teal-500" />
                2. Validation Preview &amp; Control Balance Reconciliation
              </h2>
            </div>

            <div className="card p-6 border-2 border-teal-500/30 bg-[var(--bg-card)] shadow-lg space-y-6">
              {/* Preview Header & Date / Quarter Summary */}
              <div className="flex flex-col md:flex-row items-start md:items-center justify-between pb-4 border-b border-[var(--border)] gap-4">
                <div>
                  <h3 className="text-lg font-black text-[var(--text-primary)]">
                    Pre-Commit Validation Summary
                  </h3>
                  <div className="flex flex-wrap items-center gap-2 mt-1 text-xs text-[var(--text-secondary)]">
                    <span className="font-bold text-[var(--text-primary)]">
                      As-of: {previewData.data_as_of_date} ({previewData.weekday})
                    </span>
                    <span>·</span>
                    <span className="px-2 py-0.5 rounded bg-teal-500/10 text-teal-600 dark:text-teal-400 font-bold">
                      Quarter: {previewData.quarter_label}
                    </span>
                  </div>
                </div>

                {/* Commit Button */}
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={() => handleCommit(previewData.snapshot_exists)}
                    disabled={
                      isCommitting ||
                      !previewData.can_commit ||
                      (previewData.errors && previewData.errors.length > 0) ||
                      (previewData.snapshot_exists && !userConfirmReplace)
                    }
                    className={`px-6 py-2.5 rounded-sm font-black text-xs shadow-md flex items-center gap-2 transition-all text-white ${
                      previewData.snapshot_exists
                        ? 'bg-amber-600 hover:bg-amber-700 disabled:bg-slate-500'
                        : 'bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-500'
                    } disabled:opacity-40 disabled:cursor-not-allowed`}
                    id="confirm-commit-btn"
                  >
                    {isCommitting ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        Committing Transaction...
                      </>
                    ) : !previewData.can_commit ? (
                      <>
                        <XCircle className="w-4 h-4" />
                        Blocked — Fix Errors First
                      </>
                    ) : previewData.snapshot_exists ? (
                      <>
                        <Database className="w-4 h-4" />
                        Replace Existing Snapshot &amp; Commit
                      </>
                    ) : (
                      <>
                        <Database className="w-4 h-4" />
                        Confirm &amp; Commit to Database
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Active Toggle & Baseline Resolution Notes */}
              <div className="p-4 rounded-sm bg-[var(--bg-secondary)] border border-[var(--border)] text-xs space-y-3">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <label className="flex items-center gap-2 cursor-pointer font-bold text-[var(--text-primary)]">
                      <input
                        type="checkbox"
                        checked={makeActiveChecked}
                        onChange={(e) => setMakeActiveChecked(e.target.checked)}
                        className="rounded border-[var(--border)] text-teal-600 focus:ring-teal-500"
                        id="upload-make-active-checkbox"
                      />
                      <span>Set as Active Today's Snapshot</span>
                    </label>
                    {isBackfillDate && (
                      <span className="text-[10px] px-2 py-0.5 rounded bg-blue-500/10 text-blue-600 dark:text-blue-400 font-semibold">
                        Out-of-order backfill (newer date exists in DB)
                      </span>
                    )}
                  </div>

                  <div className="text-[11px] text-[var(--text-muted)]">
                    {makeActiveChecked
                      ? 'This snapshot will be displayed as the default view across all dashboards.'
                      : 'This snapshot will be saved to history without altering the currently active dashboard date.'}
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2 border-t border-[var(--border-subtle)] text-[11px]">
                  <div className="p-2.5 rounded-lg bg-[var(--bg-card)] border border-[var(--border-subtle)]">
                    <span className="font-bold text-[var(--text-primary)] block">
                      Yesterday Baseline ({previewData.yesterday_date}):
                    </span>
                    <span className="text-[var(--text-muted)]">
                      Resolved {previewData.yesterday_source_desc}
                    </span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-[var(--bg-card)] border border-[var(--border-subtle)]">
                    <span className="font-bold text-[var(--text-primary)] block">
                      Last Week Baseline ({previewData.last_week_date}):
                    </span>
                    <span className="text-[var(--text-muted)]">
                      Resolved {previewData.last_week_source_desc}
                    </span>
                  </div>
                </div>
              </div>

              {/* Replace Existing Warning */}
              {previewData.snapshot_exists && (
                <div className="p-4 rounded-sm bg-amber-500/10 border-2 border-amber-500/40 text-amber-800 dark:text-amber-300 space-y-3 text-xs">
                  <div className="flex items-center gap-2 font-bold text-sm">
                    <AlertTriangle className="w-5 h-5 text-amber-600" />
                    Replace Existing Snapshot Warning
                  </div>
                  <p className="leading-relaxed">
                    A snapshot for <strong>{previewData.data_as_of_date}</strong> already exists in the database
                    {previewData.existing_snapshot?.uploaded_at && (
                      <> (uploaded on {new Date(previewData.existing_snapshot.uploaded_at).toLocaleString()}</>
                    )}
                    {previewData.existing_snapshot?.row_count !== undefined && (
                      <>, containing <strong>{formatNumber(previewData.existing_snapshot.row_count)}</strong> deals</>
                    )}
                    ). Overwriting will replace existing opportunities and change logs for this date atomically.
                  </p>

                  <label className="flex items-center gap-2.5 font-bold cursor-pointer pt-1 text-[var(--text-primary)]">
                    <input
                      type="checkbox"
                      checked={userConfirmReplace}
                      onChange={(e) => setUserConfirmReplace(e.target.checked)}
                      className="w-4 h-4 rounded border-[var(--border)] text-amber-600 focus:ring-amber-500"
                      id="upload-confirm-replace-checkbox"
                    />
                    <span>Yes, I confirm replacing the existing snapshot for {previewData.data_as_of_date}</span>
                  </label>
                </div>
              )}

              {/* Schema Drift Warnings */}
              {previewData.schema_drift_warnings && previewData.schema_drift_warnings.length > 0 && (
                <div className="p-4 rounded-sm bg-amber-500/10 border border-amber-500/30 text-amber-700 dark:text-amber-300 space-y-2 text-xs">
                  <div className="font-bold flex items-center gap-1.5 text-sm">
                    <AlertTriangle className="w-4 h-4 text-amber-500" />
                    Schema Drift Detected (Both Ways):
                  </div>
                  <ul className="list-disc list-inside space-y-1 pl-1">
                    {previewData.schema_drift_warnings.map((w: string, idx: number) => (
                      <li key={idx} className="font-mono text-[11px]">{w}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Source Reconciliation Checks with Expandable Table */}
              {previewData.source_checks && (
                <div className="p-4 rounded-sm bg-[var(--bg-secondary)] border border-[var(--border)] space-y-3 text-xs">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span
                        className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-sm text-xs font-bold ${
                          previewData.source_checks.badge === 'green'
                            ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border border-emerald-500/30'
                            : previewData.source_checks.badge === 'red'
                            ? 'bg-rose-500/15 text-rose-700 dark:text-rose-300 border border-rose-500/30'
                            : 'bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-500/30'
                        }`}
                      >
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        Source Check: {previewData.source_checks.badge === 'green' ? 'All Match' : `${previewData.source_checks.failed} Mismatch(es)`} ({previewData.source_checks.passed}/{previewData.source_checks.total})
                      </span>
                      <span className="text-[11px] text-[var(--text-muted)]">
                        Reconciled live against Excel's own control sheets
                      </span>
                    </div>

                    <button
                      type="button"
                      onClick={() => setPreviewChecksExpanded(!previewChecksExpanded)}
                      className="text-xs font-bold text-teal-600 dark:text-teal-400 hover:underline"
                    >
                      {previewChecksExpanded ? 'Collapse Table' : 'Expand Table'}
                    </button>
                  </div>

                  {previewChecksExpanded && previewData.source_checks.items && previewData.source_checks.items.length > 0 && (
                    <div className="overflow-x-auto rounded-lg border border-[var(--border-subtle)] max-h-64 overflow-y-auto">
                      <table className="w-full text-[11px] text-left">
                        <thead className="bg-[var(--bg-card)] text-[var(--text-muted)] font-semibold border-b border-[var(--border-subtle)] sticky top-0">
                          <tr>
                            <th className="py-2 px-2.5">Status</th>
                            <th className="py-2 px-2.5">Sheet</th>
                            <th className="py-2 px-2.5">Metric</th>
                            <th className="py-2 px-2.5 text-right">Excel Value</th>
                            <th className="py-2 px-2.5 text-right">Website Value</th>
                            <th className="py-2 px-2.5 text-right">Difference</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[var(--border-subtle)]">
                          {previewData.source_checks.items.map((chk: any, idx: number) => (
                            <tr
                              key={idx}
                              className={chk.status === 'fail' ? 'bg-rose-500/10 font-bold' : 'hover:bg-[var(--bg-card)]/50'}
                            >
                              <td className="py-1.5 px-2.5">
                                {chk.status === 'pass' ? (
                                  <span className="text-emerald-600 dark:text-emerald-400 font-bold">MATCH</span>
                                ) : (
                                  <span className="text-rose-600 dark:text-rose-400 font-bold">MISMATCH</span>
                                )}
                              </td>
                              <td className="py-1.5 px-2.5 font-medium">{chk.sheet_name}</td>
                              <td className="py-1.5 px-2.5">{chk.metric_name}</td>
                              <td className="py-1.5 px-2.5 text-right font-mono font-semibold">{chk.excel_value}</td>
                              <td className="py-1.5 px-2.5 text-right font-mono font-semibold">{chk.website_value}</td>
                              <td className="py-1.5 px-2.5 text-right font-mono">
                                {chk.diff_value != null ? Number(chk.diff_value).toFixed(2) : '0.00'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              {/* Blocking Errors */}
              {previewData.errors && previewData.errors.length > 0 && (
                <div className="p-4 rounded-sm bg-rose-500/10 border border-rose-500/30 text-rose-600 dark:text-rose-400 space-y-1.5 text-xs">
                  <div className="font-bold flex items-center gap-1.5">
                    <XCircle className="w-4 h-4" /> Blocking Errors:
                  </div>
                  <ul className="list-disc list-inside space-y-1 pl-1">
                    {previewData.errors.map((e: string, idx: number) => (
                      <li key={idx}>{e}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </motion.section>
        )}
      </AnimatePresence>

      {/* ─────────────────────────────────────────────────────────────────────────
          SECTION 3: SNAPSHOT HISTORY TABLE
          Columns: snapshot date, uploaded at, files (names + sha256 prefix), row count,
          Q-slice deals/ACV, Source check badge (clickable detail), partial flag, "active" marker.
          Sort/filter by date.
          Admin-only row actions: set active, replace, delete.
          Everyone can open a snapshot's details.
      ───────────────────────────────────────────────────────────────────────── */}
      <section className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-xs font-black uppercase tracking-wider text-[var(--text-muted)] flex items-center gap-2">
              <Clock className="w-4 h-4 text-teal-500" />
              3. Snapshot History Table
            </h2>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">
              Comprehensive audit log of ingested snapshots, SHA-256 archives, and Q-slice totals.
            </p>
          </div>

          {/* Filter & Sort Controls */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-sm bg-[var(--bg-secondary)] border border-[var(--border)] text-xs">
              <Filter className="w-3.5 h-3.5 text-[var(--text-muted)]" />
              <input
                type="text"
                placeholder="Filter by date..."
                value={dateFilter}
                onChange={(e) => setDateFilter(e.target.value)}
                className="bg-transparent border-none outline-none text-xs w-28 text-[var(--text-primary)] font-medium"
              />
            </div>

            <button
              type="button"
              onClick={() => setSortDirection((d) => (d === 'desc' ? 'asc' : 'desc'))}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-sm bg-[var(--bg-secondary)] hover:bg-[var(--bg-card)] border border-[var(--border)] text-xs font-bold text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors shadow-sm"
            >
              <ArrowUpDown className="w-3.5 h-3.5" />
              <span>{sortDirection === 'desc' ? 'Newest First' : 'Oldest First'}</span>
            </button>

            <button
              type="button"
              onClick={() => refetchHistory()}
              className="p-2 rounded-sm bg-[var(--bg-secondary)] hover:bg-[var(--bg-card)] border border-[var(--border)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors shadow-sm"
              title="Refresh list"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        <div className="card p-0 border border-[var(--border)] bg-[var(--bg-card)] rounded-md overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left" id="snapshot-history-table">
              <thead className="bg-[var(--bg-secondary)] text-[var(--text-muted)] font-bold border-b border-[var(--border)] uppercase tracking-wider text-[10px]">
                <tr>
                  <th className="py-3 px-3.5">Snapshot Date</th>
                  <th className="py-3 px-3">Uploaded At</th>
                  <th className="py-3 px-3">Files &amp; SHA-256</th>
                  <th className="py-3 px-3 text-right">Row Count</th>
                  <th className="py-3 px-3 text-right">Q-Slice Deals / ACV</th>
                  <th className="py-3 px-3 text-center">Source Check</th>
                  <th className="py-3 px-3 text-center">Partial Flag</th>
                  <th className="py-3 px-3 text-center">Active Marker</th>
                  <th className="py-3 px-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {loadingHistory ? (
                  <tr>
                    <td colSpan={9} className="py-8 text-center text-[var(--text-muted)]">
                      <RefreshCw className="w-4 h-4 animate-spin mx-auto mb-1 text-teal-500" />
                      Loading history snapshots...
                    </td>
                  </tr>
                ) : sortedAndFilteredHistory.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="py-8 text-center text-[var(--text-muted)]">
                      No snapshots match the filter criteria.
                    </td>
                  </tr>
                ) : (
                  sortedAndFilteredHistory.map((h: any) => (
                    <tr key={h.id} className="hover:bg-[var(--bg-secondary)]/50 transition-colors">
                      {/* Snapshot Date */}
                      <td className="py-3 px-3.5 font-extrabold text-[var(--text-primary)] whitespace-nowrap">
                        {h.snapshot_date}
                      </td>

                      {/* Uploaded At */}
                      <td className="py-3 px-3 text-[var(--text-muted)] whitespace-nowrap">
                        {h.uploaded_at ? new Date(h.uploaded_at).toLocaleString() : '—'}
                      </td>

                      {/* Files + sha256 prefix */}
                      <td className="py-3 px-3 max-w-[200px]">
                        {h.files && h.files.length > 0 ? (
                          <div className="space-y-1">
                            {h.files.map((f: any, fIdx: number) => (
                              <div key={fIdx} className="truncate text-[11px]" title={`${f.filename} (${f.sha256})`}>
                                <span className="font-semibold text-[var(--text-secondary)]">{f.filename}</span>
                                {f.sha256 && (
                                  <span className="ml-1.5 font-mono text-[9px] px-1 py-0.2 rounded bg-[var(--bg-secondary)] border border-[var(--border-subtle)] text-[var(--text-muted)]">
                                    {f.sha256.slice(0, 8)}
                                  </span>
                                )}
                              </div>
                            ))}
                          </div>
                        ) : (
                          <span className="text-[var(--text-muted)]">—</span>
                        )}
                      </td>

                      {/* Row Count */}
                      <td className="py-3 px-3 text-right font-mono font-semibold text-[var(--text-primary)]">
                        {formatNumber(h.active_row_count ?? h.row_count)}
                        {h.active_row_count != null && h.row_count != null && h.active_row_count !== h.row_count && (
                          <span className="block text-[10px] text-[var(--text-muted)]">
                            ({formatNumber(h.row_count)} raw)
                          </span>
                        )}
                      </td>

                      {/* Q-Slice Deals / ACV */}
                      <td className="py-3 px-3 text-right whitespace-nowrap">
                        <span className="font-bold text-[var(--text-primary)]">
                          {formatNumber(h.q_slice_deals ?? 0)} deals
                        </span>
                        <span className="block text-[10px] font-mono text-teal-600 dark:text-teal-400">
                          {formatCurrency(h.q_slice_acv ?? 0)}
                        </span>
                      </td>

                      {/* Source check badge (Clickable detail) */}
                      <td className="py-3 px-3 text-center whitespace-nowrap">
                        {h.source_checks && h.source_checks.total > 0 ? (
                          <button
                            type="button"
                            onClick={async () => {
                              setSelectedHistoryCheckSnap(h)
                              setLoadingChecks(true)
                              try {
                                const res = await getSnapshotChecks(h.id)
                                setChecksModalData(res.items || res.checks || [])
                              } catch {
                                setChecksModalData([])
                              } finally {
                                setLoadingChecks(false)
                              }
                            }}
                            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-sm text-[10px] font-bold border transition-colors ${
                              h.source_checks.badge === 'green'
                                ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/20'
                                : h.source_checks.badge === 'red'
                                ? 'bg-rose-500/10 text-rose-700 dark:text-rose-400 border-rose-500/30 hover:bg-rose-500/20'
                                : 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/30 hover:bg-amber-500/20'
                            }`}
                            title="Click to view detailed control checks"
                          >
                            <CheckCircle2 className="w-3 h-3" />
                            {h.source_checks.badge === 'green'
                              ? `Pass (${h.source_checks.passed})`
                              : `${h.source_checks.failed} Fail`}
                          </button>
                        ) : (
                          <span className="text-[var(--text-muted)]">—</span>
                        )}
                      </td>

                      {/* Partial Flag */}
                      <td className="py-3 px-3 text-center whitespace-nowrap">
                        {h.last_week_is_partial ? (
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
                            Partial
                          </span>
                        ) : (
                          <span className="text-[10px] text-[var(--text-muted)]">Complete</span>
                        )}
                      </td>

                      {/* Active Marker */}
                      <td className="py-3 px-3 text-center whitespace-nowrap">
                        {h.is_active_today ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-sm text-[10px] font-black bg-teal-500/15 text-teal-600 dark:text-teal-400 border border-teal-500/30">
                            <Check className="w-3 h-3" />
                            Active
                          </span>
                        ) : (
                          <span className="text-[var(--text-muted)]">—</span>
                        )}
                      </td>

                      {/* Row Actions */}
                      <td className="py-3 px-3.5 text-right whitespace-nowrap">
                        <div className="flex items-center justify-end gap-1.5">
                          {/* View details button: everyone can click */}
                          <button
                            type="button"
                            onClick={() => handleOpenDetail(h.id)}
                            className="p-1.5 rounded-lg bg-[var(--bg-secondary)] hover:bg-[var(--bg-card)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-[var(--border)] transition-colors"
                            title="Open snapshot details"
                          >
                            <Eye className="w-3.5 h-3.5" />
                          </button>

                          {/* Admin-only write controls */}
                          {isAdmin && (
                            <>
                              {!h.is_active_today && (
                                <button
                                  type="button"
                                  onClick={() => handleSetActive(h.id)}
                                  disabled={settingActiveId === h.id}
                                  className="px-2 py-1 rounded-lg text-[10px] font-bold bg-teal-500/10 hover:bg-teal-500/20 text-teal-600 dark:text-teal-400 border border-teal-500/30 transition-colors"
                                  title="Mark as active today"
                                >
                                  {settingActiveId === h.id ? 'Setting...' : 'Set Active'}
                                </button>
                              )}

                              <button
                                type="button"
                                onClick={() => handleInitiateReplace(h)}
                                className="px-2 py-1 rounded-lg text-[10px] font-semibold bg-[var(--bg-secondary)] hover:bg-[var(--bg-card)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-[var(--border)] transition-colors"
                                title="Stage files to replace this snapshot"
                              >
                                Replace
                              </button>

                              <button
                                type="button"
                                onClick={() => setSnapshotToDelete(h)}
                                className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-rose-500 hover:bg-rose-500/10 transition-colors"
                                title="Delete snapshot"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* ─────────────────────────────────────────────────────────────────────────
          SECTION 4: COVERAGE STRIP
          Shows which dates exist, gaps in working days, and the yesterday / last-week
          snapshot each date resolves to.
      ───────────────────────────────────────────────────────────────────────── */}
      {coverageData && (
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-black uppercase tracking-wider text-[var(--text-muted)] flex items-center gap-2">
              <Calendar className="w-4 h-4 text-teal-500" />
              4. Working-Day Ingestion Coverage &amp; Resolution Strip
            </h2>
            <span className="text-xs font-bold text-teal-600 dark:text-teal-400 bg-teal-500/10 px-2.5 py-1 rounded-sm border border-teal-500/20">
              {coverageData.presentWorkingDays} of {coverageData.totalWorkingDays} working days captured
            </span>
          </div>

          <div className="card p-6 border border-[var(--border)] bg-[var(--bg-card)] rounded-md shadow-sm space-y-5">
            {/* Calendar Working Day Tiles Strip */}
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-2.5">
                Working Day Calendar Track
              </h3>
              <div className="flex flex-wrap gap-2">
                {coverageData.workingDaysInRange.map((dateStr) => {
                  const exists = !coverageData.missingDays.includes(dateStr)
                  const info = coverageData.baselineMap[dateStr]
                  return (
                    <div
                      key={dateStr}
                      className={`p-2.5 rounded-sm border text-xs flex flex-col justify-between min-w-[125px] transition-all ${
                        exists
                          ? info?.isActive
                            ? 'bg-teal-500/15 border-teal-500/40 text-[var(--text-primary)]'
                            : 'bg-emerald-500/10 border-emerald-500/30 text-[var(--text-primary)]'
                          : 'bg-rose-500/5 border-rose-500/30 border-dashed text-rose-700 dark:text-rose-400'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-1 mb-1">
                        <span className="font-bold text-[11px]">{dateStr}</span>
                        {exists ? (
                          info?.isActive ? (
                            <span className="text-[9px] font-black px-1 rounded bg-teal-500/20 text-teal-700 dark:text-teal-300">
                              Active
                            </span>
                          ) : (
                            <CheckCircle2 className="w-3 h-3 text-emerald-500" />
                          )
                        ) : (
                          <AlertTriangle className="w-3 h-3 text-rose-500" />
                        )}
                      </div>

                      <div className="text-[10px] text-[var(--text-muted)] space-y-0.5">
                        {exists ? (
                          <>
                            <div>Yest: {info?.yesterday ?? '—'}</div>
                            <div className="truncate">LW: {info?.lastWeek ?? '—'}</div>
                          </>
                        ) : (
                          <span className="text-rose-600 dark:text-rose-400 font-semibold">Missing Working Day</span>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Coverage Gaps Notice */}
            {coverageData.missingDays.length > 0 ? (
              <div className="p-3.5 rounded-sm bg-amber-500/10 border border-amber-500/20 text-amber-800 dark:text-amber-300 text-xs flex items-center gap-3">
                <AlertTriangle className="w-4 h-4 text-amber-500 flex-shrink-0" />
                <div>
                  <strong>Working-Day Gaps Detected:</strong> The following business days have no snapshot in history:{' '}
                  <span className="font-mono font-bold">{coverageData.missingDays.join(', ')}</span>.
                  Dashboards referencing these days fall back to nearest prior snapshot or file union.
                </div>
              </div>
            ) : (
              <div className="p-3 rounded-sm bg-emerald-500/10 border border-emerald-500/20 text-emerald-800 dark:text-emerald-300 text-xs flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                <span>Continuous coverage: Every working day within this range is recorded cleanly in the database.</span>
              </div>
            )}
          </div>
        </section>
      )}

      {/* Database Connection Footer Line */}
      <div className="pt-2 pb-6 flex items-center justify-center">
        <p className="text-xs font-medium text-[var(--text-muted)] flex items-center gap-1.5">
          <Database className="w-3.5 h-3.5 text-teal-500 flex-shrink-0" />
          <span>
            Database:{' '}
            {healthData?.database?.dialect
              ? healthData.database.dialect.toLowerCase().includes('postgres')
                ? 'PostgreSQL'
                : 'SQLite'
              : 'PostgreSQL'}{' '}
            ·{' '}
            <span className={healthData?.database?.connected !== false ? 'text-emerald-600 dark:text-emerald-400 font-semibold' : 'text-rose-600 dark:text-rose-400 font-semibold'}>
              {healthData?.database?.connected !== false ? 'connected' : 'disconnected'}
            </span>
          </span>
        </p>
      </div>

      {/* ── MODAL: Source Reconciliation Details ──────────────────────────────── */}
      {selectedHistoryCheckSnap && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60"
          onClick={() => setSelectedHistoryCheckSnap(null)}
        >
          <div
            className="card p-6 border border-[var(--border)] max-w-4xl w-full max-h-[85vh] flex flex-col space-y-4 shadow-2xl bg-[var(--bg-card)] rounded-2xl overflow-hidden relative"
            onClick={(e) => e.stopPropagation()}
          >
            
            <div className="flex items-center justify-between border-b border-[var(--border)] pb-3.5">
              <div>
                <h3 className="font-black text-base text-[var(--text-primary)] flex items-center gap-2">
                  <ShieldCheck className="w-5 h-5 text-teal-500" />
                  Excel Source Reconciliation Checks — {selectedHistoryCheckSnap.snapshot_date}
                </h3>
                <p className="text-xs text-[var(--text-muted)] mt-0.5">
                  Comparison between database aggregations and control summary sheets in the uploaded workbook.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedHistoryCheckSnap(null)}
                className="p-1.5 rounded-sm hover:bg-[var(--bg-secondary)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
              >
                <XCircle className="w-5 h-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto">
              {loadingChecks ? (
                <div className="py-12 flex items-center justify-center gap-2 text-xs text-[var(--text-muted)]">
                  <RefreshCw className="w-4 h-4 animate-spin text-teal-500" />
                  Loading reconciliation checks...
                </div>
              ) : !checksModalData || checksModalData.length === 0 ? (
                <p className="text-center py-10 text-xs text-[var(--text-muted)]">
                  No detailed check records found for this snapshot.
                </p>
              ) : (
                <div className="overflow-x-auto rounded-sm border border-[var(--border)]">
                  <table className="w-full text-xs text-left">
                    <thead className="bg-[var(--bg-secondary)] text-[var(--text-muted)] font-bold uppercase tracking-wider text-[10px] border-b border-[var(--border)] sticky top-0">
                      <tr>
                        <th className="py-2.5 px-3">Status</th>
                        <th className="py-2.5 px-3">Workbook</th>
                        <th className="py-2.5 px-3">Sheet</th>
                        <th className="py-2.5 px-3">Cell / Row</th>
                        <th className="py-2.5 px-3">Metric</th>
                        <th className="py-2.5 px-3 text-right">Excel Value</th>
                        <th className="py-2.5 px-3 text-right">Website Value</th>
                        <th className="py-2.5 px-3 text-right">Diff</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--border)]">
                      {checksModalData.map((chk: any, idx: number) => (
                        <tr
                          key={chk.id || idx}
                          className={chk.status === 'fail' ? 'bg-rose-500/10 font-bold' : 'hover:bg-[var(--bg-secondary)]/50'}
                        >
                          <td className="py-2 px-3">
                            {chk.status === 'pass' ? (
                              <span className="px-2 py-0.5 rounded text-[10px] font-black bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                                MATCH
                              </span>
                            ) : (
                              <span className="px-2 py-0.5 rounded text-[10px] font-black bg-rose-500/10 text-rose-600 dark:text-rose-400">
                                MISMATCH
                              </span>
                            )}
                          </td>
                          <td className="py-2 px-3 text-[var(--text-secondary)] font-medium">{chk.workbook || chk.workbook_name}</td>
                          <td className="py-2 px-3 font-semibold">{chk.sheet || chk.sheet_name}</td>
                          <td className="py-2 px-3 font-mono text-[11px]">{chk.cell_or_row}</td>
                          <td className="py-2 px-3">{chk.metric || chk.metric_name}</td>
                          <td className="py-2 px-3 text-right font-mono font-semibold">{chk.excel_value}</td>
                          <td className="py-2 px-3 text-right font-mono font-semibold">{chk.website_value}</td>
                          <td className="py-2 px-3 text-right font-mono">
                            {chk.diff_value != null ? Number(chk.diff_value).toFixed(2) : Number(chk.diff || 0).toFixed(2)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── MODAL: Snapshot Details (Accessible to Everyone) ───────────────────── */}
      {detailSnapshot && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60"
          onClick={() => setDetailSnapshot(null)}
        >
          <div
            className="card p-6 border border-[var(--border)] max-w-lg w-full space-y-4 shadow-2xl bg-[var(--bg-card)] rounded-2xl overflow-hidden relative"
            onClick={(e) => e.stopPropagation()}
          >
            
            <div className="flex items-center justify-between border-b border-[var(--border)] pb-3.5">
              <div>
                <h3 className="font-black text-base text-[var(--text-primary)] flex items-center gap-2">
                  <Database className="w-5 h-5 text-teal-500" />
                  Snapshot Details — {detailSnapshot.snapshot_date}
                </h3>
                <p className="text-xs text-[var(--text-muted)] mt-0.5">{detailSnapshot.label}</p>
              </div>
              <button
                type="button"
                onClick={() => setDetailSnapshot(null)}
                className="p-1.5 rounded-sm hover:bg-[var(--bg-secondary)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
              >
                <XCircle className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-2.5 text-xs">
              <div className="flex justify-between py-1.5 border-b border-[var(--border-subtle)]">
                <span className="text-[var(--text-muted)]">Snapshot ID:</span>
                <span className="font-mono text-[11px] text-[var(--text-primary)]">{detailSnapshot.id}</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-[var(--border-subtle)]">
                <span className="text-[var(--text-muted)]">Uploaded At:</span>
                <span className="font-semibold text-[var(--text-primary)]">
                  {new Date(detailSnapshot.uploaded_at).toLocaleString()}
                </span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-[var(--border-subtle)]">
                <span className="text-[var(--text-muted)]">Active Opportunities:</span>
                <span className="font-mono font-bold text-teal-600 dark:text-teal-400">
                  {formatNumber(detailSnapshot.active_row_count)}
                </span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-[var(--border-subtle)]">
                <span className="text-[var(--text-muted)]">Raw Ingested Rows:</span>
                <span className="font-mono text-[var(--text-primary)]">
                  {formatNumber(detailSnapshot.row_count)}
                </span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-[var(--border-subtle)]">
                <span className="text-[var(--text-muted)]">Previous Working Day:</span>
                <span className="text-[var(--text-primary)] font-semibold">{detailSnapshot.yesterday_date ?? 'None'}</span>
              </div>
              <div className="flex justify-between py-1.5">
                <span className="text-[var(--text-muted)]">Currently Active Today:</span>
                <span className="font-bold text-[var(--text-primary)]">
                  {detailSnapshot.is_active_today ? 'Yes' : 'No'}
                </span>
              </div>
            </div>

            <div className="pt-3 border-t border-[var(--border-subtle)] flex justify-end">
              <button
                type="button"
                onClick={() => setDetailSnapshot(null)}
                className="px-4 py-2 rounded-sm bg-[var(--bg-secondary)] hover:bg-[var(--bg-card)] text-xs font-bold text-[var(--text-primary)] border border-[var(--border)] transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── MODAL: Delete Snapshot Confirmation (Admin Only) ─────────────────── */}
      {snapshotToDelete && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60"
          onClick={() => setSnapshotToDelete(null)}
        >
          <div
            className="card p-6 border border-rose-500/30 max-w-md w-full space-y-4 shadow-2xl bg-[var(--bg-card)] rounded-2xl overflow-hidden relative"
            onClick={(e) => e.stopPropagation()}
          >
            
            <div className="flex items-center gap-3 text-rose-600 dark:text-rose-400">
              <div className="p-3 rounded-md bg-rose-500/10 border border-rose-500/20">
                <Trash2 className="w-6 h-6" />
              </div>
              <div>
                <h3 className="font-black text-base text-[var(--text-primary)]">
                  Confirm Snapshot Deletion
                </h3>
                <p className="text-xs text-[var(--text-muted)]">This action is permanent and cannot be undone.</p>
              </div>
            </div>

            <div className="p-4 rounded-sm bg-rose-500/5 border border-rose-500/20 text-xs text-[var(--text-secondary)] space-y-2">
              <p>You are about to permanently remove the snapshot for:</p>
              <ul className="list-disc list-inside space-y-1 font-semibold text-[var(--text-primary)]">
                <li>Date: <span className="font-mono">{snapshotToDelete.snapshot_date}</span></li>
                <li>Total Deals: <span className="font-mono">{formatNumber(snapshotToDelete.row_count)}</span></li>
                <li>Associated Upload Files &amp; Control Checks</li>
              </ul>
            </div>

            <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-[var(--border-subtle)]">
              <button
                type="button"
                onClick={() => setSnapshotToDelete(null)}
                disabled={isDeleting}
                className="px-4 py-2 rounded-sm bg-[var(--bg-secondary)] hover:bg-[var(--bg-card)] text-xs font-semibold text-[var(--text-primary)] border border-[var(--border)] transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmDelete}
                disabled={isDeleting}
                className="px-5 py-2.5 rounded-sm bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold shadow-md shadow-rose-600/20 transition-all flex items-center gap-1.5"
              >
                {isDeleting ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    Deleting...
                  </>
                ) : (
                  <>
                    <Trash2 className="w-3.5 h-3.5" />
                    Delete Snapshot
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
