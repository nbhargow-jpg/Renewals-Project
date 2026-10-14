import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Building2,
  AlertOctagon,
  Search
} from 'lucide-react'
import { useAppStore } from '@/store/appStore'
import api from '@/api/client'
import { formatACV, formatCount, formatCurrency, getForecastCategoryLabel } from '@/utils/format'
import Card from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import DealListModal from '@/components/common/DealListModal'
import OpportunityDrawer from '@/components/overview/OpportunityDrawer'
import CompactGrid from '@/components/common/CompactGrid'
import MetricToggle from '@/components/common/MetricToggle'
import FilterBar from '@/components/common/FilterBar'
import SummaryLine from '@/components/common/SummaryLine'
import ErrorBoundary from '@/components/common/ErrorBoundary'

type MetricMode = 'Amount' | 'Count' | 'Both'

function BusinessUnitsContent() {
  const { activeSnapshotId } = useAppStore()
  const metricMode = (useAppStore((s: any) => s.metricMode) || 'Amount') as MetricMode
  const setMetricMode = useAppStore((s: any) => s.setMetricMode)

  const [compare, setCompare] = useState<'yesterday' | 'last_week'>('yesterday')
  const [heatMode, setHeatMode] = useState<'Value' | 'Yesterday' | 'LastWeek'>('Value')
  
  // Drill-through
  const [modalOpen, setModalOpen] = useState(false)
  const [modalTitle, setModalTitle] = useState('')
  const [modalFilters, setModalFilters] = useState<any>({})
  
  const [selectedOppId, setSelectedOppId] = useState<string | null>(null)
  const [topSearch, setTopSearch] = useState('')
  const [topBuFilter, setTopBuFilter] = useState('All')

  // Fetch Summary
  const { data: summary, isLoading, error } = useQuery({
    queryKey: ['v2-bu-summary', activeSnapshotId, compare],
    queryFn: async () => {
      const res = await api.get('/v2/business-units/summary', {
        params: { as_of: activeSnapshotId ?? undefined, compare }
      })
      return res.data
    },
  })

  // Fetch Deals for Modal
  const { data: dealsData } = useQuery({
    queryKey: ['v2-bu-deals', activeSnapshotId, modalFilters],
    queryFn: async () => {
      const res = await api.get('/v2/business-units/deals', {
        params: { as_of: activeSnapshotId ?? undefined, ...modalFilters }
      })
      return res.data
    },
    enabled: modalOpen
  })

  // Fetch Top Opportunities
  const { data: topOppsData } = useQuery({
    queryKey: ['v2-bu-top', activeSnapshotId, topBuFilter],
    queryFn: async () => {
      const res = await api.get('/v2/business-units/top-opportunities', {
        params: { as_of: activeSnapshotId ?? undefined, bu: topBuFilter === 'All' ? undefined : topBuFilter }
      })
      return res.data
    }
  })

  if (error || (summary && summary.error)) {
    return (
      <Card className="p-6">
        <div className="flex items-center gap-3 text-red-500 mb-2">
          <AlertOctagon className="w-6 h-6" />
          <h2 className="text-lg font-bold">Error loading Business Units</h2>
        </div>
        <p className="text-sm text-[var(--text-muted)]">{error?.toString() || summary?.error}</p>
      </Card>
    )
  }

  if (isLoading || !summary) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  const { data_slice, data_slice_key, total, rows, totals, categories } = summary
  
  // Helpers
  const deltaKey = compare === 'yesterday' ? 'delta_yesterday' : 'delta_lastweek'
  const prevDate = compare === 'yesterday' ? rows[0]?.yesterday_date : rows[0]?.lastweek_date

  // Handle drill through
  const handleCellClick = (rowId: string | null, colId: string | null, title: string) => {
    setModalTitle(title)
    setModalFilters({
      bu: rowId === 'Total' ? undefined : (rowId ?? undefined),
      category: colId === 'Total' ? undefined : (colId ?? undefined),
      as_of: activeSnapshotId ?? undefined,
    })
    setModalOpen(true)
  }
  
  const handleDonutClick = (bu: string) => {
    handleCellClick(bu, null, bu === 'Total' ? `All Business Units` : `${bu} · All Categories`)
  }

  const handleBarClick = (bu: string, fc: string) => {
    handleCellClick(bu, fc, `${bu} · ${fc}`)
  }

  // Formatting for deltas
  const fmtD = (val: number, isCount: boolean) => {
    if (!val) return '0'
    const sign = val > 0 ? '+' : ''
    if (isCount) return `${sign}${val}`
    const abs = Math.abs(val)
    if (abs >= 1_000_000) return `${sign}$${(val / 1_000_000).toFixed(2)}M`
    if (abs >= 1_000) return `${sign}$${(val / 1_000).toFixed(1)}K`
    return `${sign}$${val.toFixed(0)}`
  }
  const deltaSpan = (d: any, isCount: boolean) => {
    if (!d) return null
    const v = isCount ? d.count : d.acv
    if (!v) return null
    const color = v > 0 ? 'text-emerald-500' : 'text-red-500'
    return <span className={color}>{fmtD(v, isCount)}</span>
  }

  // Stat chips
  const largestBu = rows.length > 0 ? rows[0] : null
  const numBUs = rows.length
  const totalCommit = totals.categories['Commit']?.acv || 0
  const commitCov = total.acv > 0 ? ((totalCommit / total.acv) * 100).toFixed(1) : '0.0'
  const largestBuPct = total.acv > 0 && largestBu ? ((largestBu.acv / total.acv) * 100).toFixed(1) : '0.0'

  // Insight line logic
  const sortedByAcvDelta = [...rows].sort((a, b) => (b[deltaKey]?.acv || 0) - (a[deltaKey]?.acv || 0))
  const topMover = sortedByAcvDelta[0]
  const insightLines = []
  if (topMover && (topMover[deltaKey]?.acv || 0) > 0) {
    const dtStr = new Date(prevDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    insightLines.push(`${topMover.bu} ${fmtD(topMover[deltaKey]?.count, true)} deals / ${fmtD(topMover[deltaKey]?.acv, false)} vs ${dtStr}`)
    insightLines.push(`Largest mover vs ${dtStr}: ${topMover.bu}`)
  } else {
    insightLines.push(`No positive movements vs ${compare.replace('_', ' ')}`)
  }

  // Build grid data
  const gridRows = rows.map((r: any) => ({
    id: r.bu,
    label: r.bu,
    cells: r.cells,
    total: { count: r.count, acv: r.acv }
  }))
  const gridDeltas = {
    category: totals.categories,
    grand: totals.grand,
    rows: Object.fromEntries(rows.map((r: any) => [r.bu, {
      delta_yesterday: r.delta_yesterday,
      delta_lastweek: r.delta_lastweek,
      cells: Object.fromEntries(categories.map((c: string) => [c, {
        delta_yesterday: r.cells[c]?.delta_yesterday,
        delta_lastweek: r.cells[c]?.delta_lastweek,
      }]))
    }]))
  }

  // Filter deals by search
  const deals = topOppsData?.deals || []
  const filteredDeals = deals.filter((d: any) => 
    d.opportunity_name?.toLowerCase().includes(topSearch.toLowerCase()) ||
    d.account_name?.toLowerCase().includes(topSearch.toLowerCase())
  )

  // Chart Colors
  const catColors: Record<string, string> = {
    'Closed': '#10b981',
    'Commit': '#0284c7',
    'Best Case': '#8b5cf6',
    'Pipeline': '#f59e0b',
    'Blank': '#64748b'
  }
  const donutColors = ['#3b82f6', '#8b5cf6', '#ec4899', '#f43f5e', '#f97316', '#eab308', '#22c55e', '#14b8a6', '#0ea5e9', '#6366f1']

  // Forecast categories in required order: Closed, Commit, Best Case, Pipeline, Blank
  const displayCategories = ['Closed', 'Commit', 'Best Case', 'Pipeline', 'Blank']

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">
              <Building2 className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-2xl font-black tracking-tight text-[var(--text-primary)]">
                Business Units
              </h1>
              <div className="flex items-center gap-2 mt-1">
                <span className="px-2 py-0.5 rounded-md bg-[var(--bg-muted)] text-[var(--text-secondary)] text-xs font-medium">
                  {data_slice}
                </span>
                <span className="text-xs text-[var(--text-muted)]">
                  Compare:
                </span>
                <div className="flex bg-[var(--bg-muted)] rounded-md p-0.5">
                  <button
                    onClick={() => setCompare('yesterday')}
                    className={`px-2 py-0.5 text-[10px] rounded-sm font-medium transition-colors ${compare === 'yesterday' ? 'bg-[var(--bg-card)] text-[var(--text-primary)] shadow-sm' : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'}`}
                  >
                    vs Yesterday
                  </button>
                  <button
                    onClick={() => setCompare('last_week')}
                    className={`px-2 py-0.5 text-[10px] rounded-sm font-medium transition-colors ${compare === 'last_week' ? 'bg-[var(--bg-card)] text-[var(--text-primary)] shadow-sm' : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'}`}
                  >
                    vs Last Week
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <MetricToggle />
        </div>
      </div>


      {/* KPI Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Card className="p-3.5 border-l-4 border-l-indigo-500">
          <div className="text-[11px] font-semibold text-[var(--text-muted)] uppercase tracking-wider">Total Value</div>
          <div className="text-xl font-black text-[var(--text-primary)] mt-1">{formatACV(total.acv)}</div>
          <div className="text-xs text-[var(--text-secondary)] mt-1 font-medium">{formatCount(total.count)} deals</div>
          <div className="flex gap-2 text-[10px] mt-2">
            <span>Yday: {deltaSpan(totals.grand.delta_yesterday, false)}</span>
            <span>Wk: {deltaSpan(totals.grand.delta_lastweek, false)}</span>
          </div>
        </Card>
        <Card className="p-3.5 border-l-4 border-l-violet-500">
          <div className="text-[11px] font-semibold text-[var(--text-muted)] uppercase tracking-wider">Business Units</div>
          <div className="text-xl font-black text-[var(--text-primary)] mt-1">{numBUs}</div>
          <div className="text-xs text-[var(--text-secondary)] mt-1 font-medium">active in {data_slice}</div>
        </Card>
        <Card className="p-3.5 border-l-4 border-l-pink-500">
          <div className="text-[11px] font-semibold text-[var(--text-muted)] uppercase tracking-wider">Largest BU</div>
          <div className="text-xl font-black text-[var(--text-primary)] mt-1 truncate">{largestBu?.bu || '-'}</div>
          <div className="text-xs text-[var(--text-secondary)] mt-1 font-medium">{largestBuPct}% of total ACV</div>
          <div className="flex gap-2 text-[10px] mt-2">
            <span>Yday: {deltaSpan(largestBu?.delta_yesterday, false)}</span>
            <span>Wk: {deltaSpan(largestBu?.delta_lastweek, false)}</span>
          </div>
        </Card>
        <Card className="p-3.5 border-l-4 border-l-sky-500">
          <div className="text-[11px] font-semibold text-[var(--text-muted)] uppercase tracking-wider">Commit Coverage</div>
          <div className="text-xl font-black text-[var(--text-primary)] mt-1">{commitCov}%</div>
          <div className="text-xs text-[var(--text-secondary)] mt-1 font-medium">Commit / Total ACV</div>
          <div className="flex gap-2 text-[10px] mt-2">
            <span>Yday: {deltaSpan(totals.categories['Commit']?.delta_yesterday, false)}</span>
            <span>Wk: {deltaSpan(totals.categories['Commit']?.delta_lastweek, false)}</span>
          </div>
        </Card>
      </div>

      {/* Replaced Chart Row: Compact Heatmap Grid + Ranked Bar of BU Share of Total ACV */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-5">
        {/* Compact Heatmap Grid (BU x Forecast Category) */}
        <div className="xl:col-span-8 flex flex-col">
          <CompactGrid
            title="BU x Forecast Category Heatmap"
            rowLabelName="Business Unit"
            columns={displayCategories}
            rows={gridRows}
            totals={{ category: totals.categories, grand: totals.grand }}
            deltas={gridDeltas}
            metricMode={metricMode}
            onCellClick={handleCellClick}
            compareDate={prevDate}
            yesterdayDate={summary.yesterday_date}
            lastweekDate={summary.lastweek_date}
            heatMode={heatMode}
          />
        </div>

        {/* Ranked Bar: BU Share of Total ACV (Single colour, sorted, full untruncated labels, multi-value BUs retained) */}
        <Card className="xl:col-span-4 p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-[var(--text-primary)]">
                BU Share of Total ACV
              </h3>
              <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">
                {formatACV(total.acv)}
              </span>
            </div>

            <div className="space-y-3">
              {[...rows]
                .sort((a: any, b: any) => (b.acv || 0) - (a.acv || 0))
                .map((r: any) => {
                  const pct = total.acv > 0 ? (r.acv / total.acv) * 100 : 0
                  return (
                    <div
                      key={r.bu}
                      className="group cursor-pointer hover:bg-[var(--bg-muted)] p-2 rounded-lg transition-colors"
                      onClick={() => handleDonutClick(r.bu)}
                      title={`${r.bu}: ${formatCurrency(r.acv)} (${pct.toFixed(1)}% of total ACV) · Click to view deals`}
                    >
                      <div className="flex justify-between items-baseline text-xs mb-1">
                        <span className="font-semibold text-[var(--text-primary)] group-hover:text-indigo-600 transition-colors">
                          {r.bu}
                        </span>
                        <div className="flex items-center gap-2 font-mono">
                          <span className="font-bold text-[var(--text-primary)]">{pct.toFixed(1)}%</span>
                          <span className="text-[11px] text-[var(--text-muted)]">({formatACV(r.acv)})</span>
                        </div>
                      </div>
                      <div className="w-full h-2.5 bg-[var(--bg-muted)] rounded-full overflow-hidden border border-[var(--border)]">
                        <div
                          className="h-full bg-indigo-500 group-hover:bg-indigo-600 transition-all rounded-full"
                          style={{ width: `${Math.max(pct, 1)}%` }}
                        />
                      </div>
                    </div>
                  )
                })}
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-[var(--border)] text-[11px] text-[var(--text-muted)] flex items-center justify-between">
            <span>Ranked by ACV share · Multi-value BUs distinct</span>
            <span className="text-indigo-600 dark:text-indigo-400 font-semibold">Every row clickable →</span>
          </div>
        </Card>
      </div>

      {/* Matrix */}
      <Card className="p-1">
        <div className="p-3 flex justify-between items-center border-b border-[var(--border)]">
          <h2 className="text-sm font-bold text-[var(--text-primary)]">Forecast Category by Business Unit</h2>
          <div className="flex items-center gap-2">
            <span className="text-xs text-[var(--text-muted)] font-medium">Heat by:</span>
            <div className="flex bg-[var(--bg-muted)] rounded-md p-0.5">
              {(['Value', 'Yesterday', 'LastWeek'] as const).map(m => (
                <button
                  key={m}
                  onClick={() => setHeatMode(m)}
                  className={`px-2 py-0.5 text-[10px] rounded-sm font-medium transition-colors ${heatMode === m ? 'bg-[var(--bg-card)] text-[var(--text-primary)] shadow-sm' : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'}`}
                >
                  {m === 'Value' ? 'Value' : `vs ${m}`}
                </button>
              ))}
            </div>
          </div>
        </div>
        <div className="overflow-x-auto">
          <CompactGrid
            title="Business Units"
            rowLabelName="Business Unit"
            columns={displayCategories}
            rows={gridRows}
            totals={{ category: totals.categories, grand: totals.grand }}
            deltas={gridDeltas}
            metricMode={metricMode}
            onCellClick={handleCellClick}
            compareDate={prevDate}
            yesterdayDate={summary.yesterday_date}
            lastweekDate={summary.lastweek_date}
            heatMode={heatMode}
          />
        </div>
        <div className="px-4 py-2 border-t border-[var(--border)]">
          {insightLines.map((l, i) => (
            <SummaryLine key={i} primaryText={l} />
          ))}
        </div>
      </Card>

      {/* Top Opportunities */}
      <Card className="p-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-4 gap-3">
          <h2 className="text-sm font-bold text-[var(--text-primary)]">Top Opportunities</h2>
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-[var(--text-muted)] absolute left-2.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search..."
                value={topSearch}
                onChange={e => setTopSearch(e.target.value)}
                className="pl-8 pr-3 py-1.5 text-xs bg-[var(--bg-muted)] border-none rounded-md text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:ring-1 focus:ring-indigo-500 w-48"
              />
            </div>
          </div>
        </div>
        <div className="flex gap-2 overflow-x-auto pb-3 mb-2 scrollbar-thin">
          <button
            onClick={() => setTopBuFilter('All')}
            className={`px-3 py-1 text-[11px] font-medium rounded-sm whitespace-nowrap transition-colors border ${topBuFilter === 'All' ? 'bg-indigo-500/10 text-indigo-600 border-indigo-500/20' : 'bg-[var(--bg-muted)] text-[var(--text-secondary)] border-transparent hover:bg-[var(--bg-card)]'}`}
          >
            All Units
          </button>
          {rows.map((r: any) => (
            <button
              key={r.bu}
              onClick={() => setTopBuFilter(r.bu)}
              className={`px-3 py-1 text-[11px] font-medium rounded-sm whitespace-nowrap transition-colors border ${topBuFilter === r.bu ? 'bg-indigo-500/10 text-indigo-600 border-indigo-500/20' : 'bg-[var(--bg-muted)] text-[var(--text-secondary)] border-transparent hover:bg-[var(--bg-card)]'}`}
            >
              {r.bu}
            </button>
          ))}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs whitespace-nowrap">
            <thead>
              <tr className="border-b border-[var(--border)] text-[var(--text-muted)]">
                <th className="py-2 px-3 font-medium">Opportunity</th>
                <th className="py-2 px-3 font-medium">Account</th>
                <th className="py-2 px-3 font-medium text-right">ACV</th>
                <th className="py-2 px-3 font-medium">Category</th>
                <th className="py-2 px-3 font-medium">Close Date</th>
              </tr>
            </thead>
            <tbody>
              {filteredDeals.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-[var(--text-muted)]">No opportunities found</td>
                </tr>
              ) : (
                filteredDeals.map((d: any) => (
                  <tr 
                    key={d.opportunity_id_18} 
                    className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--bg-muted)] cursor-pointer transition-colors"
                    onClick={() => setSelectedOppId(d.opportunity_id_18)}
                  >
                    <td className="py-2 px-3 font-medium text-[var(--text-primary)] truncate max-w-[200px]" title={d.opportunity_name}>
                      {d.opportunity_name}
                    </td>
                    <td className="py-2 px-3 text-[var(--text-secondary)] truncate max-w-[150px]">{d.account_name}</td>
                    <td className="py-2 px-3 text-right font-medium text-[var(--text-primary)]">{formatACV(d.forecast_acv_amount)}</td>
                    <td className="py-2 px-3">
                      <span className="px-2 py-0.5 rounded-sm text-[10px] font-medium" style={{ backgroundColor: `${catColors[d.forecast_category] || '#ccc'}20`, color: catColors[d.forecast_category] || '#ccc' }}>
                        {d.forecast_category}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-[var(--text-muted)]">
                      {d.close_date ? new Date(d.close_date).toLocaleDateString() : '-'}
                    </td>
                  </tr>
                ))
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
            business_unit_primary: modalFilters.bu,
            forecast_category: modalFilters.category
          }}
          onSelectOpp={setSelectedOppId}
          onClose={() => setModalOpen(false)}
        />
      )}

      <OpportunityDrawer
        oppId={selectedOppId}
        onClose={() => setSelectedOppId(null)}
      />
    </div>
  )
}

export default function BusinessUnits() {
  return (
    <ErrorBoundary>
      <BusinessUnitsContent />
    </ErrorBoundary>
  )
}
