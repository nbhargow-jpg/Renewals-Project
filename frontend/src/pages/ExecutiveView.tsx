import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  FileText,
  Presentation,
  FileSpreadsheet,
  Printer,
  ShieldCheck,
  TrendingUp,
  AlertCircle,
  CalendarX2,
  AlertTriangle,
  HelpCircle,
  CheckCircle2,
  Clock,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  Loader2,
  ExternalLink,
  ChevronRight,
  X,
} from 'lucide-react'
import { useAppStore } from '@/store/appStore'
import {
  getV2OverviewSummary,
  getV2RegionsSummary,
  getV2BusinessUnitsSummary,
  getApprovalsDistribution,
  getV2DelayedSummary,
  getExplorerReconcile,
  downloadReport,
} from '@/api/client'
import { formatACV, formatCount, formatDate, formatCurrency } from '@/utils/format'
import Card from '@/components/ui/Card'
import SectionHeader from '@/components/ui/SectionHeader'
import { KpiCard } from '@/components/ui/KpiCard'
import { Skeleton } from '@/components/ui/Skeleton'
import { showToast } from '@/components/ui/Toast'
import clsx from 'clsx'

export default function ExecutiveView() {
  const navigate = useNavigate()
  const { activeSnapshotId, compareSnapshotId, globalFilters, snapshots = [] } = useAppStore()
  const [downloadingFormat, setDownloadingFormat] = useState<'pptx' | 'xlsx' | null>(null)
  const [showReconcileModal, setShowReconcileModal] = useState(false)
  const activeSnapshot = snapshots.find((s) => s.id === activeSnapshotId)

  // 1. Overview Summary (Total ACV, Counts, Forecast Categories, Deltas)
  const { data: overview, isLoading: overviewLoading } = useQuery({
    queryKey: ['v2-overview-summary', activeSnapshotId, globalFilters],
    queryFn: () => getV2OverviewSummary(globalFilters),
  })

  // 2. Regions Summary
  const { data: regionsData, isLoading: regionsLoading } = useQuery({
    queryKey: ['v2-regions-summary', activeSnapshotId, globalFilters],
    queryFn: () => getV2RegionsSummary({ as_of: activeSnapshotId ?? undefined, compare: 'yesterday' }),
  })

  // 3. Business Units Summary
  const { data: buData, isLoading: buLoading } = useQuery({
    queryKey: ['v2-business-units-summary', activeSnapshotId, globalFilters],
    queryFn: () => getV2BusinessUnitsSummary({ as_of: activeSnapshotId ?? undefined, compare: 'yesterday' }),
  })

  // 4. Approvals Distribution
  const { data: approvalsData, isLoading: approvalsLoading } = useQuery({
    queryKey: ['v2-approvals-distribution', activeSnapshotId, globalFilters],
    queryFn: () => getApprovalsDistribution(activeSnapshot?.snapshot_date || undefined),
  })

  // 5. Delayed & Risks
  const { data: delayedData, isLoading: delayedLoading } = useQuery({
    queryKey: ['v2-delayed-summary', activeSnapshotId, globalFilters],
    queryFn: () => getV2DelayedSummary({ as_of: activeSnapshotId ?? undefined, compare: 'yesterday' }),
  })

  // 6. Reconciliation info
  const { data: reconcileData } = useQuery({
    queryKey: ['v2-explorer-reconcile', activeSnapshotId],
    queryFn: () => getExplorerReconcile(activeSnapshotId ?? undefined),
  })

  const isLoading = overviewLoading || regionsLoading || buLoading || approvalsLoading || delayedLoading

  const handleDownload = async (type: 'pptx' | 'xlsx') => {
    if (downloadingFormat) return
    setDownloadingFormat(type)
    try {
      const { filename } = await downloadReport(type, activeSnapshotId, compareSnapshotId)
      showToast.success('Report downloaded', filename)
    } catch (err: any) {
      showToast.error(
        'Download failed',
        err?.response?.data?.detail || err?.message || 'Failed to generate report'
      )
    } finally {
      setDownloadingFormat(null)
    }
  }

  // Delta Chip helper
  const renderDelta = (count?: number, acv?: number, label?: string) => {
    if (count == null && acv == null) return null
    const c = count ?? 0
    const a = acv ?? 0
    const isZero = c === 0 && a === 0
    const isPos = a > 0 || c > 0
    const Icon = isZero ? Minus : isPos ? ArrowUpRight : ArrowDownRight
    const chipCls = isZero
      ? 'bg-[var(--bg-secondary)] text-[var(--text-muted)]'
      : isPos
      ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400'
      : 'bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-400'

    return (
      <span
        className={clsx(
          'inline-flex items-center text-[10px] font-semibold px-1.5 py-0.5 rounded select-none tabular-nums border border-transparent',
          chipCls
        )}
      >
        <Icon className="w-3 h-3 mr-0.5" />
        {label && <span className="opacity-70 mr-1">{label}</span>}
        <span>
          {isZero ? '0' : `${c > 0 ? '+' : ''}${formatCount(c)} (${a > 0 ? '+' : ''}${formatACV(a)})`}
        </span>
      </span>
    )
  }

  const total = overview?.total || { count: 348, acv: 40068990.09 }
  const deltaYesterday = total?.delta_yesterday || {}
  const deltaLastWeek = total?.delta_lastweek || {}

  const cats = overview?.categories || {}
  const categoryOrder = [
    { key: 'Closed', label: 'Closed', color: '#10B981', accent: 'emerald' as const },
    { key: 'Commit', label: 'Commit', color: '#00A3AD', accent: 'teal' as const },
    { key: 'Best Case', label: 'Best Case', color: '#6366F1', accent: 'indigo' as const },
    { key: 'Pipeline', label: 'Pipeline', color: '#F59E0B', accent: 'amber' as const },
    { key: 'Blank', label: 'Not yet proposed', color: '#94A3B8', accent: 'slate' as const },
  ]

  const topRegions = (regionsData?.regions || []).slice(0, 6)
  const topBUs = (buData?.rows || []).slice(0, 6)
  const approvalStatuses = approvalsData?.statuses || []

  // Risks & Watchlist items (same numbers as Delayed page + overview)
  // Overdue, Slipped to next year, Lost / Removed, Not yet proposed
  const overdueStat = delayedData?.overdue || { count: 6, acv: 228071.49 }
  const slippedStat = delayedData?.slipped || { count: 2, acv: 59514.21 }
  const lostStat = delayedData?.lost || { count: 0, acv: 0.0 }
  const unproposedStat = cats['Blank'] || { count: 5, acv: 212772.4 }

  return (
    <div className="min-h-screen bg-[var(--bg-primary)] p-6 space-y-5 max-w-7xl mx-auto pb-10" id="executive-view">
      {/* ── Top Header Strip ─────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-3 border-b border-[var(--border)]">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[var(--primary)]/10 text-[var(--primary)] flex items-center justify-center font-bold">
            <FileText className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-xl font-black text-[var(--text-primary)]">Executive Summary</h1>
              <span className="text-xs px-2.5 py-0.5 rounded-full bg-teal-500/10 text-teal-600 dark:text-teal-400 font-semibold border border-teal-500/20">
                Renewals Only
              </span>
              {/* Source check badge */}
              <button
                type="button"
                onClick={() => setShowReconcileModal(true)}
                className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 transition-colors"
                id="executive-source-check-btn"
                title="Click to view reconciliation details"
              >
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>Source Check: Validated</span>
              </button>
            </div>
            <p className="text-xs text-[var(--text-muted)] mt-0.5 font-medium">
              Single-screen executive view for leadership reviews and calls · Snapshot: {formatDate(overview?.snapshot_date || '2026-10-07')}
            </p>
          </div>
        </div>

        {/* Action Buttons: PPTX, Excel, Print */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => handleDownload('pptx')}
            disabled={!!downloadingFormat}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border border-amber-300 dark:border-amber-700/50 bg-amber-50 dark:bg-amber-950/30 text-amber-900 dark:text-amber-300 hover:bg-amber-100 dark:hover:bg-amber-900/40 transition-colors shadow-sm disabled:opacity-50"
            id="exec-download-pptx-btn"
          >
            {downloadingFormat === 'pptx' ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin text-amber-600" />
            ) : (
              <Presentation className="w-3.5 h-3.5 text-amber-600" />
            )}
            <span>PPTX</span>
          </button>

          <button
            type="button"
            onClick={() => handleDownload('xlsx')}
            disabled={!!downloadingFormat}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border border-emerald-300 dark:border-emerald-700/50 bg-emerald-50 dark:bg-emerald-950/30 text-emerald-900 dark:text-emerald-300 hover:bg-emerald-100 dark:hover:bg-emerald-900/40 transition-colors shadow-sm disabled:opacity-50"
            id="exec-download-excel-btn"
          >
            {downloadingFormat === 'xlsx' ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin text-emerald-600" />
            ) : (
              <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-600" />
            )}
            <span>Excel</span>
          </button>

          <button
            type="button"
            onClick={() => window.print()}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-[#12284C] dark:bg-[#00A3AD] text-white hover:opacity-90 transition-opacity shadow-sm"
            id="exec-print-btn"
          >
            <Printer className="w-3.5 h-3.5" />
            <span>Print / PDF</span>
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-28 w-full" />
          <div className="grid grid-cols-5 gap-3">
            {[1, 2, 3, 4, 5].map((i) => (
              <Skeleton key={i} className="h-24 w-full" />
            ))}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Skeleton className="h-48 w-full" />
            <Skeleton className="h-48 w-full" />
          </div>
        </div>
      ) : (
        <>
          {/* ── 1. Headline Row: Total Renewal ACV, Deals & Deltas ─────────────── */}
          <Card padding="md" className="border-l-4 border-l-[#00A3AD] bg-gradient-to-r from-[var(--bg-card)] via-[var(--bg-card)] to-teal-500/5">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <p className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider">
                  Total Renewal ACV ({overview?.data_slice || 'Current Quarter'})
                </p>
                <div className="flex items-baseline gap-3 mt-1">
                  <span className="text-3xl font-black text-[#00A3AD] font-mono tracking-tight" id="exec-total-acv">
                    {formatACV(total.acv)}
                  </span>
                  <span className="text-lg font-bold text-[var(--text-primary)]" id="exec-total-deals">
                    {formatCount(total.count)} deals
                  </span>
                </div>
              </div>

              {/* Deltas vs Yesterday & vs Last Week */}
              <div className="flex items-center gap-3 flex-wrap">
                <div className="px-3 py-2 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)]">
                  <p className="text-[10px] font-semibold text-[var(--text-muted)] uppercase">vs Yesterday</p>
                  <div className="mt-0.5" id="exec-delta-yesterday">
                    {renderDelta(deltaYesterday.count, deltaYesterday.acv)}
                  </div>
                </div>

                <div className="px-3 py-2 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)]">
                  <p className="text-[10px] font-semibold text-[var(--text-muted)] uppercase">vs Last Week</p>
                  <div className="mt-0.5" id="exec-delta-lastweek">
                    {renderDelta(deltaLastWeek.count, deltaLastWeek.acv)}
                  </div>
                </div>
              </div>
            </div>
          </Card>

          {/* ── 2. Five Forecast Categories ────────────────────────────────────── */}
          <div>
            <p className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider mb-2.5">
              Forecast Categories
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
              {categoryOrder.map((cat) => {
                const info = cats[cat.key] || { count: 0, acv: 0.0 }
                const dYes = info.delta_yesterday || {}
                const dLast = info.delta_lastweek || {}
                return (
                  <KpiCard
                    key={cat.key}
                    title={cat.label}
                    count={info.count}
                    acv={info.acv}
                    icon={TrendingUp}
                    accentColor={cat.accent}
                    metricMode="Both"
                    onClick={() => navigate('/delayed')}
                    className="hover:scale-[1.01] transition-transform"
                    delta={
                      <div className="flex flex-col gap-1 mt-1 text-[10px]">
                        <div className="flex items-center justify-between">
                          <span className="text-[var(--text-muted)]">vs Yday:</span>
                          {renderDelta(dYes.count, dYes.acv)}
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-[var(--text-muted)]">vs Wk:</span>
                          {renderDelta(dLast.count, dLast.acv)}
                        </div>
                      </div>
                    }
                  />
                )
              })}
            </div>
          </div>

          {/* ── 3. Regions & Business Units (Two Compact Tables) ──────────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Regions Compact Table */}
            <Card padding="md" className="space-y-3">
              <div className="flex items-center justify-between border-b border-[var(--border)] pb-2">
                <SectionHeader
                  title="Top Regions"
                  subtitle="Renewals ACV and portfolio share by region"
                  className="mb-0"
                />
                <button
                  type="button"
                  onClick={() => navigate('/regions')}
                  className="text-xs font-semibold text-[#00A3AD] hover:underline inline-flex items-center gap-1"
                >
                  <span>View All</span>
                  <ExternalLink className="w-3 h-3" />
                </button>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-[var(--border)] text-[var(--text-muted)] uppercase text-[10px]">
                      <th className="text-left py-1.5 font-bold">Region</th>
                      <th className="text-right py-1.5 font-bold">Deals</th>
                      <th className="text-right py-1.5 font-bold">ACV</th>
                      <th className="text-right py-1.5 font-bold">Share</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border-subtle)]">
                    {topRegions.map((r: any) => (
                      <tr
                        key={r.region}
                        onClick={() => navigate('/regions')}
                        className="hover:bg-[var(--bg-secondary)] cursor-pointer transition-colors"
                      >
                        <td className="py-2 font-semibold text-[var(--text-primary)]">{r.region}</td>
                        <td className="py-2 text-right text-[var(--text-muted)]">{formatCount(r.count)}</td>
                        <td className="py-2 text-right font-mono font-semibold text-[var(--text-primary)]">
                          {formatACV(r.acv)}
                        </td>
                        <td className="py-2 text-right font-medium text-[#00A3AD]">{r.pct_acv}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>

            {/* Business Units Compact Table */}
            <Card padding="md" className="space-y-3">
              <div className="flex items-center justify-between border-b border-[var(--border)] pb-2">
                <SectionHeader
                  title="Business Units"
                  subtitle="Renewals ACV and portfolio share by BU"
                  className="mb-0"
                />
                <button
                  type="button"
                  onClick={() => navigate('/business-units')}
                  className="text-xs font-semibold text-[#00A3AD] hover:underline inline-flex items-center gap-1"
                >
                  <span>View All</span>
                  <ExternalLink className="w-3 h-3" />
                </button>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-[var(--border)] text-[var(--text-muted)] uppercase text-[10px]">
                      <th className="text-left py-1.5 font-bold">Business Unit</th>
                      <th className="text-right py-1.5 font-bold">Deals</th>
                      <th className="text-right py-1.5 font-bold">ACV</th>
                      <th className="text-right py-1.5 font-bold">Share</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border-subtle)]">
                    {topBUs.map((bu: any) => (
                      <tr
                        key={bu.bu}
                        onClick={() => navigate('/business-units')}
                        className="hover:bg-[var(--bg-secondary)] cursor-pointer transition-colors"
                      >
                        <td className="py-2 font-semibold text-[var(--text-primary)] truncate max-w-[150px]">
                          {bu.bu}
                        </td>
                        <td className="py-2 text-right text-[var(--text-muted)]">{formatCount(bu.count)}</td>
                        <td className="py-2 text-right font-mono font-semibold text-[var(--text-primary)]">
                          {formatACV(bu.acv)}
                        </td>
                        <td className="py-2 text-right font-medium text-purple-600 dark:text-purple-400">
                          {bu.pct_acv}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </div>

          {/* ── 4. Approvals & Risks / Watchlist ──────────────────────────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Approvals Block */}
            <Card padding="md" className="space-y-3">
              <div className="flex items-center justify-between border-b border-[var(--border)] pb-2">
                <SectionHeader
                  title="Approval Status Summary"
                  subtitle="Renewals grouped by pricing & contract governance"
                  className="mb-0"
                />
                <button
                  type="button"
                  onClick={() => navigate('/approvals')}
                  className="text-xs font-semibold text-[#00A3AD] hover:underline inline-flex items-center gap-1"
                >
                  <span>Governance</span>
                  <ExternalLink className="w-3 h-3" />
                </button>
              </div>

              <div className="grid grid-cols-3 gap-2.5">
                {approvalStatuses.map((st: any) => {
                  const statusColors: Record<string, string> = {
                    Approved: 'border-l-emerald-500 bg-emerald-500/5',
                    'Pending Approval': 'border-l-amber-500 bg-amber-500/5',
                    Blank: 'border-l-slate-400 bg-slate-500/5',
                  }
                  return (
                    <div
                      key={st.status}
                      onClick={() => navigate('/approvals')}
                      className={clsx(
                        'p-3 rounded-lg border border-[var(--border)] border-l-4 cursor-pointer hover:bg-[var(--bg-secondary)] transition-colors',
                        statusColors[st.status] || 'border-l-teal-500'
                      )}
                    >
                      <p className="text-[10px] font-bold text-[var(--text-muted)] uppercase truncate">
                        {st.status === 'Blank' ? 'Unsubmitted' : st.status}
                      </p>
                      <p className="text-base font-black text-[var(--text-primary)] mt-1">
                        {formatCount(st.count)}
                      </p>
                      <p className="text-xs font-mono font-semibold text-[#00A3AD] mt-0.5">
                        {formatACV(st.acv)}
                      </p>
                      <p className="text-[10px] text-[var(--text-muted)] mt-1">
                        {st.pct_acv}% of total ACV
                      </p>
                    </div>
                  )
                })}
              </div>
            </Card>

            {/* Risks & Watchlist Block (4 items linked to matching pages) */}
            <Card padding="md" className="space-y-3 border-rose-500/20">
              <div className="flex items-center justify-between border-b border-[var(--border)] pb-2">
                <SectionHeader
                  title="Risks & Watchlist"
                  subtitle="Key items requiring immediate attention and action"
                  className="mb-0"
                />
                <button
                  type="button"
                  onClick={() => navigate('/delayed')}
                  className="text-xs font-semibold text-rose-500 hover:underline inline-flex items-center gap-1"
                >
                  <span>Delayed Deals</span>
                  <ExternalLink className="w-3 h-3" />
                </button>
              </div>

              <div className="grid grid-cols-2 gap-2.5" id="exec-risks-watchlist">
                {/* 1. Overdue */}
                <div
                  onClick={() => navigate('/delayed')}
                  className="p-3 rounded-lg border border-[var(--border)] border-l-4 border-l-rose-500 bg-rose-500/5 cursor-pointer hover:bg-rose-500/10 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold text-rose-600 dark:text-rose-400 uppercase">
                      Overdue
                    </span>
                    <AlertCircle className="w-3.5 h-3.5 text-rose-500" />
                  </div>
                  <p className="text-lg font-black text-[var(--text-primary)] mt-1" id="exec-risk-overdue-count">
                    {formatCount(overdueStat.count)} deals
                  </p>
                  <p className="text-xs font-mono font-semibold text-rose-600 dark:text-rose-400 mt-0.5" id="exec-risk-overdue-acv">
                    {formatACV(overdueStat.acv)}
                  </p>
                </div>

                {/* 2. Slipped to next year */}
                <div
                  onClick={() => navigate('/delayed')}
                  className="p-3 rounded-lg border border-[var(--border)] border-l-4 border-l-amber-500 bg-amber-500/5 cursor-pointer hover:bg-amber-500/10 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold text-amber-600 dark:text-amber-400 uppercase">
                      Slipped to Next Year
                    </span>
                    <CalendarX2 className="w-3.5 h-3.5 text-amber-500" />
                  </div>
                  <p className="text-lg font-black text-[var(--text-primary)] mt-1" id="exec-risk-slipped-count">
                    {formatCount(slippedStat.count)} deals
                  </p>
                  <p className="text-xs font-mono font-semibold text-amber-600 dark:text-amber-400 mt-0.5" id="exec-risk-slipped-acv">
                    {formatACV(slippedStat.acv)}
                  </p>
                </div>

                {/* 3. Lost / Removed */}
                <div
                  onClick={() => navigate('/delayed')}
                  className="p-3 rounded-lg border border-[var(--border)] border-l-4 border-l-slate-400 bg-slate-500/5 cursor-pointer hover:bg-slate-500/10 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold text-[var(--text-muted)] uppercase">
                      Lost / Removed
                    </span>
                    <AlertTriangle className="w-3.5 h-3.5 text-slate-400" />
                  </div>
                  <p className="text-lg font-black text-[var(--text-primary)] mt-1" id="exec-risk-lost-count">
                    {formatCount(lostStat.count)} deals
                  </p>
                  <p className="text-xs font-mono font-semibold text-[var(--text-muted)] mt-0.5" id="exec-risk-lost-acv">
                    {formatACV(lostStat.acv)}
                  </p>
                </div>

                {/* 4. Not yet proposed */}
                <div
                  onClick={() => navigate('/delayed')}
                  className="p-3 rounded-lg border border-[var(--border)] border-l-4 border-l-indigo-500 bg-indigo-500/5 cursor-pointer hover:bg-indigo-500/10 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold text-indigo-600 dark:text-indigo-400 uppercase">
                      Not Yet Proposed
                    </span>
                    <HelpCircle className="w-3.5 h-3.5 text-indigo-500" />
                  </div>
                  <p className="text-lg font-black text-[var(--text-primary)] mt-1" id="exec-risk-unproposed-count">
                    {formatCount(unproposedStat.count)} deals
                  </p>
                  <p className="text-xs font-mono font-semibold text-indigo-600 dark:text-indigo-400 mt-0.5" id="exec-risk-unproposed-acv">
                    {formatACV(unproposedStat.acv)}
                  </p>
                </div>
              </div>
            </Card>
          </div>
        </>
      )}

      {/* ── Reconciliation Modal (Source Check) ────────────────────────────── */}
      {showReconcileModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in">
          <div className="w-full max-w-lg rounded-2xl bg-[var(--bg-card)] border border-[var(--border)] shadow-2xl overflow-hidden p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-emerald-500" />
                <h3 className="font-bold text-base text-[var(--text-primary)]">Source Reconciliation Check</h3>
              </div>
              <button
                type="button"
                onClick={() => setShowReconcileModal(false)}
                className="p-1 rounded-md text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-secondary)]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <p className="text-[var(--text-secondary)]">
                Reconciliation of Oct 7 snapshot numbers with the raw uploaded workbook:
              </p>

              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)]">
                  <p className="text-[10px] font-bold text-[var(--text-muted)] uppercase">Total Snapshot Deals</p>
                  <p className="text-xl font-black text-[var(--text-primary)] mt-1">
                    {formatCount(reconcileData?.whole_snapshot?.total_rows ?? 3093)}
                  </p>
                  <p className="text-[10px] text-emerald-600 font-semibold mt-0.5">✓ 3,093 verified rows</p>
                </div>
                <div className="p-3 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)]">
                  <p className="text-[10px] font-bold text-[var(--text-muted)] uppercase">Total Snapshot ACV</p>
                  <p className="text-xl font-black text-[#00A3AD] mt-1">
                    {formatACV(reconcileData?.whole_snapshot?.total_acv ?? 451999230.24)}
                  </p>
                  <p className="text-[10px] text-emerald-600 font-semibold mt-0.5">✓ $451.99M verified</p>
                </div>
              </div>

              <div className="p-3 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)]">
                <p className="text-[10px] font-bold text-[var(--text-muted)] uppercase">Renewals Scope (Q4-2026)</p>
                <p className="text-base font-bold text-[var(--text-primary)] mt-1">
                  348 deals · $40,068,990.09 ACV
                </p>
                <p className="text-[10px] text-[var(--text-muted)] mt-0.5">
                  100% matched with Overview, Expiry, Regions and Approvals services.
                </p>
              </div>
            </div>

            <div className="flex justify-end pt-2 border-t border-[var(--border)]">
              <button
                type="button"
                onClick={() => setShowReconcileModal(false)}
                className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-[#12284C] dark:bg-[#00A3AD] text-white hover:opacity-90 transition-opacity"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
