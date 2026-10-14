import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Globe2,
  AlertOctagon,
  Search,
  ArrowUpRight,
  ArrowDownRight,
  Minus
} from 'lucide-react'
import { useAppStore } from '@/store/appStore'
import api from '@/api/client'
import { formatACV, formatCount } from '@/utils/format'
import Card from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import DealListModal from '@/components/common/DealListModal'
import OpportunityDrawer from '@/components/overview/OpportunityDrawer'
import CompactGrid from '@/components/common/CompactGrid'
import MetricToggle from '@/components/common/MetricToggle'
import FilterBar from '@/components/common/FilterBar'
import SummaryLine from '@/components/common/SummaryLine'
import ErrorBoundary from '@/components/common/ErrorBoundary'

const cn = (...classes: (string | undefined | null | false)[]) => classes.filter(Boolean).join(' ')

type MetricMode = 'Amount' | 'Count' | 'Both'

const ALL_FC = ['Closed', 'Commit', 'Best Case', 'Pipeline', 'Blank']
const FUNNEL_STAGES = ['Approved', 'Pending Approval', 'Blank']

function RegionsContent() {
  const { activeSnapshotId } = useAppStore()
  const metricMode = (useAppStore((s: any) => s.metricMode) || 'Amount') as MetricMode
  const setMetricMode = useAppStore((s: any) => s.setMetricMode)

  const [compare, setCompare] = useState<'yesterday' | 'last_week'>('yesterday')
  const [heatMode, setHeatMode] = useState<'Value' | 'Yesterday' | 'LastWeek'>('Value')
  const [selectedRegion, setSelectedRegion] = useState<string>('All')
  
  // Drill-through
  const [modalOpen, setModalOpen] = useState(false)
  const [modalTitle, setModalTitle] = useState('')
  const [modalFilters, setModalFilters] = useState<any>({})
  
  const [selectedOppId, setSelectedOppId] = useState<string | null>(null)
  const [topSearch, setTopSearch] = useState('')
  const [moveCompare, setMoveCompare] = useState<'yesterday' | 'last_week'>('yesterday')

  // Fetch Summary
  const { data: summary, isLoading, error } = useQuery({
    queryKey: ['v2-regions-summary', activeSnapshotId, compare],
    queryFn: async () => {
      const res = await api.get('/v2/regions/summary', {
        params: { as_of: activeSnapshotId ?? undefined, compare }
      })
      return res.data
    },
  })

  // Fetch Selected Region details if not "All"
  const { data: regionDetail } = useQuery({
    queryKey: ['v2-regions-detail', activeSnapshotId, selectedRegion],
    queryFn: async () => {
      const res = await api.get(`/v2/regions/${selectedRegion}/summary`, {
        params: { as_of: activeSnapshotId ?? undefined }
      })
      return res.data
    },
    enabled: selectedRegion !== 'All'
  })

  // Fetch Movements for selected region
  const { data: movementsData } = useQuery({
    queryKey: ['v2-regions-movements', activeSnapshotId, selectedRegion, moveCompare],
    queryFn: async () => {
      const res = await api.get(`/v2/regions/${selectedRegion}/movements`, {
        params: { as_of: activeSnapshotId ?? undefined, compare: moveCompare }
      })
      return res.data
    },
    enabled: selectedRegion !== 'All'
  })

  // Fetch Top Opps for selected region
  const { data: topOppsData } = useQuery({
    queryKey: ['v2-regions-top', activeSnapshotId, selectedRegion],
    queryFn: async () => {
      const res = await api.get(`/v2/regions/${selectedRegion}/top-opportunities`, {
        params: { as_of: activeSnapshotId ?? undefined }
      })
      return res.data
    },
    enabled: selectedRegion !== 'All'
  })

  // Fetch Deals for Modal
  const { data: dealsData } = useQuery({
    queryKey: ['v2-regions-deals', activeSnapshotId, modalFilters],
    queryFn: async () => {
      const res = await api.get('/v2/regions/deals', {
        params: { as_of: activeSnapshotId ?? undefined, ...modalFilters }
      })
      return res.data
    },
    enabled: modalOpen
  })

  if (error || (summary && summary.error)) {
    return (
      <Card className="p-6">
        <div className="flex items-center gap-3 text-red-500 mb-2">
          <AlertOctagon className="w-5 h-5" />
          <h2 className="text-lg font-semibold">Failed to load Regions</h2>
        </div>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          {error ? error.message : (summary?.error || "Unknown error")}
        </p>
      </Card>
    )
  }

  if (isLoading || !summary) {
    return (
      <div className="space-y-6 animate-pulse">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  const { data_slice, yesterday_date, lastweek_date, regions, unmapped } = summary

  const handleDrill = (title: string, filters: any) => {
    setModalTitle(title)
    setModalFilters(filters)
    setModalOpen(true)
  }

  const renderDelta = (countDelta: number, acvDelta: number, compareStr: string) => {
    const val = metricMode === 'Count' ? countDelta : acvDelta
    if (val === 0) return <span className="text-gray-400 text-xs">No change vs {compareStr}</span>
    
    const isPos = val > 0
    const color = isPos ? 'text-green-500' : 'text-red-500'
    const Icon = isPos ? ArrowUpRight : ArrowDownRight
    
    let text = ''
    if (metricMode === 'Amount') {
      text = (isPos ? '+' : '') + formatACV(acvDelta)
    } else if (metricMode === 'Count') {
      text = (isPos ? '+' : '') + formatCount(countDelta)
    } else {
      text = `${isPos ? '+' : ''}${formatCount(countDelta)} · ${isPos ? '+' : ''}${formatACV(acvDelta)}`
    }
    
    return (
      <div className={`flex items-center gap-1 text-xs font-medium ${color}`}>
        <Icon className="w-3 h-3" />
        <span>{text} vs {compareStr}</span>
      </div>
    )
  }

  const formatUI = (dstr: string | null, fb: string) => dstr ? new Date(dstr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : fb
  const yDayStr = formatUI(yesterday_date, 'yesterday')
  const lwStr = formatUI(lastweek_date, 'last week')

  const tileOrder = ["North America", "LATAM", "Middle East and North Africa", "APAC", "Europe", "Africa", "Other"]
  
  // Generate Insight Lines
  const getInsightLines = () => {
    if (!summary || !summary.regions || summary.regions.length === 0) return []
    const lines = []
    
    // Sort regions by delta for current compare mode
    const deltaKey = compare === 'yesterday' ? 'delta_yesterday' : 'delta_lastweek'
    const sorted = [...summary.regions].filter(r => r.region !== 'Other').sort((a, b) => {
      const aVal = metricMode === 'Count' ? a[deltaKey].count : a[deltaKey].acv
      const bVal = metricMode === 'Count' ? b[deltaKey].count : b[deltaKey].acv
      return bVal - aVal
    })
    
    if (sorted.length > 0) {
      const best = sorted[0]
      const bestVal = metricMode === 'Count' ? best[deltaKey].count : best[deltaKey].acv
      if (bestVal > 0) {
        const valStr = metricMode === 'Amount' ? '+' + formatACV(bestVal) : metricMode === 'Count' ? '+' + formatCount(bestVal) : `+${formatCount(best[deltaKey].count)} · +${formatACV(best[deltaKey].acv)}`
        lines.push(`${best.region} ${valStr} vs ${compare === 'yesterday' ? yDayStr : lwStr}, the largest regional gain`)
      }
    }
    return lines
  }
  
  const insightLines = getInsightLines()

  return (
    <div className="space-y-6 pb-20">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-500/20 text-blue-500 rounded-lg">
            <Globe2 className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Regions</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {data_slice} • 
              <span className="ml-1 px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-xs font-medium">YDay: {yDayStr}</span>
              <span className="ml-1 px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-xs font-medium">Wk: {lwStr}</span>
            </p>
          </div>
        </div>
        <MetricToggle />
      </div>


      {unmapped?.count > 0 && (
        <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-4 flex items-center justify-between">
          <div className="flex items-center gap-3 text-amber-700 dark:text-amber-400">
            <AlertOctagon className="w-5 h-5" />
            <span className="text-sm font-medium">
              {unmapped.count} deals have an unmapped region: {unmapped.values.join(', ')}
            </span>
          </div>
          <button 
            onClick={() => handleDrill('Unmapped Region Deals', { region: 'Other' })}
            className="text-sm font-medium text-amber-600 dark:text-amber-500 hover:underline"
          >
            View deals →
          </button>
        </div>
      )}

      {/* Tiles */}
      <div className="flex flex-wrap gap-4">
        <button
          onClick={() => setSelectedRegion('All')}
          className={cn(
            "flex-1 min-w-[140px] text-left p-4 rounded-xl border transition-colors",
            selectedRegion === 'All'
              ? "bg-blue-50 dark:bg-blue-900/20 border-blue-500"
              : "bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 hover:border-blue-300"
          )}
        >
          <div className="text-sm font-medium text-gray-500 mb-1">All Regions</div>
          <div 
            className="text-xl font-bold text-gray-900 dark:text-white cursor-pointer hover:text-blue-500 transition-colors"
            onClick={(e) => {
              e.stopPropagation()
              handleDrill(`All Regions (${data_slice})`, {})
            }}
          >
            {metricMode === 'Count' ? formatCount(summary.total.count) : 
             metricMode === 'Amount' ? formatACV(summary.total.acv) : 
             `${formatCount(summary.total.count)} · ${formatACV(summary.total.acv)}`}
          </div>
          <div className="mt-2 space-y-1">
            {renderDelta(summary.total.delta_yesterday.count, summary.total.delta_yesterday.acv, yDayStr)}
            {renderDelta(summary.total.delta_lastweek.count, summary.total.delta_lastweek.acv, lwStr)}
          </div>
        </button>

        {tileOrder.map(rname => {
          const reg = regions.find((r: any) => r.region === rname)
          if (!reg) return null
          
          return (
            <button
              key={rname}
              onClick={() => setSelectedRegion(rname)}
              className={cn(
                "flex-1 min-w-[140px] text-left p-4 rounded-xl border transition-colors",
                selectedRegion === rname
                  ? "bg-blue-50 dark:bg-blue-900/20 border-blue-500"
                  : "bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 hover:border-blue-300"
              )}
            >
              <div className="flex justify-between items-start mb-1">
                <div className="text-sm font-medium text-gray-500">{rname}</div>
                {metricMode !== 'Count' && (
                  <div className="text-xs font-medium text-blue-500 bg-blue-50 dark:bg-blue-500/10 px-1.5 py-0.5 rounded">
                    {reg.pct_acv}%
                  </div>
                )}
              </div>
              <div 
                className="text-xl font-bold text-gray-900 dark:text-white cursor-pointer hover:text-blue-500 transition-colors"
                onClick={(e) => {
                  e.stopPropagation()
                  handleDrill(`${rname} Deals`, { region: rname })
                }}
              >
                {metricMode === 'Count' ? formatCount(reg.count) : 
                 metricMode === 'Amount' ? formatACV(reg.acv) : 
                 `${formatCount(reg.count)} · ${formatACV(reg.acv)}`}
              </div>
              <div className="mt-2 space-y-1">
                {renderDelta(reg.delta_yesterday.count, reg.delta_yesterday.acv, yDayStr)}
                {renderDelta(reg.delta_lastweek.count, reg.delta_lastweek.acv, lwStr)}
              </div>
            </button>
          )
        })}
      </div>

      {selectedRegion !== 'All' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 bg-white dark:bg-gray-800 p-6 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm animate-in fade-in slide-in-">
          <div className="space-y-6">
            <h2 className="text-lg font-bold text-gray-900 dark:text-white flex items-center gap-2">
              <Globe2 className="w-5 h-5 text-blue-500" />
              {selectedRegion} Details
            </h2>
            
            {regionDetail && (
              <div className="flex gap-4">
                <div className="px-4 py-3 bg-gray-50 dark:bg-gray-900 rounded-lg flex-1 border border-gray-100 dark:border-gray-800">
                  <div className="text-xs text-gray-500 mb-1">Commit Coverage</div>
                  <div className="text-xl font-bold text-gray-900 dark:text-white">{regionDetail.commit_pct}%</div>
                </div>
                <div className="px-4 py-3 bg-gray-50 dark:bg-gray-900 rounded-lg flex-1 border border-gray-100 dark:border-gray-800">
                  <div className="text-xs text-gray-500 mb-1">Approved %</div>
                  <div className="text-xl font-bold text-gray-900 dark:text-white">
                    {regionDetail.acv > 0 ? Math.round((regionDetail.approval.Approved.acv / regionDetail.acv) * 100) : 0}%
                  </div>
                </div>
              </div>
            )}

            <div>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-gray-900 dark:text-white">What changed</h3>
                <div className="flex bg-gray-100 dark:bg-gray-800 p-0.5 rounded-lg">
                  <button
                    onClick={() => setMoveCompare('yesterday')}
                    className={cn(
                      "px-3 py-1 text-xs font-medium rounded-md transition-colors",
                      moveCompare === 'yesterday' ? "bg-white dark:bg-gray-700 shadow text-gray-900 dark:text-white" : "text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
                    )}
                  >
                    Vs YDay
                  </button>
                  <button
                    onClick={() => setMoveCompare('last_week')}
                    className={cn(
                      "px-3 py-1 text-xs font-medium rounded-md transition-colors",
                      moveCompare === 'last_week' ? "bg-white dark:bg-gray-700 shadow text-gray-900 dark:text-white" : "text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
                    )}
                  >
                    Vs 7d
                  </button>
                </div>
              </div>

              {!movementsData ? (
                <div className="h-32 flex items-center justify-center">
                  <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : (
                <div className="space-y-2">
                  {movementsData.category_moves.map((m: any, i: number) => (
                    <div 
                      key={`c-${i}`} 
                      className="flex justify-between items-center p-3 rounded-lg bg-gray-50 dark:bg-gray-900/50 hover:bg-gray-100 dark:hover:bg-gray-900 cursor-pointer transition-colors border border-transparent hover:border-gray-200 dark:hover:border-gray-700"
                      onClick={() => handleDrill(`Moved ${m.from_category} → ${m.to_category}`, { region: selectedRegion, deals: m.deals })}
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-medium px-2 py-1 bg-gray-200 dark:bg-gray-800 rounded">{m.from_category}</span>
                        <span className="text-gray-400">→</span>
                        <span className="text-xs font-medium px-2 py-1 bg-gray-200 dark:bg-gray-800 rounded">{m.to_category}</span>
                      </div>
                      <div className="text-sm font-medium text-gray-900 dark:text-white">
                        {metricMode === 'Count' ? formatCount(m.count) : metricMode === 'Amount' ? formatACV(m.acv) : `${formatCount(m.count)} · ${formatACV(m.acv)}`}
                      </div>
                    </div>
                  ))}
                  {movementsData.approval_moves.map((m: any, i: number) => (
                    <div 
                      key={`a-${i}`} 
                      className="flex justify-between items-center p-3 rounded-lg bg-gray-50 dark:bg-gray-900/50 hover:bg-gray-100 dark:hover:bg-gray-900 cursor-pointer transition-colors border border-transparent hover:border-gray-200 dark:hover:border-gray-700"
                      onClick={() => handleDrill(`Moved ${m.from_status} → ${m.to_status}`, { region: selectedRegion, deals: m.deals })}
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-medium px-2 py-1 bg-gray-200 dark:bg-gray-800 rounded">{m.from_status}</span>
                        <span className="text-gray-400">→</span>
                        <span className="text-xs font-medium px-2 py-1 bg-gray-200 dark:bg-gray-800 rounded">{m.to_status}</span>
                      </div>
                      <div className="text-sm font-medium text-gray-900 dark:text-white">
                        {metricMode === 'Count' ? formatCount(m.count) : metricMode === 'Amount' ? formatACV(m.acv) : `${formatCount(m.count)} · ${formatACV(m.acv)}`}
                      </div>
                    </div>
                  ))}
                  {movementsData.new_to_slice.count > 0 && (
                    <div 
                      className="flex justify-between items-center p-3 rounded-lg bg-green-50 dark:bg-green-900/10 hover:bg-green-100 dark:hover:bg-green-900/20 cursor-pointer transition-colors border border-transparent hover:border-green-200 dark:hover:border-green-900/30 text-green-700 dark:text-green-400"
                      onClick={() => handleDrill(`New to slice`, { region: selectedRegion, deals: movementsData.new_to_slice.deals })}
                    >
                      <div className="text-sm font-medium flex items-center gap-2">
                        <ArrowUpRight className="w-4 h-4" /> New to slice
                      </div>
                      <div className="text-sm font-bold">
                        {metricMode === 'Count' ? formatCount(movementsData.new_to_slice.count) : metricMode === 'Amount' ? formatACV(movementsData.new_to_slice.acv) : `${formatCount(movementsData.new_to_slice.count)} · ${formatACV(movementsData.new_to_slice.acv)}`}
                      </div>
                    </div>
                  )}
                  {movementsData.slipped_out.count > 0 && (
                    <div 
                      className="flex justify-between items-center p-3 rounded-lg bg-red-50 dark:bg-red-900/10 hover:bg-red-100 dark:hover:bg-red-900/20 cursor-pointer transition-colors border border-transparent hover:border-red-200 dark:hover:border-red-900/30 text-red-700 dark:text-red-400"
                      onClick={() => handleDrill(`Slipped out`, { region: selectedRegion, deals: movementsData.slipped_out.deals })}
                    >
                      <div className="text-sm font-medium flex items-center gap-2">
                        <ArrowDownRight className="w-4 h-4" /> Slipped out of slice
                      </div>
                      <div className="text-sm font-bold">
                        {metricMode === 'Count' ? formatCount(movementsData.slipped_out.count) : metricMode === 'Amount' ? formatACV(movementsData.slipped_out.acv) : `${formatCount(movementsData.slipped_out.count)} · ${formatACV(movementsData.slipped_out.acv)}`}
                      </div>
                    </div>
                  )}
                  {movementsData.category_moves.length === 0 && movementsData.approval_moves.length === 0 && movementsData.new_to_slice.count === 0 && movementsData.slipped_out.count === 0 && (
                    <div className="text-sm text-gray-500 italic p-4 text-center">No movements vs {moveCompare === 'yesterday' ? yDayStr : lwStr}</div>
                  )}
                </div>
              )}
            </div>
            
            {regionDetail && regionDetail.business_units && (
              <div>
                <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">Business Unit Mix</h3>
                <div className="space-y-2">
                  {regionDetail.business_units.map((bu: any) => {
                    const pct = regionDetail.acv > 0 ? (bu.acv / regionDetail.acv) * 100 : 0
                    return (
                      <div 
                        key={bu.bu}
                        className="cursor-pointer group"
                        onClick={() => handleDrill(`${selectedRegion} - ${bu.bu}`, { region: selectedRegion, bu: bu.bu })}
                      >
                        <div className="flex justify-between text-xs mb-1">
                          <span className="font-medium text-gray-700 dark:text-gray-300 group-hover:text-blue-500 transition-colors">{bu.bu}</span>
                          <span className="text-gray-500">
                            {metricMode === 'Count' ? formatCount(bu.count) : metricMode === 'Amount' ? formatACV(bu.acv) : `${formatCount(bu.count)} · ${formatACV(bu.acv)}`}
                            {' '}({Math.round(pct)}%)
                          </span>
                        </div>
                        <div className="h-2 w-full bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
                          <div 
                            className="h-full bg-blue-500 rounded-full transition-all group-hover:bg-blue-400"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
          
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white">Top Opportunities</h3>
              <div className="relative">
                <Search className="w-4 h-4 absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search deals..."
                  value={topSearch}
                  onChange={(e) => setTopSearch(e.target.value)}
                  className="pl-8 pr-3 py-1.5 text-sm bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 w-48"
                />
              </div>
            </div>

            {!topOppsData ? (
              <div className="h-64 flex items-center justify-center">
                <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : (
              <div className="space-y-1 max-h-[500px] overflow-y-auto pr-1">
                {topOppsData
                  .filter((o: any) => o.opportunity_name.toLowerCase().includes(topSearch.toLowerCase()) || o.account_name.toLowerCase().includes(topSearch.toLowerCase()))
                  .map((opp: any, idx: number) => (
                    <div 
                      key={opp.id}
                      onClick={() => setSelectedOppId(opp.id)}
                      className="p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer border border-transparent hover:border-gray-200 dark:hover:border-gray-700 transition-all flex items-center gap-3"
                    >
                      <div className="flex-shrink-0 w-6 text-center text-xs font-bold text-gray-400">
                        {idx + 1}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-900 dark:text-white truncate">
                          {opp.opportunity_name}
                        </div>
                        <div className="text-xs text-gray-500 truncate flex items-center gap-2 mt-0.5">
                          <span>{opp.account_name}</span>
                          <span>•</span>
                          <span>{opp.forecast_category}</span>
                        </div>
                      </div>
                      <div className="text-sm font-bold text-gray-900 dark:text-white whitespace-nowrap">
                        {formatACV(opp.forecast_acv_amount)}
                      </div>
                    </div>
                  ))}
                  {topOppsData.length === 0 && (
                    <div className="text-center py-8 text-gray-500 text-sm">No opportunities found</div>
                  )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Matrices */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-bold text-gray-900 dark:text-white">Region Matrix</h2>
          <div className="flex items-center gap-2 bg-gray-100 dark:bg-gray-800 p-1 rounded-lg">
            {['Value', 'Yesterday', 'LastWeek'].map(hm => (
              <button
                key={hm}
                onClick={() => setHeatMode(hm as any)}
                className={cn(
                  "px-3 py-1.5 text-xs font-medium rounded-md transition-all",
                  heatMode === hm
                    ? "bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm"
                    : "text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
                )}
              >
                {hm === 'Yesterday' ? 'vs YDay' : hm === 'LastWeek' ? 'vs 7d' : hm}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-8">
          <div>
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Forecast Category</h3>
            {(() => {
              const displayFc = ALL_FC
              return (
                <CompactGrid
                  title="Regions (Forecast Category)"
                  rowLabelName="Region"
                  columns={displayFc}
                  rows={regions.map((r: any) => ({
                    label: r.region,
                    cells: r.cells,
                    total: { count: r.count, acv: r.acv }
                  }))}
                  totals={{ category: summary.totals.categories, grand: summary.total }}
                  deltas={heatMode === 'Yesterday' ? 
                    regions.reduce((acc: any, r: any) => ({...acc, [r.region]: r.delta_yesterday}), {}) :
                    heatMode === 'LastWeek' ? 
                    regions.reduce((acc: any, r: any) => ({...acc, [r.region]: r.delta_lastweek}), {}) : {}
                  }
                  metricMode={metricMode}
                  onCellClick={(rowLabel, col) => {
                    if (!col && !rowLabel) handleDrill(`All Regions`, {})
                    else if (!col) handleDrill(`${rowLabel} Deals`, { region: rowLabel })
                    else if (!rowLabel) handleDrill(`All Regions - ${col}`, { category: col })
                    else handleDrill(`${rowLabel} - ${col}`, { region: rowLabel, category: col })
                  }}
                  compareDate={compare === 'yesterday' ? summary.yesterday_date : summary.lastweek_date}
                  yesterdayDate={summary.yesterday_date}
                  lastweekDate={summary.lastweek_date}
                />
              )
            })()}
          </div>

          <div>
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Approval Status</h3>
            <CompactGrid
              title="Regions (Approval Status)"
              rowLabelName="Region"
              columns={FUNNEL_STAGES}
              rows={regions.map((r: any) => ({
                label: r.region,
                cells: r.approval,
                total: { count: r.count, acv: r.acv }
              }))}
              totals={{ category: summary.totals.approval, grand: summary.total }}
              deltas={heatMode === 'Yesterday' ? 
                regions.reduce((acc: any, r: any) => ({...acc, [r.region]: r.delta_yesterday}), {}) :
                heatMode === 'LastWeek' ? 
                regions.reduce((acc: any, r: any) => ({...acc, [r.region]: r.delta_lastweek}), {}) : {}
              }
              metricMode={metricMode}
              onCellClick={(rowLabel, col) => {
                if (!col && !rowLabel) handleDrill(`All Regions`, {})
                else if (!col) handleDrill(`${rowLabel} Deals`, { region: rowLabel })
                else if (!rowLabel) handleDrill(`All Regions - ${col}`, { status: col })
                else handleDrill(`${rowLabel} - ${col}`, { region: rowLabel, status: col })
              }}
              compareDate={compare === 'yesterday' ? summary.yesterday_date : summary.lastweek_date}
              yesterdayDate={summary.yesterday_date}
              lastweekDate={summary.lastweek_date}
            />
          </div>
        </div>
      </Card>
      
      {/* Insight Line */}
      {insightLines.map((l, i) => (
        <SummaryLine key={i} primaryText={l} />
      ))}

      {modalOpen && (
        <DealListModal
          title={modalTitle}
          deals={dealsData?.deals || []}
          initialFilters={{
            sub_region: modalFilters.region,
            forecast_category: modalFilters.category,
            approval_status: modalFilters.status
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

export default function Regions() {
  return (
    <ErrorBoundary>
      <RegionsContent />
    </ErrorBoundary>
  )
}
