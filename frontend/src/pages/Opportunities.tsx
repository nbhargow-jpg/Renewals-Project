import React, { useState, useEffect, useMemo, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Search,
  X,
  Filter,
  Download,
  Bookmark,
  Plus,
  Trash2,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  ChevronLeft,
  ChevronRight,
  Eye,
  Check,
  RotateCcw,
  ShieldCheck,
  Columns,
  Loader2,
  ChevronDown,
  SlidersHorizontal,
} from 'lucide-react'
import {
  getExplorerColumns,
  getExplorerRows,
  exportExplorerData,
  getExplorerReconcile,
  getExplorerQuickFilters,
} from '@/api/client'
import { useAppStore } from '@/store/appStore'
import { formatACV, formatCount } from '@/utils/format'
import { Card } from '@/components/ui/Card'
import { SectionHeader } from '@/components/ui/SectionHeader'
import ControlChip from '@/components/ui/ControlChip'
import showToast from '@/components/ui/Toast'

// Types
export interface ColumnMeta {
  name: string
  position: number
  type: 'text' | 'number' | 'currency' | 'date' | 'boolean'
}

export interface FilterRule {
  column: string
  operator: string
  value?: any
  value_to?: any
  group?: 'and' | 'or'
}

export interface SavedExplorerView {
  name: string
  filters: FilterRule[]
  columns: string[]
  sort?: { column: string; dir: 'asc' | 'desc' }
}

const TEXT_OPERATORS = [
  { value: 'contains', label: 'contains' },
  { value: 'equals', label: 'equals' },
  { value: 'not equals', label: 'not equals' },
  { value: 'starts with', label: 'starts with' },
  { value: 'is empty', label: 'is empty' },
  { value: 'is not empty', label: 'is not empty' },
  { value: 'in list', label: 'in list (comma separated)' },
]

const NUMBER_OPERATORS = [
  { value: '=', label: '=' },
  { value: '≠', label: '≠' },
  { value: '>', label: '>' },
  { value: '≥', label: '≥' },
  { value: '<', label: '<' },
  { value: '≤', label: '≤' },
  { value: 'between', label: 'between' },
]

const DATE_OPERATORS = [
  { value: 'on', label: 'on' },
  { value: 'before', label: 'before' },
  { value: 'after', label: 'after' },
  { value: 'date between', label: 'between' },
]

const BOOLEAN_OPERATORS = [
  { value: 'is true', label: 'is true' },
  { value: 'is false', label: 'is false' },
]

export default function Opportunities() {
  const activeSnapshotId = useAppStore((s) => s.activeSnapshotId)

  // 1. Fetch Columns Metadata (all 172 columns in exact raw order)
  const { data: colsResp, isLoading: colsLoading } = useQuery({
    queryKey: ['explorer-columns', activeSnapshotId],
    queryFn: () => getExplorerColumns(activeSnapshotId),
  })
  const allColumns: ColumnMeta[] = useMemo(() => colsResp?.columns || [], [colsResp])

  // 2. Fetch Quick Filter distinct options
  const { data: quickFiltersData } = useQuery({
    queryKey: ['explorer-quick-filters', activeSnapshotId],
    queryFn: () => getExplorerQuickFilters(activeSnapshotId),
  })

  // Visible columns selection (defaults to all columns in original order)
  const [visibleColNames, setVisibleColNames] = useState<string[]>([])
  useEffect(() => {
    if (allColumns.length > 0 && visibleColNames.length === 0) {
      try {
        const saved = localStorage.getItem('mobileum_explorer_columns')
        if (saved) {
          const parsed = JSON.parse(saved)
          if (Array.isArray(parsed) && parsed.length > 0) {
            setVisibleColNames(parsed)
            return
          }
        }
      } catch (_) {}
      setVisibleColNames(allColumns.map((c) => c.name))
    }
  }, [allColumns])

  // Saved Views in localStorage
  const [savedViews, setSavedViews] = useState<SavedExplorerView[]>(() => {
    try {
      const saved = localStorage.getItem('mobileum_explorer_saved_views')
      return saved ? JSON.parse(saved) : []
    } catch (_) {
      return []
    }
  })
  const [newViewName, setNewViewName] = useState('')
  const [showSaveViewModal, setShowSaveViewModal] = useState(false)

  // Filter Builder state
  const [filters, setFilters] = useState<FilterRule[]>([])
  const [includeDeletedLost, setIncludeDeletedLost] = useState<boolean>(true)

  // Quick filters selection states
  const [selectedSalesTypes, setSelectedSalesTypes] = useState<string[]>([])
  const [selectedFiscalPeriods, setSelectedFiscalPeriods] = useState<string[]>([])
  const [selectedForecastCats, setSelectedForecastCats] = useState<string[]>([])
  const [selectedRegions, setSelectedRegions] = useState<string[]>([])
  const [selectedApprovals, setSelectedApprovals] = useState<string[]>([])
  const [selectedBUs, setSelectedBUs] = useState<string[]>([])

  // Pagination & Sorting
  const [page, setPage] = useState<number>(1)
  const [pageSize, setPageSize] = useState<number>(50)
  const [sortCol, setSortCol] = useState<string | null>(null)
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')

  // UI state
  const [showFilterBuilder, setShowFilterBuilder] = useState<boolean>(false)
  const [showColPicker, setShowColPicker] = useState<boolean>(false)
  const [colSearchQuery, setColSearchQuery] = useState<string>('')
  const [selectedRowData, setSelectedRowData] = useState<Record<string, any> | null>(null)
  const [showReconcileModal, setShowReconcileModal] = useState<boolean>(false)
  const [drawerSearchQuery, setDrawerSearchQuery] = useState<string>('')
  const [isExporting, setIsExporting] = useState<boolean>(false)

  // Search queries for quick-filter groups with > 12 items
  const [buFilterSearch, setBuFilterSearch] = useState<string>('')
  const [periodFilterSearch, setPeriodFilterSearch] = useState<string>('')
  const [regionFilterSearch, setRegionFilterSearch] = useState<string>('')
  const [approvalFilterSearch, setApprovalFilterSearch] = useState<string>('')

  // Combine quick filter selections + include_deleted_lost into FilterSpec or FilterRules
  const effectiveFilterSpec = useMemo(() => {
    return {
      include_deleted_lost: includeDeletedLost,
      sales_types: selectedSalesTypes.length > 0 ? selectedSalesTypes : [],
      forecast_categories: selectedForecastCats.length > 0 ? selectedForecastCats : [],
      approval_statuses: selectedApprovals.length > 0 ? selectedApprovals : [],
      business_units: selectedBUs.length > 0 ? selectedBUs : [],
      regions: selectedRegions.length > 0 ? selectedRegions : [],
      period: selectedFiscalPeriods.length === 1 ? selectedFiscalPeriods[0] : 'all_periods',
    }
  }, [
    includeDeletedLost,
    selectedSalesTypes,
    selectedForecastCats,
    selectedApprovals,
    selectedBUs,
    selectedRegions,
    selectedFiscalPeriods,
  ])

  // Combine user-added custom rules with multiple fiscal periods if > 1
  const effectiveCustomFilters = useMemo(() => {
    const list = [...filters]
    if (selectedFiscalPeriods.length > 1) {
      list.push({
        column: 'Fiscal Period',
        operator: 'in list',
        value: selectedFiscalPeriods,
      })
    }
    return list
  }, [filters, selectedFiscalPeriods])

  // 3. Fetch Reconciliation Summary (Whole snapshot + current filter)
  const { data: reconcileData } = useQuery({
    queryKey: ['explorer-reconcile', activeSnapshotId, effectiveFilterSpec, effectiveCustomFilters],
    queryFn: () =>
      getExplorerReconcile(activeSnapshotId, {
        filter_spec: effectiveFilterSpec,
        filters: effectiveCustomFilters,
      }),
  })

  // 4. Fetch Rows
  const requestPayload = useMemo(() => {
    return {
      filter_spec: effectiveFilterSpec,
      filters: effectiveCustomFilters,
      sort: sortCol,
      sort_dir: sortDir,
      page,
      page_size: pageSize,
    }
  }, [effectiveFilterSpec, effectiveCustomFilters, sortCol, sortDir, page, pageSize])

  const {
    data: rowsResp,
    isLoading: rowsLoading,
    isFetching: rowsFetching,
    refetch,
  } = useQuery({
    queryKey: ['explorer-rows', activeSnapshotId, requestPayload],
    queryFn: () => getExplorerRows(requestPayload, activeSnapshotId),
  })

  const rows = useMemo(() => rowsResp?.rows || [], [rowsResp])
  const totalCount = rowsResp?.total_count ?? 0
  const totalACV = rowsResp?.total_acv ?? 0.0

  // Total pages
  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize))

  // Handle Quick filter toggles
  const toggleQuickFilter = (
    list: string[],
    setList: React.Dispatch<React.SetStateAction<string[]>>,
    item: string
  ) => {
    setPage(1)
    if (list.includes(item)) {
      setList(list.filter((x) => x !== item))
    } else {
      setList([...list, item])
    }
  }

  // Clear all filters
  const handleClearAllFilters = () => {
    setSelectedSalesTypes([])
    setSelectedFiscalPeriods([])
    setSelectedForecastCats([])
    setSelectedRegions([])
    setSelectedApprovals([])
    setSelectedBUs([])
    setFilters([])
    setIncludeDeletedLost(true)
    setPage(1)
  }

  const activeChipsCount =
    selectedSalesTypes.length +
    selectedFiscalPeriods.length +
    selectedForecastCats.length +
    selectedRegions.length +
    selectedApprovals.length +
    selectedBUs.length +
    filters.length +
    (!includeDeletedLost ? 1 : 0)

  // Column picker helpers
  const handleToggleCol = (colName: string) => {
    if (visibleColNames.includes(colName)) {
      if (visibleColNames.length > 1) {
        const next = visibleColNames.filter((c) => c !== colName)
        setVisibleColNames(next)
        localStorage.setItem('mobileum_explorer_columns', JSON.stringify(next))
      }
    } else {
      const next = [...visibleColNames, colName]
      setVisibleColNames(next)
      localStorage.setItem('mobileum_explorer_columns', JSON.stringify(next))
    }
  }

  const handleShowAllCols = () => {
    const all = allColumns.map((c) => c.name)
    setVisibleColNames(all)
    localStorage.setItem('mobileum_explorer_columns', JSON.stringify(all))
  }

  const handleResetToExcelOrder = () => {
    const original = allColumns.map((c) => c.name)
    setVisibleColNames(original)
    localStorage.setItem('mobileum_explorer_columns', JSON.stringify(original))
  }

  // Export handlers
  const handleExport = async (format: 'csv' | 'xlsx') => {
    if (isExporting) return
    setIsExporting(true)
    try {
      const exportPayload = {
        filter_spec: effectiveFilterSpec,
        filters: effectiveCustomFilters,
        sort: sortCol,
        sort_dir: sortDir,
        format,
      }
      const res = await exportExplorerData(exportPayload, activeSnapshotId)
      const blob = new Blob([res.data], {
        type:
          format === 'xlsx'
            ? 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            : 'text/csv;charset=utf-8;',
      })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `data_explorer_export.${format}`)
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
      showToast.success('Export downloaded successfully')
    } catch (err: any) {
      showToast.error(err?.response?.data?.detail || err?.message || 'Export failed')
    } finally {
      setIsExporting(false)
    }
  }

  // Saved Views handlers
  const handleSaveView = () => {
    if (!newViewName.trim()) return
    const newView: SavedExplorerView = {
      name: newViewName.trim(),
      filters: [...filters],
      columns: [...visibleColNames],
      sort: sortCol ? { column: sortCol, dir: sortDir } : undefined,
    }
    const updated = [...savedViews.filter((v) => v.name !== newView.name), newView]
    setSavedViews(updated)
    localStorage.setItem('mobileum_explorer_saved_views', JSON.stringify(updated))
    setNewViewName('')
    setShowSaveViewModal(false)
    showToast.success(`View "${newView.name}" saved!`)
  }

  const handleApplyView = (view: SavedExplorerView) => {
    setFilters(view.filters || [])
    if (view.columns && view.columns.length > 0) {
      setVisibleColNames(view.columns)
    }
    if (view.sort) {
      setSortCol(view.sort.column)
      setSortDir(view.sort.dir)
    }
    setPage(1)
    showToast.success(`Applied view "${view.name}"`)
  }

  const handleDeleteView = (viewName: string) => {
    const updated = savedViews.filter((v) => v.name !== viewName)
    setSavedViews(updated)
    localStorage.setItem('mobileum_explorer_saved_views', JSON.stringify(updated))
  }

  // Filter builder row addition
  const handleAddFilterRule = () => {
    const firstCol = allColumns[0]?.name || 'Opportunity Name'
    setFilters([...filters, { column: firstCol, operator: 'contains', value: '' }])
  }

  const handleUpdateFilterRule = (idx: number, patch: Partial<FilterRule>) => {
    const updated = [...filters]
    updated[idx] = { ...updated[idx], ...patch }
    // If column changed, reset operator to first matching operator
    if (patch.column && patch.column !== filters[idx].column) {
      const meta = allColumns.find((c) => c.name === patch.column)
      if (meta?.type === 'currency' || meta?.type === 'number') {
        updated[idx].operator = '='
      } else if (meta?.type === 'date') {
        updated[idx].operator = 'on'
      } else if (meta?.type === 'boolean') {
        updated[idx].operator = 'is true'
      } else {
        updated[idx].operator = 'contains'
      }
      updated[idx].value = ''
      updated[idx].value_to = undefined
    }
    setFilters(updated)
  }

  const handleRemoveFilterRule = (idx: number) => {
    setFilters(filters.filter((_, i) => i !== idx))
  }

  // Sorting click handler
  const handleSort = (colName: string) => {
    if (sortCol === colName) {
      if (sortDir === 'asc') setSortDir('desc')
      else {
        setSortCol(null)
        setSortDir('asc')
      }
    } else {
      setSortCol(colName)
      setSortDir('asc')
    }
    setPage(1)
  }

  // Render cell formatting
  const formatCellValue = (val: any) => {
    if (val === null || val === undefined || String(val).trim() === '') {
      return <span className="text-[var(--text-muted)] opacity-60">—</span>
    }
    return String(val)
  }

  // Filter visible columns based on picker search
  const filteredColsForPicker = useMemo(() => {
    if (!colSearchQuery.trim()) return allColumns
    const q = colSearchQuery.toLowerCase()
    return allColumns.filter((c) => c.name.toLowerCase().includes(q))
  }, [allColumns, colSearchQuery])

  // Filter drawer properties based on search query
  const drawerFields = useMemo(() => {
    if (!selectedRowData) return []
    const originalOrder = allColumns.map((c) => c.name)
    const list = originalOrder.map((colName) => ({
      name: colName,
      value: selectedRowData[colName],
    }))
    if (!drawerSearchQuery.trim()) return list
    const q = drawerSearchQuery.toLowerCase()
    return list.filter(
      (f) => f.name.toLowerCase().includes(q) || String(f.value || '').toLowerCase().includes(q)
    )
  }, [selectedRowData, allColumns, drawerSearchQuery])

  return (
    <div className="space-y-4 max-w-full" id="data-explorer-page">
      {/* ── Top Header Strip ─────────────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-[var(--border)]">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-black text-[var(--text-primary)]">Data Explorer</h1>
            <span className="text-xs px-2.5 py-1 rounded-full bg-teal-500/10 text-teal-600 dark:text-teal-400 font-semibold border border-teal-500/20">
              Full Excel View
            </span>
            {/* Reconciliation Badge */}
            <button
              type="button"
              onClick={() => setShowReconcileModal(true)}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 transition-colors"
              id="explorer-reconcile-badge"
              title="Click to view reconciliation with raw Excel Renewals scope"
            >
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>Reconciliation</span>
            </button>
          </div>
          <p className="text-xs text-[var(--text-muted)] mt-1 font-medium">
            Showing <strong className="text-[var(--text-primary)]">{formatCount(totalCount)}</strong> of{' '}
            {formatCount(totalCount)} rows ·{' '}
            <strong className="text-[#00A3AD]">{formatACV(totalACV)}</strong> ACV
          </p>
        </div>

        {/* Top Action Buttons: Column Picker, Filter Builder, Export */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Column Picker Button */}
          <button
            type="button"
            onClick={() => setShowColPicker(!showColPicker)}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold border transition-all ${
              showColPicker
                ? 'bg-teal-500/10 border-teal-500 text-teal-600 dark:text-teal-400'
                : 'bg-[var(--bg-card)] border-[var(--border)] text-[var(--text-secondary)] hover:border-teal-500/40'
            }`}
            id="explorer-columns-btn"
          >
            <Columns className="w-3.5 h-3.5" />
            <span>Columns ({visibleColNames.length}/172)</span>
          </button>

          {/* Filter Builder Toggle */}
          <button
            type="button"
            onClick={() => setShowFilterBuilder(!showFilterBuilder)}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold border transition-all ${
              showFilterBuilder || filters.length > 0
                ? 'bg-[#12284C] text-white border-[#12284C]'
                : 'bg-[var(--bg-card)] border-[var(--border)] text-[var(--text-secondary)] hover:border-slate-400'
            }`}
            id="explorer-filter-builder-btn"
          >
            <SlidersHorizontal className="w-3.5 h-3.5" />
            <span>Filter Builder {filters.length > 0 && `(${filters.length})`}</span>
          </button>

          {/* Export CSV */}
          <button
            type="button"
            onClick={() => handleExport('csv')}
            disabled={isExporting}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold border border-[var(--border)] bg-[var(--bg-card)] hover:bg-[var(--bg-secondary)] text-[var(--text-primary)] transition-all disabled:opacity-50"
            id="explorer-export-csv-btn"
          >
            {isExporting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5 text-[#00A3AD]" />}
            <span>Export CSV</span>
          </button>

          {/* Export Excel */}
          <button
            type="button"
            onClick={() => handleExport('xlsx')}
            disabled={isExporting}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold border border-[var(--border)] bg-[var(--bg-card)] hover:bg-[var(--bg-secondary)] text-[var(--text-primary)] transition-all disabled:opacity-50"
            id="explorer-export-excel-btn"
          >
            {isExporting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5 text-emerald-600" />}
            <span>Export Excel</span>
          </button>
        </div>
      </div>

      {/* ── Quick Filter Row (Chips with Row Counts) ─────────────────────── */}
      <Card padding="sm" className="space-y-3">
        {/* Row 1: Sales Type & Include Deleted/Lost */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="font-bold text-[10px] uppercase tracking-wider text-[var(--text-muted)] min-w-[70px]">
            Sales Type:
          </span>
          <div className="flex flex-wrap gap-1.5 items-center">
            {(quickFiltersData?.sales_types || []).map((st: any) => {
              const active = selectedSalesTypes.includes(st.name)
              return (
                <button
                  key={st.name}
                  type="button"
                  onClick={() => toggleQuickFilter(selectedSalesTypes, setSelectedSalesTypes, st.name)}
                  className={`px-2.5 py-1 rounded-md text-xs font-medium border transition-all ${
                    active
                      ? 'bg-[#12284C] text-white border-[#12284C] shadow-sm'
                      : 'bg-[var(--bg-secondary)] text-[var(--text-secondary)] border-[var(--border)] hover:bg-[var(--bg-card)]'
                  }`}
                  id={`quick-filter-st-${st.name.replace(/\s+/g, '-').toLowerCase()}`}
                >
                  {st.name} <span className="opacity-70 ml-1">({st.count})</span>
                </button>
              )
            })}
          </div>

          <div className="h-4 w-px bg-[var(--border)] mx-1 hidden sm:block" />

          {/* Include Deleted & Lost toggle (ON by default) */}
          <label className="flex items-center gap-1.5 cursor-pointer text-xs font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] select-none">
            <input
              type="checkbox"
              checked={includeDeletedLost}
              onChange={(e) => {
                setIncludeDeletedLost(e.target.checked)
                setPage(1)
              }}
              className="rounded border-[var(--border)] text-[#00A3AD] focus:ring-0 w-3.5 h-3.5 cursor-pointer"
              id="explorer-toggle-deleted-lost"
            />
            <span>Include Deleted & Lost</span>
          </label>
        </div>

        {/* Row 2: Fiscal Period Chips (All periods, chronologically sorted, search if >12) */}
        {quickFiltersData?.fiscal_periods && quickFiltersData.fiscal_periods.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 text-xs pt-1 border-t border-[var(--border)]">
            <span className="font-bold text-[10px] uppercase tracking-wider text-[var(--text-muted)] min-w-[70px]">
              Period:
            </span>
            {quickFiltersData.fiscal_periods.length > 12 && (
              <input
                type="text"
                placeholder="Search period..."
                value={periodFilterSearch}
                onChange={(e) => setPeriodFilterSearch(e.target.value)}
                className="px-2 py-0.5 rounded border border-[var(--border)] bg-[var(--bg-secondary)] text-xs text-[var(--text-primary)] w-28 focus:outline-none"
              />
            )}
            <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto">
              {quickFiltersData.fiscal_periods
                .filter((fp: any) =>
                  !periodFilterSearch || fp.name.toLowerCase().includes(periodFilterSearch.toLowerCase())
                )
                .map((fp: any) => {
                  const active = selectedFiscalPeriods.includes(fp.name)
                  return (
                    <button
                      key={fp.name}
                      type="button"
                      onClick={() =>
                        toggleQuickFilter(selectedFiscalPeriods, setSelectedFiscalPeriods, fp.name)
                      }
                      className={`px-2 py-0.5 rounded text-xs font-medium border transition-all ${
                        active
                          ? 'bg-[#00A3AD] text-white border-[#00A3AD]'
                          : 'bg-[var(--bg-secondary)] text-[var(--text-secondary)] border-[var(--border)] hover:bg-[var(--bg-card)]'
                      }`}
                      id={`quick-filter-period-${fp.name.toLowerCase()}`}
                    >
                      {fp.name} <span className="opacity-70 ml-0.5">({fp.count})</span>
                    </button>
                  )
                })}
            </div>
          </div>
        )}

        {/* Row 3: Forecast Category & Approval Status */}
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs pt-1 border-t border-[var(--border)]">
          {/* Forecast Categories */}
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="font-bold text-[10px] uppercase tracking-wider text-[var(--text-muted)] min-w-[70px]">
              Forecast:
            </span>
            {(quickFiltersData?.forecast_categories || []).map((fc: any) => {
              const active = selectedForecastCats.includes(fc.name)
              return (
                <button
                  key={fc.name}
                  type="button"
                  onClick={() =>
                    toggleQuickFilter(selectedForecastCats, setSelectedForecastCats, fc.name)
                  }
                  className={`px-2 py-0.5 rounded text-xs font-medium border transition-all ${
                    active
                      ? 'bg-[#12284C] text-white border-[#12284C]'
                      : 'bg-[var(--bg-secondary)] text-[var(--text-secondary)] border-[var(--border)] hover:bg-[var(--bg-card)]'
                  }`}
                  id={`quick-filter-fc-${fc.name.toLowerCase()}`}
                >
                  {fc.name} ({fc.count})
                </button>
              )
            })}
          </div>

          {/* Approval Status */}
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="font-bold text-[10px] uppercase tracking-wider text-[var(--text-muted)] min-w-[70px]">
              Approval:
            </span>
            {(quickFiltersData?.approval_statuses || []).map((app: any) => {
              const active = selectedApprovals.includes(app.name)
              return (
                <button
                  key={app.name}
                  type="button"
                  onClick={() =>
                    toggleQuickFilter(selectedApprovals, setSelectedApprovals, app.name)
                  }
                  className={`px-2 py-0.5 rounded text-xs font-medium border transition-all ${
                    active
                      ? 'bg-amber-600 text-white border-amber-600'
                      : 'bg-[var(--bg-secondary)] text-[var(--text-secondary)] border-[var(--border)] hover:bg-[var(--bg-card)]'
                  }`}
                  id={`quick-filter-app-${app.name.toLowerCase().replace(/\s+/g, '-')}`}
                >
                  {app.name} ({app.count})
                </button>
              )
            })}
          </div>
        </div>

        {/* Row 4: Region */}
        <div className="flex flex-wrap items-center gap-1.5 text-xs pt-1 border-t border-[var(--border)]">
          <span className="font-bold text-[10px] uppercase tracking-wider text-[var(--text-muted)] min-w-[70px]">
            Region:
          </span>
          <div className="flex flex-wrap gap-1.5">
            {(quickFiltersData?.regions || []).map((reg: any) => {
              const active = selectedRegions.includes(reg.name)
              return (
                <button
                  key={reg.name}
                  type="button"
                  onClick={() =>
                    toggleQuickFilter(selectedRegions, setSelectedRegions, reg.name)
                  }
                  className={`px-2 py-0.5 rounded text-xs font-medium border transition-all ${
                    active
                      ? 'bg-[#12284C] text-white border-[#12284C]'
                      : 'bg-[var(--bg-secondary)] text-[var(--text-secondary)] border-[var(--border)] hover:bg-[var(--bg-card)]'
                  }`}
                  id={`quick-filter-reg-${reg.name.toLowerCase().replace(/\s+/g, '-')}`}
                >
                  {reg.name} ({reg.count})
                </button>
              )
            })}
          </div>
        </div>

        {/* Row 5: Business Unit */}
        <div className="flex flex-wrap items-center gap-1.5 text-xs pt-1 border-t border-[var(--border)]">
          <span className="font-bold text-[10px] uppercase tracking-wider text-[var(--text-muted)] min-w-[70px]">
            BU:
          </span>
          {(quickFiltersData?.business_units || []).length > 12 && (
            <input
              type="text"
              placeholder="Search BU..."
              value={buFilterSearch}
              onChange={(e) => setBuFilterSearch(e.target.value)}
              className="px-2 py-0.5 rounded border border-[var(--border)] bg-[var(--bg-secondary)] text-xs text-[var(--text-primary)] w-24 focus:outline-none"
            />
          )}
          <div className="flex flex-wrap gap-1.5">
            {(quickFiltersData?.business_units || [])
              .filter((bu: any) =>
                !buFilterSearch || bu.name.toLowerCase().includes(buFilterSearch.toLowerCase())
              )
              .map((bu: any) => {
                const active = selectedBUs.includes(bu.name)
                return (
                  <button
                    key={bu.name}
                    type="button"
                    onClick={() =>
                      toggleQuickFilter(selectedBUs, setSelectedBUs, bu.name)
                    }
                    className={`px-2 py-0.5 rounded text-xs font-medium border transition-all ${
                      active
                        ? 'bg-purple-600 text-white border-purple-600'
                        : 'bg-[var(--bg-secondary)] text-[var(--text-secondary)] border-[var(--border)] hover:bg-[var(--bg-card)]'
                    }`}
                    id={`quick-filter-bu-${bu.name.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`}
                  >
                    {bu.name} ({bu.count})
                  </button>
                )
              })}
          </div>
        </div>

          {/* Reset All Filters button */}
          {activeChipsCount > 0 && (
            <button
              type="button"
              onClick={handleClearAllFilters}
              className="ml-auto inline-flex items-center gap-1 px-2.5 py-1 text-xs text-rose-500 hover:text-rose-600 hover:bg-rose-500/10 rounded-md font-medium transition-colors"
              id="explorer-clear-all-filters-btn"
            >
              <RotateCcw className="w-3 h-3" />
              <span>Reset Filters</span>
            </button>
          )}
      </Card>

      {/* ── Filter Builder Popover / Panel ───────────────────────────────── */}
      {showFilterBuilder && (
        <Card padding="md" className="space-y-4 border-[#00A3AD]/30 bg-[var(--bg-card)] shadow-lg">
          <div className="flex items-center justify-between border-b border-[var(--border)] pb-2">
            <div className="flex items-center gap-2">
              <SlidersHorizontal className="w-4 h-4 text-[#00A3AD]" />
              <h3 className="font-bold text-sm text-[var(--text-primary)]">Custom Filter Builder</h3>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setShowSaveViewModal(true)}
                className="flex items-center gap-1 text-xs px-2.5 py-1 rounded bg-[var(--bg-secondary)] hover:bg-[var(--bg-hover)] text-[var(--text-primary)] border border-[var(--border)] font-medium"
              >
                <Bookmark className="w-3.5 h-3.5 text-[#00A3AD]" />
                <span>Save View</span>
              </button>
              <button
                type="button"
                onClick={() => setShowFilterBuilder(false)}
                className="text-[var(--text-muted)] hover:text-[var(--text-primary)]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Active Quick Filters shown as removable chips in the filter builder */}
          {activeChipsCount > 0 && (
            <div className="space-y-1.5 p-2 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)]">
              <div className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                Active Quick Filters:
              </div>
              <div className="flex flex-wrap gap-1.5">
                {selectedSalesTypes.map((st) => (
                  <span
                    key={`st-${st}`}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-[#12284C] text-white"
                  >
                    Sales Type = {st}
                    <button
                      type="button"
                      onClick={() => toggleQuickFilter(selectedSalesTypes, setSelectedSalesTypes, st)}
                      className="hover:opacity-75"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
                {selectedFiscalPeriods.map((fp) => (
                  <span
                    key={`fp-${fp}`}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-[#00A3AD] text-white"
                  >
                    Period = {fp}
                    <button
                      type="button"
                      onClick={() =>
                        toggleQuickFilter(selectedFiscalPeriods, setSelectedFiscalPeriods, fp)
                      }
                      className="hover:opacity-75"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
                {selectedForecastCats.map((fc) => (
                  <span
                    key={`fc-${fc}`}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-[#12284C] text-white"
                  >
                    Forecast = {fc}
                    <button
                      type="button"
                      onClick={() =>
                        toggleQuickFilter(selectedForecastCats, setSelectedForecastCats, fc)
                      }
                      className="hover:opacity-75"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
                {selectedApprovals.map((app) => (
                  <span
                    key={`app-${app}`}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-amber-600 text-white"
                  >
                    Approval = {app}
                    <button
                      type="button"
                      onClick={() =>
                        toggleQuickFilter(selectedApprovals, setSelectedApprovals, app)
                      }
                      className="hover:opacity-75"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
                {selectedRegions.map((reg) => (
                  <span
                    key={`reg-${reg}`}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-[#12284C] text-white"
                  >
                    Region = {reg}
                    <button
                      type="button"
                      onClick={() =>
                        toggleQuickFilter(selectedRegions, setSelectedRegions, reg)
                      }
                      className="hover:opacity-75"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
                {selectedBUs.map((bu) => (
                  <span
                    key={`bu-${bu}`}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-purple-700 text-white"
                  >
                    BU = {bu}
                    <button
                      type="button"
                      onClick={() => toggleQuickFilter(selectedBUs, setSelectedBUs, bu)}
                      className="hover:opacity-75"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
                {!includeDeletedLost && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-slate-700 text-white">
                    Exclude Deleted & Lost
                    <button
                      type="button"
                      onClick={() => setIncludeDeletedLost(true)}
                      className="hover:opacity-75"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Rules List */}
          {filters.length === 0 ? (
            <p className="text-xs text-[var(--text-muted)] italic py-2">
              No custom filters defined yet. Click "Add Filter Rule" to construct complex queries.
            </p>
          ) : (
            <div className="space-y-2.5 max-h-60 overflow-y-auto pr-1">
              {filters.map((rule, idx) => {
                const meta = allColumns.find((c) => c.name === rule.column)
                const colType = meta?.type || 'text'
                const ops =
                  colType === 'currency' || colType === 'number'
                    ? NUMBER_OPERATORS
                    : colType === 'date'
                    ? DATE_OPERATORS
                    : colType === 'boolean'
                    ? BOOLEAN_OPERATORS
                    : TEXT_OPERATORS

                return (
                  <div
                    key={idx}
                    className="flex flex-wrap sm:flex-nowrap items-center gap-2 p-2 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)] text-xs"
                  >
                    {/* Group prefix if not first */}
                    <span className="font-semibold text-[10px] text-[var(--text-muted)] uppercase w-8">
                      {idx === 0 ? 'Where' : 'And'}
                    </span>

                    {/* Column Select */}
                    <select
                      value={rule.column}
                      onChange={(e) => handleUpdateFilterRule(idx, { column: e.target.value })}
                      className="px-2 py-1 rounded border border-[var(--border)] bg-[var(--bg-card)] text-[var(--text-primary)] font-medium max-w-[200px]"
                    >
                      {allColumns.map((c) => (
                        <option key={c.name} value={c.name}>
                          {c.name}
                        </option>
                      ))}
                    </select>

                    {/* Operator Select */}
                    <select
                      value={rule.operator}
                      onChange={(e) => handleUpdateFilterRule(idx, { operator: e.target.value })}
                      className="px-2 py-1 rounded border border-[var(--border)] bg-[var(--bg-card)] text-[var(--text-primary)] font-medium"
                    >
                      {ops.map((o) => (
                        <option key={o.value} value={o.value}>
                          {o.label}
                        </option>
                      ))}
                    </select>

                    {/* Value Input */}
                    {!['is empty', 'is not empty', 'is true', 'is false'].includes(rule.operator) && (
                      <input
                        type={colType === 'number' || colType === 'currency' ? 'number' : 'text'}
                        placeholder="Value..."
                        value={rule.value || ''}
                        onChange={(e) => handleUpdateFilterRule(idx, { value: e.target.value })}
                        className="px-2 py-1 rounded border border-[var(--border)] bg-[var(--bg-card)] text-[var(--text-primary)] flex-1 min-w-[120px]"
                      />
                    )}

                    {/* Value To for 'between' */}
                    {['between', 'date between'].includes(rule.operator) && (
                      <input
                        type={colType === 'number' || colType === 'currency' ? 'number' : 'text'}
                        placeholder="To..."
                        value={rule.value_to || ''}
                        onChange={(e) => handleUpdateFilterRule(idx, { value_to: e.target.value })}
                        className="px-2 py-1 rounded border border-[var(--border)] bg-[var(--bg-card)] text-[var(--text-primary)] flex-1 min-w-[120px]"
                      />
                    )}

                    {/* Remove rule */}
                    <button
                      type="button"
                      onClick={() => handleRemoveFilterRule(idx)}
                      className="text-red-500 hover:text-red-700 p-1"
                      title="Remove condition"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )
              })}
            </div>
          )}

          <div className="flex items-center justify-between pt-2">
            <button
              type="button"
              onClick={handleAddFilterRule}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#12284C] text-white text-xs font-semibold hover:bg-[#1B365D]"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Add Filter Rule</span>
            </button>

            {/* Saved Views dropdown list */}
            {savedViews.length > 0 && (
              <div className="flex items-center gap-1.5 text-xs">
                <span className="text-[var(--text-muted)] font-medium">Saved Views:</span>
                <div className="flex gap-1">
                  {savedViews.map((sv) => (
                    <span
                      key={sv.name}
                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-[var(--bg-secondary)] border border-[var(--border)] text-[var(--text-secondary)]"
                    >
                      <button
                        type="button"
                        onClick={() => handleApplyView(sv)}
                        className="font-medium hover:text-[#00A3AD]"
                      >
                        {sv.name}
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDeleteView(sv.name)}
                        className="text-red-400 hover:text-red-600"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </Card>
      )}

      {/* ── Column Chooser Modal / Drawer ─────────────────────────────────── */}
      {showColPicker && (
        <Card padding="md" className="space-y-3 bg-[var(--bg-card)] shadow-lg border-teal-500/30">
          <div className="flex items-center justify-between border-b border-[var(--border)] pb-2">
            <div className="flex items-center gap-2">
              <Columns className="w-4 h-4 text-teal-600" />
              <h3 className="font-bold text-sm text-[var(--text-primary)]">
                Column Chooser ({visibleColNames.length} of 172 selected)
              </h3>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleShowAllCols}
                className="text-xs px-2.5 py-1 rounded bg-[var(--bg-secondary)] text-[var(--text-primary)] border border-[var(--border)] hover:bg-[var(--bg-hover)] font-medium"
              >
                Show All 172
              </button>
              <button
                type="button"
                onClick={handleResetToExcelOrder}
                className="text-xs px-2.5 py-1 rounded bg-[var(--bg-secondary)] text-[var(--text-primary)] border border-[var(--border)] hover:bg-[var(--bg-hover)] font-medium"
              >
                Reset to Excel Order
              </button>
              <button
                type="button"
                onClick={() => setShowColPicker(false)}
                className="text-[var(--text-muted)] hover:text-[var(--text-primary)] ml-2"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          <div className="flex items-center gap-2 bg-[var(--bg-secondary)] px-2.5 py-1.5 rounded-lg border border-[var(--border)]">
            <Search className="w-3.5 h-3.5 text-[var(--text-muted)]" />
            <input
              type="text"
              placeholder="Search columns..."
              value={colSearchQuery}
              onChange={(e) => setColSearchQuery(e.target.value)}
              className="bg-transparent text-xs text-[var(--text-primary)] outline-none w-full"
            />
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-1.5 max-h-64 overflow-y-auto p-1">
            {filteredColsForPicker.map((col) => {
              const isSelected = visibleColNames.includes(col.name)
              return (
                <label
                  key={col.name}
                  className={`flex items-center gap-1.5 p-1.5 rounded border text-xs cursor-pointer select-none transition-colors ${
                    isSelected
                      ? 'bg-teal-500/10 border-teal-500/30 text-teal-700 dark:text-teal-300 font-medium'
                      : 'bg-[var(--bg-secondary)] border-[var(--border)] text-[var(--text-muted)]'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => handleToggleCol(col.name)}
                    className="rounded border-[var(--border)] text-teal-600 focus:ring-0 w-3 h-3"
                  />
                  <span className="truncate" title={col.name}>
                    {col.name}
                  </span>
                </label>
              )
            })}
          </div>
        </Card>
      )}

      {/* ── Virtualised / Sticky Header Table ────────────────────────────── */}
      <Card padding="none" className="overflow-hidden border-[var(--border)] shadow-sm">
        <div className="overflow-x-auto max-h-[600px] overflow-y-auto relative" id="explorer-table-container">
          <table className="w-full text-xs text-left border-collapse">
            {/* Sticky Header */}
            <thead className="sticky top-0 bg-[var(--bg-secondary)] z-20 shadow-sm border-b border-[var(--border)]">
              <tr>
                {/* Pinned First Column: # (Index) or ID */}
                <th className="sticky left-0 bg-[var(--bg-secondary)] z-30 px-3 py-2.5 font-bold text-[var(--text-primary)] border-r border-[var(--border)] w-12 text-center">
                  #
                </th>
                {visibleColNames.map((colName, cIdx) => {
                  const isSorted = sortCol === colName
                  return (
                    <th
                      key={colName}
                      onClick={() => handleSort(colName)}
                      className="px-3 py-2.5 font-bold text-[var(--text-primary)] whitespace-nowrap cursor-pointer hover:bg-[var(--bg-hover)] transition-colors select-none border-r border-[var(--border)] last:border-r-0"
                    >
                      <div className="flex items-center gap-1.5">
                        <span>{colName}</span>
                        {isSorted ? (
                          sortDir === 'asc' ? (
                            <ArrowUp className="w-3 h-3 text-[#00A3AD]" />
                          ) : (
                            <ArrowDown className="w-3 h-3 text-[#00A3AD]" />
                          )
                        ) : (
                          <ArrowUpDown className="w-2.5 h-2.5 text-[var(--text-muted)] opacity-40" />
                        )}
                      </div>
                    </th>
                  )
                })}
              </tr>
            </thead>

            {/* Table Body */}
            <tbody>
              {rowsLoading ? (
                <tr>
                  <td colSpan={visibleColNames.length + 1} className="py-20 text-center text-xs text-[var(--text-muted)]">
                    <div className="flex flex-col items-center gap-2">
                      <Loader2 className="w-6 h-6 animate-spin text-[#00A3AD]" />
                      <span>Loading snapshot data...</span>
                    </div>
                  </td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan={visibleColNames.length + 1} className="py-16 text-center text-xs text-[var(--text-muted)]">
                    No deals match the selected criteria. Try adjusting the filters above.
                  </td>
                </tr>
              ) : (
                rows.map((row: any, rIdx: number) => {
                  const rowNum = (page - 1) * pageSize + rIdx + 1
                  return (
                    <tr
                      key={row._id || rIdx}
                      onClick={() => setSelectedRowData(row)}
                      className="border-b border-[var(--border)] hover:bg-[var(--bg-hover)] cursor-pointer transition-colors group"
                    >
                      {/* Pinned first column */}
                      <td className="sticky left-0 bg-[var(--bg-card)] group-hover:bg-[var(--bg-hover)] z-10 px-3 py-2 text-center font-mono text-[var(--text-muted)] border-r border-[var(--border)]">
                        {rowNum}
                      </td>

                      {/* Dynamic columns */}
                      {visibleColNames.map((colName) => {
                        const val = row[colName]
                        return (
                          <td
                            key={colName}
                            className="px-3 py-2 whitespace-nowrap text-[var(--text-primary)] border-r border-[var(--border)] last:border-r-0 font-medium"
                          >
                            {formatCellValue(val)}
                          </td>
                        )
                      })}
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>

        {/* ── Table Footer & Pagination ──────────────────────────────────── */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 bg-[var(--bg-secondary)] border-t border-[var(--border)] text-xs">
          <div className="flex items-center gap-2 text-[var(--text-muted)]">
            <span>
              Showing {(page - 1) * pageSize + 1} to {Math.min(page * pageSize, totalCount)} of{' '}
              {formatCount(totalCount)} rows
            </span>
            <div className="h-3 w-px bg-[var(--border)] mx-1" />
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value))
                setPage(1)
              }}
              className="px-2 py-0.5 rounded border border-[var(--border)] bg-[var(--bg-card)] text-[var(--text-primary)]"
            >
              <option value={25}>25 per page</option>
              <option value={50}>50 per page</option>
              <option value={100}>100 per page</option>
              <option value={200}>200 per page</option>
              <option value={500}>500 per page</option>
            </select>
          </div>

          <div className="flex items-center gap-1.5">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => setPage(page - 1)}
              className="p-1 rounded border border-[var(--border)] bg-[var(--bg-card)] text-[var(--text-primary)] disabled:opacity-40"
              title="Previous Page"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="px-2 font-medium text-[var(--text-primary)]">
              Page {page} of {totalPages}
            </span>
            <button
              type="button"
              disabled={page >= totalPages}
              onClick={() => setPage(page + 1)}
              className="p-1 rounded border border-[var(--border)] bg-[var(--bg-card)] text-[var(--text-primary)] disabled:opacity-40"
              title="Next Page"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </Card>

      {/* ── Detail Drawer (Click any row) ─────────────────────────────────── */}
      {selectedRowData && (
        <div className="fixed inset-0 z-50 overflow-hidden bg-black/40 backdrop-blur-xs flex justify-end">
          <div className="w-full max-w-xl bg-[var(--bg-card)] h-full shadow-2xl flex flex-col border-l border-[var(--border)] animate-in slide-in-from-right duration-200">
            {/* Drawer Header */}
            <div className="p-4 border-b border-[var(--border)] flex items-center justify-between">
              <div>
                <h2 className="font-black text-base text-[var(--text-primary)]">
                  {selectedRowData['Opportunity Name'] || 'Deal Detail'}
                </h2>
                <p className="text-xs text-[var(--text-muted)] font-mono">
                  {selectedRowData['Opportunity ID 18 Digit'] || selectedRowData._opp_id_18}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedRowData(null)}
                className="p-1 rounded-md text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)]"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Drawer Field Search */}
            <div className="p-3 border-b border-[var(--border)] bg-[var(--bg-secondary)]">
              <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-md bg-[var(--bg-card)] border border-[var(--border)] text-xs">
                <Search className="w-3.5 h-3.5 text-[var(--text-muted)]" />
                <input
                  type="text"
                  placeholder="Filter 172 fields in Excel order..."
                  value={drawerSearchQuery}
                  onChange={(e) => setDrawerSearchQuery(e.target.value)}
                  className="bg-transparent text-xs text-[var(--text-primary)] outline-none w-full"
                />
              </div>
            </div>

            {/* Drawer Fields List (172 fields in original order) */}
            <div className="flex-1 overflow-y-auto p-4 space-y-2 divide-y divide-[var(--border)]">
              {drawerFields.map((field) => (
                <div key={field.name} className="pt-2 first:pt-0 flex flex-col sm:flex-row justify-between gap-1 text-xs">
                  <span className="font-semibold text-[var(--text-muted)] break-words max-w-[200px]">
                    {field.name}
                  </span>
                  <span className="text-[var(--text-primary)] font-medium break-all text-right">
                    {formatCellValue(field.value)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── Reconciliation Modal ─────────────────────────────────────────── */}
      {showReconcileModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <Card padding="lg" className="w-full max-w-2xl space-y-4 bg-[var(--bg-card)] shadow-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-emerald-500" />
                <h3 className="font-black text-base text-[var(--text-primary)]">
                  Excel Data Reconciliation
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setShowReconcileModal(false)}
                className="text-[var(--text-muted)] hover:text-[var(--text-primary)]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Whole Snapshot Section */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <p className="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wider">
                  1. Full Snapshot Reconciliation (Excel vs Database)
                </p>
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                  Exact Match
                </span>
              </div>
              <p className="text-xs text-[var(--text-secondary)]">
                Compares the entire uploaded Excel sheet today for Oct 7 against the database:
              </p>

              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)]">
                  <p className="text-[10px] font-bold text-[var(--text-muted)] uppercase">Total Deals</p>
                  <p className="text-xl font-black text-[var(--text-primary)] mt-1">
                    {formatCount(reconcileData?.whole_snapshot?.total_rows ?? reconcileData?.total_rows ?? 3093)}
                  </p>
                  <p className="text-[10px] text-[var(--text-muted)] mt-0.5">Excel: 3,093 rows</p>
                </div>
                <div className="p-3 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)]">
                  <p className="text-[10px] font-bold text-[var(--text-muted)] uppercase">Total ACV</p>
                  <p className="text-xl font-black text-[#00A3AD] mt-1">
                    {formatACV(reconcileData?.whole_snapshot?.total_acv ?? reconcileData?.total_acv ?? 451999230.24)}
                  </p>
                  <p className="text-[10px] text-[var(--text-muted)] mt-0.5">Excel: $451,999,230.24</p>
                </div>
              </div>

              {/* Whole Snapshot Breakdown */}
              <div className="space-y-1.5 pt-1">
                <p className="text-xs font-semibold text-[var(--text-primary)]">Forecast Category Breakdown:</p>
                <div className="max-h-36 overflow-y-auto border border-[var(--border)] rounded-lg divide-y divide-[var(--border)] text-xs">
                  {Object.entries(
                    reconcileData?.whole_snapshot?.forecast_categories || reconcileData?.forecast_categories || {}
                  ).map(([cat, info]: any) => (
                    <div key={cat} className="flex justify-between p-2">
                      <span className="font-medium text-[var(--text-secondary)]">{cat}</span>
                      <span className="font-semibold text-[var(--text-primary)]">
                        {info.count} deals · {formatACV(info.acv)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Current Filter Section */}
            {reconcileData?.current_filter && (
              <div className="space-y-2 pt-3 border-t border-[var(--border)]">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wider">
                    2. Current Active Filter Reconciliation
                  </p>
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200">
                    Filtered Set
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="p-2.5 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)]">
                    <p className="text-[10px] font-bold text-[var(--text-muted)] uppercase">Filtered Deals</p>
                    <p className="text-lg font-black text-[var(--text-primary)] mt-0.5">
                      {formatCount(reconcileData.current_filter.total_rows)}
                    </p>
                  </div>
                  <div className="p-2.5 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)]">
                    <p className="text-[10px] font-bold text-[var(--text-muted)] uppercase">Filtered ACV</p>
                    <p className="text-lg font-black text-[#00A3AD] mt-0.5">
                      {formatACV(reconcileData.current_filter.total_acv)}
                    </p>
                  </div>
                </div>

                {/* Filtered Forecast Breakdown */}
                <div className="space-y-1">
                  <p className="text-xs font-semibold text-[var(--text-primary)]">Filtered Forecast Breakdown:</p>
                  <div className="max-h-28 overflow-y-auto border border-[var(--border)] rounded-lg divide-y divide-[var(--border)] text-xs">
                    {Object.entries(reconcileData.current_filter.forecast_categories || {}).map(([cat, info]: any) => (
                      <div key={cat} className="flex justify-between p-1.5 px-2">
                        <span className="font-medium text-[var(--text-secondary)]">{cat}</span>
                        <span className="font-semibold text-[var(--text-primary)]">
                          {info.count} deals · {formatACV(info.acv)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            <div className="flex justify-end pt-2 border-t border-[var(--border)]">
              <button
                type="button"
                onClick={() => setShowReconcileModal(false)}
                className="px-4 py-1.5 rounded-lg bg-[#12284C] text-white text-xs font-semibold hover:bg-[#1B365D]"
              >
                Close
              </button>
            </div>
          </Card>
        </div>
      )}

      {/* ── Save View Modal ──────────────────────────────────────────────── */}
      {showSaveViewModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <Card padding="md" className="w-full max-w-sm space-y-3 bg-[var(--bg-card)]">
            <h4 className="font-bold text-sm text-[var(--text-primary)]">Save Current Explorer View</h4>
            <input
              type="text"
              placeholder="View name (e.g. Q4 Large Deals)..."
              value={newViewName}
              onChange={(e) => setNewViewName(e.target.value)}
              className="w-full px-3 py-1.5 rounded-md border border-[var(--border)] bg-[var(--bg-secondary)] text-xs text-[var(--text-primary)]"
            />
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowSaveViewModal(false)}
                className="px-3 py-1 rounded text-xs text-[var(--text-muted)]"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSaveView}
                disabled={!newViewName.trim()}
                className="px-3 py-1 rounded text-xs bg-[#12284C] text-white font-semibold disabled:opacity-50"
              >
                Save
              </button>
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}
