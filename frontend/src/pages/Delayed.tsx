import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  AlertCircle,
  Clock,
  CalendarX2,
  ArrowRight,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  AlertTriangle,
} from 'lucide-react'
import { useAppStore } from '@/store/appStore'
import api from '@/api/client'
import { formatACV, formatCount } from '@/utils/format'
import Card from '@/components/ui/Card'
import SectionHeader from '@/components/ui/SectionHeader'
import { Skeleton } from '@/components/ui/Skeleton'
import DealListModal from '@/components/common/DealListModal'
import OpportunityDrawer from '@/components/overview/OpportunityDrawer'
import CompactGrid from '@/components/common/CompactGrid'
import MetricToggle from '@/components/common/MetricToggle'
import ErrorBoundary from '@/components/common/ErrorBoundary'
import { format, parseISO } from 'date-fns'
import clsx from 'clsx'

const cn = (...classes: (string | undefined | null | false)[]) => classes.filter(Boolean).join(' ')
type MetricMode = 'Amount' | 'Count' | 'Both'

function DelayedContent() {
  const { activeSnapshotId, globalFilters } = useAppStore()
  const metricMode = (useAppStore((s: any) => s.metricMode) || 'Amount') as MetricMode

  const [compare, setCompare] = useState<'yesterday' | 'last_week'>('yesterday')
  const [heatMode, setHeatMode] = useState<'Value' | 'Yesterday' | 'LastWeek'>('Value')
  const [modalOpen, setModalOpen] = useState(false)
  const [modalTitle, setModalTitle] = useState('')
  const [modalFilters, setModalFilters] = useState<any>({})
  const [selectedOppId, setSelectedOppId] = useState<string | null>(null)

  const { data: summary, isLoading, error } = useQuery({
    queryKey: ['v2-delayed-summary', activeSnapshotId, compare, globalFilters],
    queryFn: async () => {
      const res = await api.get('/v2/delayed/summary', {
        params: { as_of: activeSnapshotId ?? undefined, compare, ...globalFilters },
      })
      return res.data
    },
  })

  const { data: dealsData } = useQuery({
    queryKey: ['v2-delayed-deals', activeSnapshotId, compare, globalFilters, modalFilters],
    queryFn: async () => {
      const res = await api.get('/v2/delayed/deals', {
        params: { as_of: activeSnapshotId ?? undefined, compare, ...globalFilters, ...modalFilters },
      })
      return res.data
    },
    enabled: modalOpen,
  })

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (error || summary?.error) {
    return (
      <div>
        <Card className="p-8 text-center text-red-500">
          <AlertCircle className="w-12 h-12 mx-auto mb-4" />
          <h2 className="text-lg font-semibold mb-2">Could not load Delayed data</h2>
          <p className="text-sm opacity-80">{summary?.error || 'Server error'}</p>
        </Card>
      </div>
    )
  }

  const handleDrill = (title: string, filters: any = {}) => {
    setModalTitle(title)
    setModalFilters({ ...filters, compare, as_of: activeSnapshotId ?? undefined })
    setModalOpen(true)
  }

  const yDateStr = summary.yesterday_date ? format(parseISO(summary.yesterday_date), 'dd MMM') : 'Yday'
  const wDateStr = summary.lastweek_date ? format(parseISO(summary.lastweek_date), 'dd MMM') : 'Wk'

  const DualDeltaDisplay = ({ data }: { data: any }) => {
    if (!data) return null
    const yCount = data.delayed_vs_yesterday?.count ?? 0
    const yAcv = data.delayed_vs_yesterday?.acv ?? 0
    const wCount = data.delayed_vs_lastweek?.count ?? 0
    const wAcv = data.delayed_vs_lastweek?.acv ?? 0

    const renderDelta = (count: number, acv: number, label: string) => {
      const isPos = acv > 0 || count > 0 // in delays, increase is bad
      const isNeg = acv < 0 || count < 0
      const isZero = count === 0 && acv === 0

      const Icon = isPos ? ArrowUpRight : isNeg ? ArrowDownRight : Minus
      const val = isZero
        ? 'No change'
        : metricMode === 'Amount'
        ? formatACV(acv)
        : metricMode === 'Count'
        ? formatCount(count)
        : `${formatCount(count)} / ${formatACV(acv)}`

      // Soft muted background with dark text of the same hue
      const chipClasses = isZero
        ? 'bg-slate-100 text-slate-700 dark:bg-slate-800/60 dark:text-[#8A9BB5]'
        : isPos
        ? 'bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-400'
        : 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400'

      return (
        <span
          className={cn(
            'inline-flex items-center text-[10px] font-medium px-2 py-0.5 rounded-sm select-none tabular-nums transition-colors',
            chipClasses
          )}
          title={label}
        >
          <Icon className="w-3 h-3 mr-0.5" />
          <span className="opacity-70 mr-1">{label}</span>
          <span>{val}</span>
        </span>
      )
    }

    return (
      <div className="flex items-center gap-1.5 flex-wrap">
        {renderDelta(yCount, yAcv, `vs ${yDateStr}`)}
        {renderDelta(wCount, wAcv, `vs ${wDateStr}`)}
      </div>
    )
  }

  // 4px left accent bar + 32px rounded-lg tinted icon tile
  const DelayedKpiCard = ({ title, data, icon: Icon, accent, kind }: any) => {
    const accentBorder = {
      amber: 'border-l-amber-500',
      rose: 'border-l-rose-500',
      slate: 'border-l-slate-400',
      teal: 'border-l-[#00A3AD]',
    }[accent as 'amber' | 'rose' | 'slate' | 'teal'] || 'border-l-[#00A3AD]'

    const iconTileClass = {
      amber: 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
      rose: 'bg-rose-500/10 text-rose-600 dark:text-rose-400',
      slate: 'bg-slate-500/10 text-slate-600 dark:text-slate-300',
      teal: 'bg-[#00A3AD]/10 text-[#00A3AD]',
    }[accent as 'amber' | 'rose' | 'slate' | 'teal'] || 'bg-[#00A3AD]/10 text-[#00A3AD]'

    return (
      <div
        className={cn(
          'rounded-xl bg-[var(--bg-card)] border border-[var(--border)] border-l-4 shadow-[var(--card-shadow)]',
          accentBorder,
          'p-5 flex flex-col justify-between h-full items-stretch transition-colors select-none cursor-pointer hover:bg-[var(--bg-secondary)]/50'
        )}
        onClick={() => handleDrill(title, { kind })}
      >
        <div>
          <div className="flex items-center justify-between gap-2 mb-3">
            <span className="text-xs font-medium text-[var(--text-muted)] truncate">
              {title}
            </span>
            <div className={cn('w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0', iconTileClass)}>
              <Icon className="w-4 h-4" strokeWidth={1.75} />
            </div>
          </div>
          <div className="space-y-0.5 mb-3">
            {(metricMode === 'Count' || metricMode === 'Both') && (
              <div className="text-2xl font-semibold tracking-tight text-[var(--text-primary)] tabular-nums">
                {formatCount(data?.count || 0)}
              </div>
            )}
            {(metricMode === 'Amount' || metricMode === 'Both') && (
              <div className="text-sm font-medium text-[var(--text-muted)] tabular-nums">
                {formatACV(data?.acv || 0)}
              </div>
            )}
          </div>
        </div>
        <div className="pt-2 border-t border-[var(--border-subtle)]">
          <DualDeltaDisplay data={data} />
        </div>
      </div>
    )
  }

  const buildGrid = (byField: 'by_region' | 'by_bu', clickKey: 'region' | 'bu') => {
    const categories = ['Closed', 'Commit', 'Best Case', 'Pipeline', 'Blank']
    const totals = { category: {} as any, grand: { count: 0, acv: 0 } }
    const gridDeltas: any = {}

    summary[byField]?.forEach((row: any) => {
      totals.grand.count += row.count
      totals.grand.acv += row.acv
      categories.forEach((cat) => {
        if (!totals.category[cat]) totals.category[cat] = { count: 0, acv: 0 }
        totals.category[cat].count += row.categories?.[cat]?.count || 0
        totals.category[cat].acv += row.categories?.[cat]?.acv || 0
      })
    })

    const rows = (summary[byField] || []).map((row: any) => {
      const cells = categories.map((cat) => ({
        count: row.categories?.[cat]?.count || 0,
        acv: row.categories?.[cat]?.acv || 0,
      }))

      const isY = compare === 'yesterday'
      categories.forEach((cat) => {
        const catData = row.categories?.[cat]
        const dCount = isY ? (catData?.delayed_vs_yesterday?.count ?? 0) : (catData?.delayed_vs_lastweek?.count ?? 0)
        const dAcv = isY ? (catData?.delayed_vs_yesterday?.acv ?? 0) : (catData?.delayed_vs_lastweek?.acv ?? 0)
        gridDeltas[`${row.label}-${cat}`] = { count: dCount, acv: dAcv }
      })

      const rdCount = isY ? (row.delayed_vs_yesterday?.count ?? 0) : (row.delayed_vs_lastweek?.count ?? 0)
      const rdAcv = isY ? (row.delayed_vs_yesterday?.acv ?? 0) : (row.delayed_vs_lastweek?.acv ?? 0)
      gridDeltas[`${row.label}-total`] = { count: rdCount, acv: rdAcv }

      return {
        label: row.label,
        cells,
        totals: { count: row.count, acv: row.acv },
      }
    })

    categories.forEach((cat) => {
      let dCount = 0
      let dAcv = 0
      summary[byField]?.forEach((row: any) => {
        const catData = row.categories?.[cat]
        dCount += compare === 'yesterday' ? (catData?.delayed_vs_yesterday?.count ?? 0) : (catData?.delayed_vs_lastweek?.count ?? 0)
        dAcv += compare === 'yesterday' ? (catData?.delayed_vs_yesterday?.acv ?? 0) : (catData?.delayed_vs_lastweek?.acv ?? 0)
      })
      gridDeltas[`total-${cat}`] = { count: dCount, acv: dAcv }
    })

    const dTotalCount = compare === 'yesterday' ? (summary.total?.delayed_vs_yesterday?.count ?? 0) : (summary.total?.delayed_vs_lastweek?.count ?? 0)
    const dTotalAcv = compare === 'yesterday' ? (summary.total?.delayed_vs_yesterday?.acv ?? 0) : (summary.total?.delayed_vs_lastweek?.acv ?? 0)
    gridDeltas['grand-total'] = { count: dTotalCount, acv: dTotalAcv }

    const handleCellClick = (rowId: string | null, colId: string | null, title: string) => {
      const filters: any = { kind: 'all' }
      if (rowId && rowId !== 'Total') filters[clickKey] = rowId
      if (colId && colId !== 'Total') filters.category = colId
      handleDrill(title || `Delayed Deals`, filters)
    }

    return { categories, rows, totals, gridDeltas, handleCellClick }
  }

  const regionGrid = buildGrid('by_region', 'region')
  const buGrid = buildGrid('by_bu', 'bu')

  return (
    <div className="space-y-6">
      {/* Aligned Section Header with integrated controls (no second filter bar) */}
      <SectionHeader
        title="Delayed Renewals"
        subtitle={`Renewals in ${summary.data_slice} that have slipped, pushed out, or are overdue.`}
        actions={
          <div className="flex flex-wrap items-center gap-3">
            <MetricToggle />
            <div className="h-9 inline-flex items-center rounded-md border border-[var(--border)] bg-[var(--bg-secondary)] p-0.5 text-xs font-medium">
              <button
                type="button"
                onClick={() => setCompare('yesterday')}
                className={clsx(
                  'h-full px-3 rounded-sm transition-colors flex items-center justify-center',
                  compare === 'yesterday'
                    ? 'bg-[var(--bg-card)] text-[var(--text-primary)] shadow-sm'
                    : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                )}
              >
                vs Yesterday
              </button>
              <button
                type="button"
                onClick={() => setCompare('last_week')}
                className={clsx(
                  'h-full px-3 rounded-sm transition-colors flex items-center justify-center',
                  compare === 'last_week'
                    ? 'bg-[var(--bg-card)] text-[var(--text-primary)] shadow-sm'
                    : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                )}
              >
                vs Last Week
              </button>
            </div>
          </div>
        }
      />

      {/* 5 KPI Cards in one row: grid-cols-5 at ≥1280px, 3 at ≥768px, 1 on mobile */}
      <div className="grid grid-cols-1 md:grid-cols-3 xl:grid-cols-5 gap-4 items-stretch">
        <DelayedKpiCard
          title="Total Delayed"
          data={summary.total}
          icon={Clock}
          accent="teal"
          kind="all"
        />
        <DelayedKpiCard
          title="Overdue"
          data={summary.overdue}
          icon={AlertCircle}
          accent="rose"
          kind="overdue"
        />
        <DelayedKpiCard
          title="Slipped to Next Year"
          data={summary.slipped}
          icon={CalendarX2}
          accent="amber"
          kind="slipped"
        />
        <DelayedKpiCard
          title="Later Close Date"
          data={summary.later_close}
          icon={ArrowRight}
          accent="amber"
          kind="later_close"
        />
        <DelayedKpiCard
          title="Lost / Removed"
          data={summary.lost}
          icon={AlertTriangle}
          accent="slate"
          kind="lost"
        />
      </div>

      {/* Grid Breakdowns */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card className="flex flex-col h-[400px]" padding="none">
          <div className="overflow-x-auto h-full p-4">
            <CompactGrid
              title="By Region"
              rowLabelName="Region"
              columns={regionGrid.categories}
              rows={regionGrid.rows}
              totals={regionGrid.totals}
              deltas={regionGrid.gridDeltas}
              metricMode={metricMode}
              onCellClick={regionGrid.handleCellClick}
              compareDate={compare === 'yesterday' ? summary.yesterday_date : summary.lastweek_date}
              yesterdayDate={summary.yesterday_date}
              lastweekDate={summary.lastweek_date}
              heatMode={heatMode}
            />
          </div>
        </Card>

        <Card className="flex flex-col h-[400px]" padding="none">
          <div className="overflow-x-auto h-full p-4">
            <CompactGrid
              title="By Business Unit"
              rowLabelName="Business Unit"
              columns={buGrid.categories}
              rows={buGrid.rows}
              totals={buGrid.totals}
              deltas={buGrid.gridDeltas}
              metricMode={metricMode}
              onCellClick={buGrid.handleCellClick}
              compareDate={compare === 'yesterday' ? summary.yesterday_date : summary.lastweek_date}
              yesterdayDate={summary.yesterday_date}
              lastweekDate={summary.lastweek_date}
              heatMode={heatMode}
            />
          </div>
        </Card>
      </div>

      {/* Top Delayed Deals Table: 44px rows, px-4 py-3 padding, hairline divider, right-aligned numbers */}
      <Card padding="none">
        <div className="p-4 border-b border-[var(--border)]">
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">Top Delayed Deals</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="table-enterprise text-xs">
            <thead>
              <tr>
                <th className="text-left">Opportunity</th>
                <th className="text-left">Region</th>
                <th className="text-left">Reason</th>
                <th className="text-right">Push Out (Days)</th>
                <th className="text-right">ACV</th>
              </tr>
            </thead>
            <tbody>
              {summary.top_deals?.map((deal: any) => (
                <tr
                  key={deal.opportunity_id_18}
                  className="hover:bg-[var(--bg-secondary)]/60 cursor-pointer transition-colors"
                  onClick={() => setSelectedOppId(deal.opportunity_id_18)}
                >
                  <td className="font-medium text-[var(--brand-teal)] truncate max-w-xs">
                    {deal.opportunity_name}
                  </td>
                  <td className="text-[var(--text-secondary)]">{deal.region}</td>
                  <td>
                    <span
                      className={cn(
                        'px-2 py-0.5 rounded-sm text-[10px] font-medium border',
                        deal.reason === 'Overdue'
                          ? 'bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-400 border-rose-200 dark:border-rose-900/30'
                          : deal.reason === 'Slipped quarter'
                          ? 'bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400 border-amber-200 dark:border-amber-900/30'
                          : deal.reason === 'Lost/removed'
                          ? 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border-slate-200 dark:border-slate-700'
                          : 'bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400 border-amber-200 dark:border-amber-900/30'
                      )}
                    >
                      {deal.reason}
                    </span>
                  </td>
                  <td className="text-right text-[var(--text-muted)] tabular-nums">
                    {deal.push_out_days > 0 ? `+${deal.push_out_days}` : '-'}
                  </td>
                  <td className="text-right font-medium text-[var(--text-primary)] tabular-nums">
                    {formatACV(deal.forecast_acv_amount)}
                  </td>
                </tr>
              ))}
              {(!summary.top_deals || summary.top_deals.length === 0) && (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-[var(--text-muted)]">
                    No delayed deals found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {modalOpen && (
        <DealListModal
          title={modalTitle}
          deals={dealsData?.deals || []}
          initialFilters={{
            sub_region: modalFilters.region,
            forecast_category: modalFilters.category,
            approval_status: modalFilters.status,
            business_unit_primary: modalFilters.bu,
          }}
          onSelectOpp={setSelectedOppId}
          onClose={() => setModalOpen(false)}
        />
      )}

      <OpportunityDrawer oppId={selectedOppId} onClose={() => setSelectedOppId(null)} />
    </div>
  )
}

export default function Delayed() {
  return (
    <ErrorBoundary>
      <DelayedContent />
    </ErrorBoundary>
  )
}
