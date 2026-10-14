import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  RefreshCw, Upload, AlertTriangle, TrendingUp, TrendingDown,
  ChevronRight, X, CheckCircle2, ArrowRight, BarChart3, Users, Globe2,
} from 'lucide-react'
import { useAppStore } from '@/store/appStore'
import {
  getV2OverviewSummary,
  getV2OverviewMovements,
  getV2RegionalBreakdown,
  getV2OverviewDeals,
} from '@/api/client'
import { getForecastCategoryLabel, formatCurrency, formatNumber } from '@/utils/format'
import { formatDate } from '@/utils/format'
import { FORECAST_COLORS } from '@/design/tokens'
import OpportunityDrawer from '@/components/overview/OpportunityDrawer'
import EmptyState from '@/components/ui/EmptyState'
import DealListModal from '@/components/common/DealListModal'
import FilterBar from '@/components/common/FilterBar'

// Region display order (Sections 6 & 7)
const REGION_ORDER = [
  'North America', 'LATAM', 'Middle East and North Africa', 'APAC', 'Europe', 'Africa',
]

function acvM(v: number | null | undefined): string {
  if (v == null) return '\u2014'
  const abs = Math.abs(v)
  const sign = v < 0 ? '-' : ''
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(2)}M`
  if (abs >= 1_000)     return `${sign}$${(abs / 1_000).toFixed(1)}K`
  return `${sign}$${abs.toFixed(0)}`
}

function DeltaBadge({ val, label }: { val: number | null | undefined; label?: string }) {
  if (val == null) return null
  const up = val >= 0
  return (
    <span className={`inline-flex items-center gap-0.5 text-[10px] font-bold px-2 py-0.5 rounded-sm ${
      up ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
         : 'bg-red-500/10 text-red-700 dark:text-red-400'
    }`}>
      {up ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
      {up ? '+' : ''}{val}{label ? ` ${label}` : ''}
    </span>
  )
}

function AcvDelta({ val }: { val: number | null | undefined }) {
  if (val == null) return null
  const up = val >= 0
  return (
    <span className={`inline-flex items-center gap-0.5 text-[10px] font-bold px-2 py-0.5 rounded-sm ${
      up ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
         : 'bg-red-500/10 text-red-700 dark:text-red-400'
    }`}>
      {up ? '\u25b2' : '\u25bc'} {up ? '+' : ''}{acvM(val)}
    </span>
  )
}

function Pill({ children, color = 'teal' }: { children: React.ReactNode; color?: string }) {
  const cls: Record<string, string> = {
    teal: 'bg-teal-500/10 text-teal-700 dark:text-teal-300 border border-teal-500/20',
    violet: 'bg-violet-500/10 text-violet-700 dark:text-violet-300 border border-violet-500/20',
    amber: 'bg-amber-500/10 text-amber-700 dark:text-amber-300 border border-amber-500/20',
    slate: 'bg-slate-200/70 dark:bg-slate-700/40 text-slate-600 dark:text-slate-400 border border-slate-300/40 dark:border-slate-600/40',
  }
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-bold px-2.5 py-1 rounded-sm ${cls[color] ?? cls.teal}`}>
      {children}
    </span>
  )
}

function DealModal({ title, deals, onSelectOpp, onClose }: {
  title: string; deals: any[]; onSelectOpp: (id: string) => void; onClose: () => void
}) {
  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
        style={{ background: 'rgba(0,0,0,0.55)' }}
        onClick={onClose}
      >
        <motion.div
          initial={{ scale: 0.95, y: 20 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.95, y: 20 }}
          className="card w-full max-w-2xl max-h-[80vh] flex flex-col overflow-hidden"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border)]">
            <h3 className="font-bold text-sm">{title}</h3>
            <button onClick={onClose}><X className="w-4 h-4 text-[var(--text-muted)]" /></button>
          </div>
          <div className="overflow-y-auto flex-1">
            {deals.length === 0
              ? <p className="text-center text-sm text-[var(--text-muted)] py-8">No deals.</p>
              : (
                <table className="w-full text-xs">
                  <thead className="sticky top-0 bg-[var(--bg-secondary)]">
                    <tr>
                      <th className="text-left px-4 py-2.5 font-semibold text-[var(--text-muted)]">Opportunity</th>
                      <th className="text-left px-4 py-2.5 font-semibold text-[var(--text-muted)]">Region</th>
                      <th className="text-right px-4 py-2.5 font-semibold text-[var(--text-muted)]">ACV</th>
                      <th className="w-6" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border-subtle)]">
                    {deals.map((d: any, i: number) => (
                      <tr
                        key={d.opportunity_id_18 || i}
                        className="hover:bg-[var(--bg-secondary)] cursor-pointer transition-colors group"
                        onClick={() => d.opportunity_id_18 && onSelectOpp(d.opportunity_id_18)}
                      >
                        <td className="px-4 py-2.5 font-medium">{d.opportunity_name || d.opportunity_id_18}</td>
                        <td className="px-4 py-2.5 text-[var(--text-muted)]">{d.region || d.canonical_region || '\u2014'}</td>
                        <td className="px-4 py-2.5 text-right font-mono font-semibold">{acvM(d.acv ?? d.forecast_acv_amount)}</td>
                        <td className="pr-3 text-[var(--text-muted)] opacity-0 group-hover:opacity-100">
                          <ChevronRight className="w-3.5 h-3.5" />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
export default function Dashboard() {
  const { snapshots = [] } = useAppStore()
  const navigate = useNavigate()

  const [movCompare, setMovCompare] = useState<'yesterday' | 'last_week'>('yesterday')
  const [modal, setModal] = useState<{ title: string; deals: any[]; deltaGroups?: any } | null>(null)
  const [modalInitialFilters, setModalInitialFilters] = useState<any>(undefined)

  const openDealsQuery = async (
    title: string,
    params: { category?: string; region?: string; approval_status?: string; kind?: string; compare?: string },
    initialFilters?: any
  ) => {
    try {
      const res = await getV2OverviewDeals(params)
      setModalInitialFilters(initialFilters)
      setModal({
        title,
        deals: res.deals || [],
        deltaGroups: res.delta_groups,
      })
    } catch (err) {
      console.error('Failed to load deals', err)
    }
  }


  const [selectedOppId, setSelectedOppId] = useState<string | null>(null)

  const { globalFilters } = useAppStore()

  const { data: summary, isLoading: sumLoading, refetch: refetchSum } = useQuery({
    queryKey: ['v2-summary', globalFilters],
    queryFn: () => getV2OverviewSummary(globalFilters),
  })

  const { data: movYesterday, isLoading: movYLoading, refetch: refetchMovY } = useQuery({
    queryKey: ['v2-movements-yesterday', globalFilters],
    queryFn: () => getV2OverviewMovements('yesterday', globalFilters),
  })

  const { data: movLastWeek, isLoading: movLWLoading, refetch: refetchMovLW } = useQuery({
    queryKey: ['v2-movements-lastweek', globalFilters],
    queryFn: () => getV2OverviewMovements('last_week', globalFilters),
  })

  const movements = movCompare === 'yesterday' ? movYesterday : movLastWeek
  const movLoading = movCompare === 'yesterday' ? movYLoading : movLWLoading

  const { data: regional, isLoading: regLoading, refetch: refetchReg } = useQuery({
    queryKey: ['v2-regional', globalFilters],
    queryFn: () => getV2RegionalBreakdown(globalFilters),
  })

  const isLoading = sumLoading || movYLoading || movLWLoading || regLoading
  const refetchAll = () => { refetchSum(); refetchMovY(); refetchMovLW(); refetchReg() }


  if (snapshots.length === 0 && !isLoading) {
    return (
      <EmptyState
        title="No Snapshot Data Found"
        description="Please upload renewal workbooks to initialize the pipeline intelligence platform."
      />
    )
  }

  if (summary?.error || movements?.error || regional?.error) {
    return <div className="p-8 text-center text-rose-500 font-semibold bg-rose-50 border border-rose-200 rounded-xl m-6">{summary?.error || movements?.error || regional?.error}</div>
  }

  if (!isLoading && (!summary || !summary.total)) {
    return <EmptyState title="No data" description="Overview data is empty or malformed." />
  }

  const otherCount  = summary?.other_region_count ?? 0
  const cats        = summary?.categories ?? {}
  const standingSlip= summary?.slippage_to_2027 ?? { count: 0, acv: 0 }
  const total       = summary?.total ?? { count: 0, acv: 0 }

  const pos: any[]  = movements?.positive ?? []
  const neg: any[]  = movements?.negative ?? []
  const apv: any[]  = movements?.approval ?? []
  const movSlip     = movements?.slippage_to_2027 ?? { count: 0, acv: 0, deals: [] }
  const slipLater   = movements?.slipped_later_quarter ?? { count: 0, acv: 0, deals: [] }
  const slipEarlier = movements?.slipped_earlier ?? { count: 0, acv: 0, deals: [] }
  const compareDate = movements?.compare_date

  const posTotal = pos.reduce((s: number, r: any) => s + (r.acv ?? 0), 0)
  const negTotal = neg.reduce((s: number, r: any) => s + (r.acv ?? 0), 0)
  const apvTotal = apv.reduce((s: number, r: any) => s + (r.acv ?? 0), 0)

  const propConf   = regional?.proposal_confirmation ?? []
  const propTotals = regional?.proposal_confirmation_totals ?? {}
  const regTrend   = regional?.regional_trend ?? []
  const regTotals  = regional?.regional_trend_totals ?? {}

  const orderRegions = (rows: any[]) =>
    REGION_ORDER.map(r => rows.find((x: any) => x.region === r)).filter(Boolean)

  const propRows  = orderRegions(propConf)
  const trendRows = orderRegions(regTrend)

  const FC_COLS = ['Closed', 'Commit', 'Best Case', 'Pipeline', 'Blank'] as const

  return (
    <div className="space-y-6 pb-16 w-full">

      {/* ── Page header ─────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="font-extrabold text-2xl md:text-3xl tracking-tight text-[var(--text-primary)]">
              Renewals Overview
            </h1>
            <Pill color="teal">{summary?.data_slice || 'Overview'}</Pill>
            {summary?.source_checks && (
              <span
                className={`inline-flex items-center gap-1 text-xs font-bold px-2.5 py-1 rounded-sm border ${
                  summary.source_checks.badge === 'green'
                    ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30'
                    : summary.source_checks.badge === 'red'
                    ? 'bg-rose-500/10 text-rose-700 dark:text-rose-300 border-rose-500/30'
                    : 'bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/30'
                }`}
                title={`${summary.source_checks.passed}/${summary.source_checks.total} control checks matched Excel summary sheets`}
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                Source check: {summary.source_checks.badge === 'green' ? `yes (${summary.source_checks.passed} checks)` : `${summary.source_checks.failed} mismatches`}
              </span>
            )}
          </div>
          {summary?.snapshot_date && (
            <p className="text-xs text-[var(--text-muted)] mt-1">
              Data as of: <strong>{formatDate(summary.snapshot_date)}</strong>
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button" onClick={() => navigate('/data-uploads')}
            className="h-9 px-3 rounded-md border border-[var(--border)] bg-teal-500/10 hover:bg-teal-500/20 text-xs font-semibold text-teal-600 dark:text-teal-400 transition-colors inline-flex items-center gap-1.5 focus:outline-none"
            id="overview-upload-data-btn"
          >
            <Upload className="w-3.5 h-3.5" /> Upload Excel
          </button>
          <button
            type="button" onClick={refetchAll}
            className="h-9 px-3 rounded-md border border-[var(--border)] bg-[var(--bg-card)] hover:bg-[var(--bg-secondary)] text-xs font-semibold text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors inline-flex items-center gap-1.5 focus:outline-none"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-teal-500' : ''}`} /> Refresh
          </button>
        </div>
      </div>


      {/* ── SECTION 0 – Regional notice banner ──────────────────────────────── */}
      {otherCount > 0 && (
        <motion.div
          initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }}
          className="flex items-center gap-3 px-4 py-3 rounded-xl border border-amber-400/40 bg-amber-50 dark:bg-amber-900/20 text-amber-800 dark:text-amber-300 text-xs font-medium"
        >
          <AlertTriangle className="w-4 h-4 flex-shrink-0 text-amber-500" />
          <span>
            <strong>{otherCount} deal{otherCount !== 1 ? 's' : ''}</strong> cannot be assigned to a
            canonical region — check <em>revised_sub_region</em> values in source Excel.
          </span>
        </motion.div>
      )}

      {/* ── SECTION 1 – Total Renewal ACV Value ──────────────────────────── */}
      <div className="card p-6">
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div
            className="cursor-pointer group"
            onClick={() => openDealsQuery(`Total Renewal ${summary?.data_slice || ''} Deals (${total.count} Contracts · ${formatCurrency(total.acv)})`, {})}
            title={`Click to view all ${summary?.data_slice || 'renewal'} deals`}
          >
            <p className="text-xs font-semibold text-[var(--text-muted)] group-hover:text-[var(--brand-teal)] uppercase tracking-wider mb-2 transition-colors">
              Total Renewal {summary?.data_slice || 'ACV'} ACV Value
            </p>
            <div className="flex items-baseline gap-3">
              {sumLoading
                ? <div className="h-12 w-52 rounded-lg skeleton-shimmer" />
                : (
                  <span className="font-extrabold text-4xl md:text-5xl text-[var(--text-primary)] tabular-nums group-hover:underline">
                    ${(total.acv / 1_000_000).toFixed(2)}M
                  </span>
                )}
              <Pill color="teal"><Users className="w-3 h-3" />{total.count} Contracts</Pill>
            </div>
            <p className="text-[11px] text-[var(--text-muted)] mt-2">Fiscal Period = {summary?.data_slice || 'Selected Period'} · Click to view all {total.count} contracts</p>
          </div>
          <div className="flex gap-3 flex-wrap">
            {[
              { label: 'vs Yesterday', delta: total.delta_yesterday, kind: 'delta_yesterday' },
              { label: 'vs Last Week', delta: total.delta_lastweek, kind: 'delta_lastweek' },
            ].map(({ label, delta, kind }) => (
              <div
                key={label}
                className="card px-4 py-3 min-w-[145px] cursor-pointer hover:border-[var(--brand-teal)] transition-all"
                onClick={() => delta && openDealsQuery(`${label} Movement Deals (${delta.count} deals · ${acvM(delta.acv)})`, { kind })}
                title={`Click to view deals with changes ${label}`}
              >
                <p className="text-[11px] text-[var(--text-muted)] font-medium mb-2">{label}</p>
                {delta
                  ? <div className="flex flex-col gap-1"><DeltaBadge val={delta.count} label="deals" /><AcvDelta val={delta.acv} /></div>
                  : <span className="text-xs text-[var(--text-muted)]">\u2014</span>}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── SECTION 2 – Category cards in one row ──────────────────────── */}
      {(() => {
        const categoryCards = [
          { key: 'Closed', label: 'Closed', dataKey: 'Closed' },
          { key: 'Commit', label: 'Commit', dataKey: 'Commit' },
          { key: 'Best Case', label: 'Best Case', dataKey: 'Best Case' },
          { key: 'Pipeline', label: 'Pipeline', dataKey: 'Pipeline' },
          { key: 'Blank', label: 'Not yet proposed', dataKey: 'Blank' },
        ] as const

        return (
          <div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
              {categoryCards.map(({ key, label, dataKey }) => {
                const cat = cats[dataKey] ?? { count: 0, acv: 0, delta_yesterday: null, delta_lastweek: null }
                const color = FORECAST_COLORS[dataKey] || '#64748b'

                return (
                  <motion.div
                    key={key}
                    initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                    className="card p-5 flex flex-col justify-between gap-3 cursor-pointer hover:border-[var(--brand-teal)] transition-all"
                    style={{ borderTop: `3px solid ${color}` }}
                    onClick={() => openDealsQuery(`${label} Deals (${cat.count} deals · ${acvM(cat.acv)})`, { category: dataKey }, { forecast_category: dataKey })}
                    title={`Click to view ${label} deals`}
                  >
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider">{label}</span>
                        <Pill color="slate"><Users className="w-3 h-3" />{cat.count} deals</Pill>
                      </div>
                      {sumLoading
                        ? <div className="h-8 w-28 skeleton-shimmer rounded" />
                        : <span className="font-extrabold text-2xl tabular-nums block hover:underline" style={{ color }}>{acvM(cat.acv)}</span>}
                      
                      <hr className="border-[var(--border-subtle)]" />
                      
                      <div className="flex flex-col gap-1">
                        {[
                          { l: 'vs Yesterday', d: cat.delta_yesterday },
                          { l: 'vs Last Week', d: cat.delta_lastweek },
                        ].map(({ l, d }) => d ? (
                          <div key={l} className="flex items-center justify-between text-[11px]">
                            <span className="text-[var(--text-muted)]">{l}</span>
                            <div className="flex gap-1"><DeltaBadge val={d.count} /><AcvDelta val={d.acv} /></div>
                          </div>
                        ) : (
                          <div key={l} className="flex items-center justify-between text-[11px] text-[var(--text-muted)] opacity-60">
                            <span>{l}</span>
                            <span>—</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </motion.div>
                )
              })}
            </div>
          </div>
        )
      })()}

      {/* ── SECTION 3 – Slippage to Next Year (Movement-based) ─────────────── */}
      <div className="card p-6" style={{ borderLeft: '4px solid #F59E0B' }}>
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="w-2.5 h-2.5 rounded-full bg-amber-500 animate-pulse" />
              <p className="text-xs font-bold text-amber-600 dark:text-amber-400 uppercase tracking-wider">
                Slipped to Next Year (Movement-Based)
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-6 mt-3">
              {/* Yesterday comparison */}
              {(() => {
                const ySlip = movYesterday?.slippage_to_2027 ?? { count: 0, acv: 0, deals: [] }
                const yDate = movYesterday?.compare_date
                return (
                  <div
                    className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 cursor-pointer hover:border-amber-500/50 transition-all"
                    onClick={() => openDealsQuery(`Slipped to Next Year (vs Yesterday, ${yDate ? formatDate(yDate) : 'Oct 6'}) · ${ySlip.count} deals · ${acvM(ySlip.acv)}`, { kind: 'slipped', compare: 'yesterday' })}
                    title="Click to view deals slipped vs yesterday"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-[11px] font-semibold text-[var(--text-muted)]">
                        vs Yesterday {yDate && `(${formatDate(yDate)})`}
                      </span>
                      <Pill color="amber"><AlertTriangle className="w-3 h-3" />{ySlip.count} deals</Pill>
                    </div>
                    <div className="font-extrabold text-2xl text-amber-600 dark:text-amber-400 tabular-nums mt-1 hover:underline">
                      {acvM(ySlip.acv)}
                    </div>
                  </div>
                )
              })()}

              {/* Last week comparison */}
              {(() => {
                const lwSlip = movLastWeek?.slippage_to_2027 ?? { count: 0, acv: 0, deals: [] }
                const lwDate = movLastWeek?.compare_date
                return (
                  <div
                    className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 cursor-pointer hover:border-amber-500/50 transition-all"
                    onClick={() => openDealsQuery(`Slipped to Next Year (vs Last Week, ${lwDate ? formatDate(lwDate) : 'Sep 30'}) · ${lwSlip.count} deals · ${acvM(lwSlip.acv)}`, { kind: 'slipped', compare: 'last_week' })}
                    title="Click to view deals slipped vs last week"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-[11px] font-semibold text-[var(--text-muted)]">
                        vs Last Week {lwDate && `(${formatDate(lwDate)})`}
                      </span>
                      <Pill color="amber"><AlertTriangle className="w-3 h-3" />{lwSlip.count} deals</Pill>
                    </div>
                    <div className="font-extrabold text-2xl text-amber-600 dark:text-amber-400 tabular-nums mt-1 hover:underline">
                      {acvM(lwSlip.acv)}
                    </div>
                  </div>
                )
              })()}
            </div>

            <p className="text-[11px] text-[var(--text-muted)] mt-3">
              Contracts originally in Q4 that moved close date / fiscal period to FY2027.
              {standingSlip.count > 0 && ` Active snapshot standing slippage: ${standingSlip.count} deals.`}
            </p>
          </div>
        </div>
      </div>


      {/* ── SECTION 4 – Forecast Category & Approval Movement ───────────────── */}
      <div className="card p-6 space-y-5">
        {/* Block header */}
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3 flex-wrap">
            <h2 className="font-bold text-base text-[var(--text-primary)]">
              Forecast Category &amp; Approval Movement
            </h2>
            {cats['Closed'] != null && (
              <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold bg-emerald-500/10 border border-emerald-500/30 text-emerald-700 dark:text-emerald-400">
                <CheckCircle2 className="w-3.5 h-3.5" />
                {cats['Closed'].count} Closed &middot; {acvM(cats['Closed'].acv)}
              </span>
            )}
          </div>
          {/* Toggle */}
          <div className="flex items-center rounded-xl overflow-hidden border border-[var(--border)] text-xs font-semibold">
            {(['yesterday', 'last_week'] as const).map((v) => (
              <button
                key={v} type="button" onClick={() => setMovCompare(v)}
                className={`px-4 py-2 transition-colors ${
                  movCompare === v
                    ? 'bg-[var(--brand-teal)] text-white'
                    : 'bg-[var(--bg-secondary)] text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                }`}
              >
                {v === 'yesterday' ? 'vs Yesterday' : 'vs Last Week'}
              </button>
            ))}
          </div>
        </div>

        {compareDate && (
          <p className="text-[11px] text-[var(--text-muted)]">Comparing with {formatDate(compareDate)}</p>
        )}

        {/* Positive / Negative tables */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

          {/* GREEN – Positive */}
          <div className="rounded-xl border border-emerald-500/20 bg-emerald-50/40 dark:bg-emerald-900/10 overflow-hidden">
            <div className="px-4 py-3 bg-emerald-500/10 border-b border-emerald-500/20">
              <h3 className="text-xs font-bold text-emerald-700 dark:text-emerald-400 uppercase tracking-wider flex items-center gap-2">
                <TrendingUp className="w-4 h-4" /> Positive Movements
              </h3>
            </div>
            <table className="w-full text-xs">
              <thead>
                <tr className="text-[var(--text-muted)]">
                  <th className="text-left px-4 py-2.5 font-semibold">Movement</th>
                  <th className="text-right px-4 py-2.5 font-semibold">Count</th>
                  <th className="text-right px-4 py-2.5 font-semibold">ACV</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-emerald-500/10">
                {pos.reduce((s: number, r: any) => s + (r.count ?? 0), 0) === 0 && (
                  <tr><td colSpan={3} className="px-4 py-2.5 text-center text-[var(--text-muted)] italic">No upgrades since {compareDate ? compareDate.substring(5,10) : 'Oct 6'}</td></tr>
                )}
                {pos.map((row: any, i: number) => (
                  <tr
                    key={i}
                    className="hover:bg-emerald-500/10 cursor-pointer transition-colors"
                    onClick={() => row.deals?.length && setModal({ title: row.label ?? `${row.from_category} \u2192 ${row.to_category}`, deals: row.deals })}
                  >
                    <td className="px-4 py-2.5 font-medium flex items-center gap-1.5">
                      {row.label ? (
                        <span className="font-bold">{row.label}</span>
                      ) : (
                        <>
                          <span className="text-[var(--text-muted)]">{row.from_category}</span>
                          <ArrowRight className="w-3 h-3 text-emerald-500 flex-shrink-0" />
                          <span className="font-bold">{row.to_category}</span>
                        </>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono font-bold text-emerald-700 dark:text-emerald-400">{row.count}</td>
                    <td className="px-4 py-2.5 text-right font-mono">{acvM(row.acv)}</td>
                  </tr>
                ))}
                <tr className="bg-emerald-500/10 border-t-2 border-emerald-500/30 font-bold">
                  <td className="px-4 py-2.5 text-emerald-700 dark:text-emerald-400">Total</td>
                  <td className="px-4 py-2.5 text-right font-mono text-emerald-700 dark:text-emerald-400">
                    {pos.reduce((s: number, r: any) => s + (r.count ?? 0), 0)}
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono text-emerald-700 dark:text-emerald-400">{acvM(posTotal)}</td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* RED – Negative */}
          <div className="rounded-xl border border-red-500/20 bg-red-50/40 dark:bg-red-900/10 overflow-hidden">
            <div className="px-4 py-3 bg-red-500/10 border-b border-red-500/20">
              <h3 className="text-xs font-bold text-red-700 dark:text-red-400 uppercase tracking-wider flex items-center gap-2">
                <TrendingDown className="w-4 h-4" /> Negative Movements
              </h3>
            </div>
            <table className="w-full text-xs">
              <thead>
                <tr className="text-[var(--text-muted)]">
                  <th className="text-left px-4 py-2.5 font-semibold">Movement</th>
                  <th className="text-right px-4 py-2.5 font-semibold">Count</th>
                  <th className="text-right px-4 py-2.5 font-semibold">ACV</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-red-500/10">
                {neg.reduce((s: number, r: any) => s + (r.count ?? 0), 0) === 0 && (
                  <tr><td colSpan={3} className="px-4 py-2.5 text-center text-[var(--text-muted)] italic">No downgrades since {compareDate ? compareDate.substring(5,10) : 'Oct 6'}</td></tr>
                )}
                {neg.map((row: any, i: number) => {
                  return (
                    <tr
                      key={i}
                      className="hover:bg-red-500/10 cursor-pointer transition-colors"
                      onClick={() => row.deals?.length && setModal({ title: row.label ?? `${row.from_category} \u2192 ${row.to_category}`, deals: row.deals })}
                    >
                      <td className="px-4 py-2.5 font-medium">
                        {row.label ? (
                          <span className="flex items-center gap-1.5">
                            {row.label.toLowerCase().includes('slip') && <AlertTriangle className="w-3 h-3 text-amber-500 flex-shrink-0" />}
                            <span className={row.label.toLowerCase().includes('slip') ? "font-bold text-amber-700 dark:text-amber-400" : "font-bold"}>{row.label}</span>
                          </span>
                        ) : (
                          <span className="flex items-center gap-1.5">
                            <span className="text-[var(--text-muted)]">{row.from_category}</span>
                            <ArrowRight className="w-3 h-3 text-red-500 flex-shrink-0" />
                            <span className="font-bold">{row.to_category}</span>
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-right font-mono font-bold text-red-700 dark:text-red-400">{row.count}</td>
                      <td className="px-4 py-2.5 text-right font-mono">{acvM(row.acv)}</td>
                    </tr>
                  )
                })}
                <tr className="bg-red-500/10 border-t-2 border-red-500/30 font-bold">
                  <td className="px-4 py-2.5 text-red-700 dark:text-red-400">Total</td>
                  <td className="px-4 py-2.5 text-right font-mono text-red-700 dark:text-red-400">
                    {neg.reduce((s: number, r: any) => s + (r.count ?? 0), 0)}
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono text-red-700 dark:text-red-400">{acvM(negTotal)}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* Approval Movement Table */}
        {apv.length > 0 && (
          <div className="mt-2">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wider">
                Approval Movement Table
              </h3>
              <Pill color="violet">
                <Users className="w-3 h-3" />
                {apv.reduce((s: number, r: any) => s + (r.count ?? 0), 0)} Status Changes ({acvM(apvTotal)})
              </Pill>
            </div>
            <div className="rounded-xl border border-[var(--border)] overflow-hidden">
              <table className="w-full text-xs">
                <thead className="bg-[var(--bg-secondary)]">
                  <tr>
                    <th className="text-left px-4 py-2.5 font-semibold text-[var(--text-muted)]">From Approval Status</th>
                    <th className="text-left px-4 py-2.5 font-semibold text-[var(--text-muted)]">To Approval Status</th>
                    <th className="text-right px-4 py-2.5 font-semibold text-[var(--text-muted)]">Opportunity Count</th>
                    <th className="text-right px-4 py-2.5 font-semibold text-[var(--text-muted)]">ACV Value ($M)</th>
                    <th className="px-4 py-2.5 font-semibold text-[var(--text-muted)]">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-subtle)]">
                  {apv.map((row: any, i: number) => (
                    <tr key={i} className="hover:bg-[var(--bg-secondary)] transition-colors">
                      <td className="px-4 py-2.5 text-[var(--text-secondary)]">{row.from_status}</td>
                      <td className="px-4 py-2.5 font-semibold">{row.to_status}</td>
                      <td className="px-4 py-2.5 text-right font-mono font-bold">{row.count}</td>
                      <td className="px-4 py-2.5 text-right font-mono">{acvM(row.acv)}</td>
                      <td className="px-4 py-2.5">
                        <button
                          type="button"
                          onClick={() => row.deals?.length && setModal({ title: `${row.from_status} \u2192 ${row.to_status}`, deals: row.deals })}
                          className="text-[10px] font-bold text-[var(--brand-teal)] hover:underline"
                        >
                          View Deals
                        </button>
                      </td>
                    </tr>
                  ))}
                  <tr className="bg-[var(--bg-secondary)] font-bold border-t-2 border-[var(--border)]">
                    <td className="px-4 py-2.5 text-[var(--text-muted)]" colSpan={2}>Total Approval Movements</td>
                    <td className="px-4 py-2.5 text-right font-mono">{apv.reduce((s: number, r: any) => s + (r.count ?? 0), 0)}</td>
                    <td className="px-4 py-2.5 text-right font-mono">{acvM(apvTotal)}</td>
                    <td />
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* ── SECTION 6 – Proposal Confirmation ───────────────────────────────── */}
      <div className="card p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-bold text-base text-[var(--text-primary)]">Proposal Confirmation</h2>
            <p className="text-[11px] text-[var(--text-muted)] mt-0.5">Unit: Opportunity Count (#)</p>
          </div>
          <Globe2 className="w-5 h-5 text-[var(--text-muted)]" />
        </div>
        <div className="overflow-x-auto rounded-xl border border-[var(--border)]">
          <table className="w-full text-xs">
            <thead className="bg-[var(--bg-secondary)]">
              <tr>
                <th className="text-left px-4 py-3 font-semibold text-[var(--text-muted)]">Region</th>
                <th className="text-right px-4 py-3 font-semibold text-[var(--text-muted)]">Total Opportunity Approval in the System</th>
                <th className="text-right px-4 py-3 font-semibold text-emerald-600 dark:text-emerald-400">Approved</th>
                <th className="text-right px-4 py-3 font-semibold text-amber-600 dark:text-amber-400">Pending Approval</th>
                <th className="text-right px-4 py-3 font-semibold text-[var(--text-muted)]">Blanks (Yet to be proposed)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-subtle)]">
              {propRows.map((row: any) => (
                <tr key={row.region} className="hover:bg-[var(--bg-secondary)] transition-colors">
                  <td className="px-4 py-3 font-medium cursor-pointer hover:underline" onClick={() => openDealsQuery(`${row.region} Deals`, { region: row.region }, { sub_region: row.region })}>{row.region}</td>
                  <td className="px-4 py-3 text-right font-mono font-bold cursor-pointer hover:underline text-[var(--brand-teal)]" onClick={() => openDealsQuery(`${row.region} · All Approvals`, { region: row.region }, { sub_region: row.region })}>
                    {(row.approved_count ?? 0) + (row.pending_count ?? 0) + (row.blank_count ?? 0)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-emerald-700 dark:text-emerald-400 font-bold cursor-pointer hover:underline" onClick={() => openDealsQuery(`${row.region} · Approved Deals`, { region: row.region, approval_status: 'Approved' }, { sub_region: row.region, approval_status: 'Approved' })}>{row.approved_count ?? 0}</td>
                  <td className="px-4 py-3 text-right font-mono text-amber-700 dark:text-amber-400 font-bold cursor-pointer hover:underline" onClick={() => openDealsQuery(`${row.region} · Pending Approval Deals`, { region: row.region, approval_status: 'Pending Approval' }, { sub_region: row.region, approval_status: 'Pending Approval' })}>{row.pending_count ?? 0}</td>
                  <td className="px-4 py-3 text-right font-mono text-[var(--text-secondary)] cursor-pointer hover:underline" onClick={() => openDealsQuery(`${row.region} · Not submitted (Blank)`, { region: row.region, approval_status: 'Blank' }, { sub_region: row.region, approval_status: 'Blank' })}>{row.blank_count ?? 0}</td>
                </tr>
              ))}
              <tr className="bg-[var(--bg-secondary)] font-bold border-t-2 border-[var(--border)]">
                <td className="px-4 py-3">Total</td>
                <td className="px-4 py-3 text-right font-mono cursor-pointer hover:underline text-[var(--brand-teal)]" onClick={() => openDealsQuery(`Total Opportunity Approvals (${(propTotals.approved_count ?? 0) + (propTotals.pending_count ?? 0) + (propTotals.blank_count ?? 0)} deals)`, {})}>
                  {(propTotals.approved_count ?? 0) + (propTotals.pending_count ?? 0) + (propTotals.blank_count ?? 0)}
                </td>
                <td className="px-4 py-3 text-right font-mono text-emerald-700 dark:text-emerald-400 cursor-pointer hover:underline" onClick={() => openDealsQuery(`All Approved Deals (${propTotals.approved_count ?? 0} deals)`, { approval_status: 'Approved' }, { approval_status: 'Approved' })}>{propTotals.approved_count ?? 0}</td>
                <td className="px-4 py-3 text-right font-mono text-amber-700 dark:text-amber-400 cursor-pointer hover:underline" onClick={() => openDealsQuery(`All Pending Approval Deals (${propTotals.pending_count ?? 0} deals)`, { approval_status: 'Pending Approval' }, { approval_status: 'Pending Approval' })}>{propTotals.pending_count ?? 0}</td>
                <td className="px-4 py-3 text-right font-mono cursor-pointer hover:underline" onClick={() => openDealsQuery(`All Not submitted (Blank) Deals (${propTotals.blank_count ?? 0} deals)`, { approval_status: 'Blank' }, { approval_status: 'Blank' })}>{propTotals.blank_count ?? 0}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* ── SECTION 7 – Regional Trend ───────────────────────────────────────── */}
      <div className="card p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-bold text-base text-[var(--text-primary)]">Regional Trend</h2>
            <p className="text-[11px] text-[var(--text-muted)] mt-0.5">ACV values in $M</p>
          </div>
          <BarChart3 className="w-5 h-5 text-[var(--text-muted)]" />
        </div>
        <div className="overflow-x-auto rounded-xl border border-[var(--border)]">
          <table className="w-full text-xs">
            <thead className="bg-[var(--bg-secondary)]">
              <tr>
                <th className="text-left px-4 py-3 font-semibold text-[var(--text-muted)]">Region</th>
                <th className="text-right px-4 py-3 font-semibold text-[var(--text-muted)]">Total ACV Value</th>
                {FC_COLS.map(fc => (
                  <th key={fc} className="text-right px-4 py-3 font-semibold" style={{ color: FORECAST_COLORS[fc] }}>{getForecastCategoryLabel(fc)}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-subtle)]">
              {trendRows.map((row: any) => (
                <tr key={row.region} className="hover:bg-[var(--bg-secondary)] transition-colors">
                  <td className="px-4 py-3 font-medium cursor-pointer hover:underline" onClick={() => openDealsQuery(`${row.region} Deals (${acvM(row.total_acv)})`, { region: row.region }, { sub_region: row.region })}>{row.region}</td>
                  <td className="px-4 py-3 text-right font-mono font-bold cursor-pointer hover:underline text-[var(--brand-teal)]" onClick={() => openDealsQuery(`${row.region} Total (${acvM(row.total_acv)})`, { region: row.region }, { sub_region: row.region })}>{acvM(row.total_acv)}</td>
                  {FC_COLS.map(fc => {
                    const k = fc.toLowerCase().replace(' ', '_') + '_acv'
                    const val = row[k] ?? 0
                    return (
                      <td
                        key={fc}
                        className="px-4 py-3 text-right font-mono cursor-pointer hover:underline"
                        style={{ color: FORECAST_COLORS[fc] }}
                        onClick={() => openDealsQuery(`${row.region} · ${getForecastCategoryLabel(fc)} (${acvM(val)})`, { region: row.region, category: fc }, { sub_region: row.region, forecast_category: fc })}
                      >
                        {acvM(val)}
                      </td>
                    )
                  })}
                </tr>
              ))}
              <tr className="bg-[var(--bg-secondary)] font-bold border-t-2 border-[var(--border)]">
                <td className="px-4 py-3">Total</td>
                <td className="px-4 py-3 text-right font-mono cursor-pointer hover:underline text-[var(--brand-teal)]" onClick={() => openDealsQuery(`Total Renewal ACV (${acvM(regTotals.total_acv)})`, {})}>{acvM(regTotals.total_acv)}</td>
                {FC_COLS.map(fc => {
                  const k = fc.toLowerCase().replace(' ', '_') + '_acv'
                  const val = regTotals[k] ?? 0
                  return (
                    <td
                      key={fc}
                      className="px-4 py-3 text-right font-mono cursor-pointer hover:underline"
                      style={{ color: FORECAST_COLORS[fc] }}
                      onClick={() => openDealsQuery(`Total · ${getForecastCategoryLabel(fc)} (${acvM(val)})`, { category: fc }, { forecast_category: fc })}
                    >
                      {acvM(val)}
                    </td>
                  )
                })}
              </tr>
            </tbody>
          </table>
        </div>
        {regional?.total_acv_check_passes != null && (
          <div className={`flex items-center gap-2 text-xs font-semibold px-3 py-2 rounded-lg ${
            regional.total_acv_check_passes
              ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
              : 'bg-red-500/10 text-red-700 dark:text-red-400'
          }`}>
            <CheckCircle2 className="w-3.5 h-3.5" />
            {regional.total_acv_check_passes
              ? `Regional Trend Total matches Overview Total Renewal ${summary?.data_slice || ''} ACV \u2713`
              : '\u26a0 Regional Trend Total does NOT match — check for unmapped regions'}
          </div>
        )}
      </div>

      {/* Deal modal */}
      {modal && (
        <DealListModal
          title={modal.title}
          deals={modal.deals}
          initialFilters={modalInitialFilters}
          deltaGroups={modal.deltaGroups}
          onSelectOpp={(id) => { setModal(null); setSelectedOppId(id) }}
          onClose={() => { setModal(null); setModalInitialFilters(undefined) }}
        />
      )}


      {/* Opportunity drawer */}
      <OpportunityDrawer oppId={selectedOppId} onClose={() => setSelectedOppId(null)} />
    </div>
  )
}
