import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { CheckCircle2, Clock, FileQuestion, Sigma, Activity, TrendingUp, AlertOctagon } from 'lucide-react'
import { useAppStore } from '@/store/appStore'
import { getApprovalsDistribution, getApprovalsDeals } from '@/api/client'
import { formatCurrency, formatNumber, acvM } from '@/utils/format'
import EmptyState from '@/components/ui/EmptyState'
import MetricToggle from '@/components/common/MetricToggle'
import CompactGrid from '@/components/common/CompactGrid'
import DealListModal from '@/components/common/DealListModal'
import FilterBar from '@/components/common/FilterBar'
import OpportunityDrawer from '@/components/overview/OpportunityDrawer'
import Card from '@/components/ui/Card'

function formatDelta(val: number, isCount: boolean) {
  if (val == null) return null
  const sign = val > 0 ? '+' : ''
  const color = val > 0 ? 'text-emerald-600 dark:text-emerald-400' : val < 0 ? 'text-red-600 dark:text-red-400' : 'text-[var(--text-muted)]'
  const text = isCount ? `${sign}${val}` : `${sign}${acvM(val)}`
  return <span className={color}>{text}</span>
}

function StatChip({ label, data, icon: Icon, metricMode, compareDate }: any) {
  const isCount = metricMode === 'Count'
  const val = isCount ? data.count : data.acv
  const valStr = isCount ? formatNumber(val) : formatCurrency(val)
  
  const dYes = data.delta_yesterday
  const dLast = data.delta_lastweek
  const dCust = data.delta_custom

  const renderDeltas = () => {
    if (dCust && (dCust.count || dCust.acv)) {
      return <span>{compareDate ? compareDate.substring(5,10) : 'vs'} {formatDelta(dCust.count, true)} · {formatDelta(dCust.acv, false)}</span>
    }
    return (
      <span className="flex flex-col gap-0.5 mt-1 text-[10px] text-[var(--text-muted)] font-medium">
        <span>vs {data.yesterday_date ? data.yesterday_date.substring(5,10) : 'Yesterday'} {formatDelta(dYes?.count, true)} · {formatDelta(dYes?.acv, false)}</span>
        <span>vs {data.lastweek_date ? data.lastweek_date.substring(5,10) : 'Last Week'} {formatDelta(dLast?.count, true)} · {formatDelta(dLast?.acv, false)}</span>
      </span>
    )
  }

  return (
    <div className="card px-4 py-3 flex items-center justify-between border border-[var(--border)] transition-transform hover:scale-[1.02]">
      <div className="flex items-center gap-3">
        <div className={`p-2 rounded-xl ${label === 'Approved' ? 'bg-emerald-500/10 text-emerald-500' : label === 'Pending' ? 'bg-amber-500/10 text-amber-500' : label === 'Blank' ? 'bg-slate-500/10 text-slate-500' : 'bg-[var(--primary)]/10 text-[var(--primary)]'}`}>
          <Icon className="w-5 h-5" />
        </div>
        <div>
          <div className="text-[11px] font-semibold text-[var(--text-muted)] uppercase tracking-wider">{label}</div>
          <div className="text-xl font-black text-[var(--text-primary)] leading-tight">{valStr}</div>
          <div className="text-[10px] text-[var(--text-muted)] leading-tight mt-0.5 font-medium">{renderDeltas()}</div>
        </div>
      </div>
    </div>
  )
}

export default function Approvals() {
  const { activeSnapshotId, compareSnapshotId, includeDeletedLost, snapshots, metricMode, selectedOppId, setSelectedOppId } = useAppStore()
  
  const [modalOpen, setModalOpen] = useState(false)
  const [modalTitle, setModalTitle] = useState('')
  const [modalFilters, setModalFilters] = useState<any>({})
  
  const [movementsMode, setMovementsMode] = useState<'yesterday' | 'lastweek'>('yesterday')

  const activeSnapshot = snapshots.find(s => s.id === activeSnapshotId)
  const compareSnapshot = snapshots.find(s => s.id === compareSnapshotId)

  const { data, isLoading, error } = useQuery({
    queryKey: ['approvals_v2', activeSnapshotId, compareSnapshotId, includeDeletedLost],
    queryFn: async () => {
      if (!activeSnapshotId) return null
      return getApprovalsDistribution(activeSnapshot?.snapshot_date || '', compareSnapshot?.snapshot_date, includeDeletedLost)
    },
    enabled: !!activeSnapshotId,
  })

  const { data: dealsData } = useQuery({
    queryKey: ['approvals_deals_v2', activeSnapshotId, modalFilters, includeDeletedLost],
    queryFn: () => getApprovalsDeals(
      activeSnapshot?.snapshot_date || '', 
      modalFilters.approval_status || undefined, 
      modalFilters.forecast_category || undefined, 
      includeDeletedLost,
      modalFilters.sub_region || undefined,
      modalFilters.business_unit_primary || undefined
    ),
    enabled: modalOpen && !!activeSnapshotId,
  })

  if (!activeSnapshotId) return <EmptyState title="No active snapshot" description="Select a snapshot to view data" />
  if (isLoading) return <div className="p-8 text-center text-slate-500 animate-pulse">Loading approval data...</div>
  if (error || data?.error) return <div className="p-8 text-center text-rose-500 font-semibold bg-rose-50 border border-rose-200 rounded-xl m-6">{(error as any)?.message || data?.error}</div>
  if (!data || !data.total) return <EmptyState title="No data" description="No approval data found or the response was malformed." />
  if (data.total?.count === 0) return <EmptyState title="No data" description="The data slice is empty." />

  const total = data.total || { count: 0, acv: 0 }
  const statuses = data.statuses || []
  const matrix = data.matrix || {}
  const categories = data.categories || []
  const movements_yesterday = data.movements_yesterday || []
  const movements_lastweek = data.movements_lastweek || []
  const movements_custom = data.movements_custom || []
  const pending_deals = data.pending_deals || []
  const data_slice = data.data_slice || ''
  const data_slice_key = data.data_slice_key || ''
  const yesterday_date = data.yesterday_date
  const lastweek_date = data.lastweek_date
  
  const getStatus = (name: string) => statuses.find((s: any) => s.status === name) || { count: 0, acv: 0, delta_yesterday: {}, delta_lastweek: {}, delta_custom: {} }
  const attachDates = (obj: any) => ({ ...obj, yesterday_date, lastweek_date })

  const handleCellClick = (filters: any, title?: string) => {
    setModalFilters(filters)
    setModalTitle(title || `Deals`)
    setModalOpen(true)
  }

  const colSums = categories.reduce((acc: any, c: string) => {
    acc[c] = { count: 0, acv: 0 }
    Object.values(matrix).forEach((row: any) => {
      acc[c].count += row[c]?.count || 0
      acc[c].acv += row[c]?.acv || 0
    })
    return acc
  }, {})

  const rowsForGrid = Object.entries(matrix).map(([st, cells]: [string, any]) => ({
    id: st,
    label: st,
    cells: cells || {},
    total: getStatus(st)
  }))

  const deltasForGrid = {
    yesterday: {
      rows: statuses.reduce((acc: any, s: any) => ({ ...acc, [s.status]: s.delta_yesterday }), {}),
      grand: total.delta_yesterday
    },
    lastweek: {
      rows: statuses.reduce((acc: any, s: any) => ({ ...acc, [s.status]: s.delta_lastweek }), {}),
      grand: total.delta_lastweek
    },
    custom: {
      rows: statuses.reduce((acc: any, s: any) => ({ ...acc, [s.status]: s.delta_custom }), {}),
      grand: total.delta_custom
    }
  }

  // Donut chart logic
  let cumulativePct = 0
  const donutSegments = statuses.map((r: any) => {
    const pct = total.acv ? (r.acv / total.acv) * 100 : 0
    const startPct = cumulativePct
    cumulativePct += pct
    const color = r.status === 'Approved' ? '#10B981' : r.status === 'Pending Approval' ? '#F59E0B' : r.status === 'Blank' ? '#94A3B8' : '#ef4444'
    return { ...r, pct, startPct, color }
  })

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-6 pb-20"
    >
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-black text-[var(--text-primary)] tracking-tight">Approval Funnel</h1>
          <p className="text-[var(--text-muted)] mt-1 flex items-center gap-2 text-sm font-medium">
            <span className="px-2 py-0.5 rounded-md bg-[var(--bg-secondary)] border border-[var(--border)]">{data_slice}</span>
            <span className="px-2 py-0.5 rounded-md bg-[var(--bg-secondary)] border border-[var(--border)]">{data_slice_key}</span>
            <span>As of {activeSnapshot?.snapshot_date}</span>
          </p>
        </div>
        <MetricToggle />
      </div>


      {/* Slim Stat Chips */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="cursor-pointer" onClick={() => handleCellClick({ approval_status: 'Approved' }, 'Approved Deals')}><StatChip label="Approved" data={attachDates(getStatus('Approved'))} icon={CheckCircle2} metricMode={metricMode} compareDate={compareSnapshot?.snapshot_date} /></div>
        <div className="cursor-pointer" onClick={() => handleCellClick({ approval_status: 'Pending Approval' }, 'Pending Deals')}><StatChip label="Pending" data={attachDates(getStatus('Pending Approval'))} icon={Clock} metricMode={metricMode} compareDate={compareSnapshot?.snapshot_date} /></div>
        <div className="cursor-pointer" onClick={() => handleCellClick({ approval_status: 'Blank' }, 'Not Submitted Deals')}><StatChip label="Not submitted" data={attachDates(getStatus('Blank'))} icon={FileQuestion} metricMode={metricMode} compareDate={compareSnapshot?.snapshot_date} /></div>
        <div className="cursor-pointer" onClick={() => handleCellClick({}, 'All Deals')}><StatChip label="Total" data={attachDates(total)} icon={Sigma} metricMode={metricMode} compareDate={compareSnapshot?.snapshot_date} /></div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        
        {/* Left: Donut Chart */}
        <Card className="xl:col-span-5 p-5 flex flex-col hover:border-[var(--primary)] transition-colors">
           <h2 className="text-sm font-bold text-[var(--text-primary)] mb-4 cursor-pointer" onClick={() => handleCellClick({}, 'All Approvals')}>Status Share</h2>
           <div className="flex flex-col sm:flex-row items-center gap-6">
             <div className="relative w-40 h-40 flex-shrink-0 flex items-center justify-center cursor-pointer" onClick={() => handleCellClick({}, 'All Approvals')}>
               <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
                 <circle cx="50" cy="50" r="40" fill="transparent" stroke="var(--bg-secondary)" strokeWidth="14" />
                 {donutSegments.map((seg: any) => {
                   const circumference = 2 * Math.PI * 40
                   const strokeDasharray = `${(seg.pct / 100) * circumference} ${circumference}`
                   const strokeDashoffset = -((seg.startPct / 100) * circumference)
                   if (seg.pct === 0) return null
                   return (
                     <circle
                       key={seg.status}
                       cx="50" cy="50" r="40"
                       fill="transparent"
                       stroke={seg.color}
                       strokeWidth="14"
                       strokeDasharray={strokeDasharray}
                       strokeDashoffset={strokeDashoffset}
                       className="transition-all hover:opacity-80"
                       onClick={(e) => { e.stopPropagation(); handleCellClick({ approval_status: seg.status }, seg.status) }}
                     />
                   )
                 })}
               </svg>
               <div className="absolute inset-0 flex flex-col items-center justify-center text-center pointer-events-none">
                 <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">{metricMode === 'Count' ? 'Deals' : 'ACV'}</span>
                 <span className="text-xl font-black text-[var(--text-primary)] tabular-nums">{metricMode === 'Count' ? formatNumber(total?.count ?? 0) : acvM(total?.acv ?? 0)}</span>
               </div>
             </div>
             
             {/* Legend */}
             <div className="flex-1 w-full space-y-2">
               {donutSegments.map((seg: any) => (
                 <div key={seg.status} className="flex flex-col bg-[var(--bg-secondary)] p-2 rounded-lg border border-[var(--border)] cursor-pointer hover:border-[var(--primary)] transition-colors" onClick={() => handleCellClick({ approval_status: seg.status }, seg.status)}>
                   <div className="flex items-center justify-between font-bold text-[var(--text-primary)] text-xs">
                     <div className="flex items-center gap-1.5">
                       <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: seg.color }}></div>
                       <span>{seg.status === 'Blank' ? 'Not submitted' : seg.status}</span>
                     </div>
                     <span>{metricMode === 'Count' ? formatNumber(seg.count) : acvM(seg.acv)} ({seg.pct.toFixed(0)}%)</span>
                   </div>
                   <div className="flex justify-between items-center text-[9px] text-[var(--text-muted)] mt-1 font-medium pl-4">
                      <span>vs {yesterday_date ? yesterday_date.substring(5,10) : '1d'} {formatDelta(metricMode === 'Count' ? seg.delta_yesterday?.count : seg.delta_yesterday?.acv, metricMode === 'Count')}</span>
                      <span>vs {lastweek_date ? lastweek_date.substring(5,10) : '7d'} {formatDelta(metricMode === 'Count' ? seg.delta_lastweek?.count : seg.delta_lastweek?.acv, metricMode === 'Count')}</span>
                   </div>
                 </div>
               ))}
             </div>
           </div>
        </Card>

        {/* Right: Grid */}
        <div className="xl:col-span-7">
          {(() => {
            const displayCategories = ['Closed', 'Commit', 'Best Case', 'Pipeline', 'Blank']
            return (
              <CompactGrid
                title="Status vs. Forecast Category"
                columns={displayCategories}
                rows={rowsForGrid}
                totals={{ category: colSums, grand: { count: total.count, acv: total.acv } }}
                deltas={deltasForGrid}
                metricMode={metricMode}
                onCellClick={(r, c, title) => handleCellClick({ approval_status: r === 'Total' ? null : r, forecast_category: c === 'Total' ? null : c }, title)}
                rowLabelName="Status"
                compareDate={compareSnapshot?.snapshot_date}
              />
            )
          })()}
        </div>
      </div>

      {/* Insights Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="p-4 flex flex-col hover:border-[var(--primary)] transition-colors">
          <div className="flex items-center justify-between mb-3 text-[var(--text-primary)]">
             <div className="flex items-center gap-2">
               <Activity className="w-5 h-5 text-emerald-500" />
               <h3 className="font-bold">Recent Movements</h3>
             </div>
             {!compareSnapshotId && (
               <div className="flex bg-[var(--bg-secondary)] rounded-lg p-0.5 border border-[var(--border)]">
                 <button className={`px-2 py-0.5 text-[10px] font-bold rounded-md ${movementsMode === 'yesterday' ? 'bg-[var(--bg-primary)] shadow-sm' : 'text-[var(--text-muted)]'}`} onClick={() => setMovementsMode('yesterday')}>Yesterday</button>
                 <button className={`px-2 py-0.5 text-[10px] font-bold rounded-md ${movementsMode === 'lastweek' ? 'bg-[var(--bg-primary)] shadow-sm' : 'text-[var(--text-muted)]'}`} onClick={() => setMovementsMode('lastweek')}>Last Week</button>
               </div>
             )}
          </div>
          <div className="flex-1 overflow-y-auto min-h-[160px] text-xs space-y-3">
             {(() => {
               const moves = compareSnapshotId ? movements_custom : (movementsMode === 'yesterday' ? movements_yesterday : movements_lastweek);
               const newlyAppr = moves.filter((m: any) => m.to_status === 'Approved');
               const newlyPend = moves.filter((m: any) => m.to_status === 'Pending Approval');
               return (
                 <>
                   <div>
                     <p className="text-[var(--text-muted)] text-[10px] font-bold uppercase mb-1">Newly Approved ({newlyAppr.length})</p>
                     {newlyAppr.length === 0 ? <div className="text-[10px] text-[var(--text-muted)] italic">None</div> : 
                       newlyAppr.map((m: any, idx: number) => (
                         <div key={'a'+idx} className="bg-[var(--bg-secondary)] p-1.5 rounded-md border border-[var(--border)] mb-1 flex justify-between">
                           <span className="font-semibold text-[10px]">From {m.from_status}</span>
                           <span className="font-bold text-[10px] text-emerald-600">+{formatCurrency(m.acv)} ({m.count})</span>
                         </div>
                       ))
                     }
                   </div>
                   <div>
                     <p className="text-[var(--text-muted)] text-[10px] font-bold uppercase mb-1">Newly Pending ({newlyPend.length})</p>
                     {newlyPend.length === 0 ? <div className="text-[10px] text-[var(--text-muted)] italic">None</div> : 
                       newlyPend.map((m: any, idx: number) => (
                         <div key={'p'+idx} className="bg-[var(--bg-secondary)] p-1.5 rounded-md border border-[var(--border)] mb-1 flex justify-between">
                           <span className="font-semibold text-[10px]">From {m.from_status}</span>
                           <span className="font-bold text-[10px] text-amber-600">+{formatCurrency(m.acv)} ({m.count})</span>
                         </div>
                       ))
                     }
                   </div>
                 </>
               )
             })()}
          </div>
        </Card>

        <Card className="p-4 flex flex-col hover:border-[var(--primary)] transition-colors">
          <div className="flex items-center gap-2 mb-3 text-[var(--text-primary)]">
             <Clock className="w-5 h-5 text-amber-500" />
             <h3 className="font-bold">Submitted, waiting for approval</h3>
          </div>
          <div className="flex-1 overflow-y-auto min-h-[160px] text-xs space-y-2">
             <p className="text-[var(--text-muted)] text-[11px] italic cursor-pointer hover:underline" onClick={() => handleCellClick({ approval_status: 'Pending Approval' }, 'Pending Deals')}>All {pending_deals?.length || 0} pending deals...</p>
             {(!pending_deals || pending_deals.length === 0) ? (
                <div className="text-center py-6 text-[var(--text-muted)]">No pending deals.</div>
             ) : (
                pending_deals.map((p: any, idx: number) => {
                  const daysToClose = p.close_date && activeSnapshot ? Math.floor((new Date(p.close_date).getTime() - new Date(activeSnapshot.snapshot_date).getTime()) / (1000 * 3600 * 24)) : 999;
                  return (
                  <div key={idx} className="bg-[var(--bg-secondary)] p-2 rounded-lg border border-[var(--border)] cursor-pointer hover:border-[var(--primary)] transition-colors" onClick={() => { setSelectedOppId(p.opportunity_id_18); handleCellClick({ approval_status: 'Pending Approval' }, 'Pending Deals'); }}>
                    <div className="flex justify-between font-bold text-[var(--text-primary)]"><span className="truncate pr-2">{p.account_name || p.opportunity_name}</span> <span className="text-amber-600">{acvM(p.forecast_acv_amount)}</span></div>
                    <div className="flex justify-between items-center text-[10px] text-[var(--text-muted)] mt-1">
                      <span>{p.close_date ? p.close_date.substring(0,10) : 'No close date'}</span>
                      {daysToClose <= 30 && <span className="bg-red-500/10 text-red-600 px-1.5 py-0.5 rounded-sm font-bold border border-red-500/20">closes in {daysToClose}d</span>}
                    </div>
                  </div>
                )})
             )}
          </div>
        </Card>

        <Card className="p-4 flex flex-col hover:border-[var(--primary)] transition-colors">
          <div className="flex items-center gap-2 mb-3 text-[var(--text-primary)]">
             <AlertOctagon className="w-5 h-5 text-rose-500" />
             <h3 className="font-bold">Not Submitted</h3>
          </div>
          <div className="flex-1 overflow-y-auto min-h-[160px] text-xs space-y-2">
             <p className="text-[var(--text-muted)] text-[11px] italic">Commit deals with Blank status...</p>
             <div className="bg-[var(--bg-secondary)] p-2 rounded-lg border border-[var(--border)] cursor-pointer hover:border-[var(--primary)] transition-colors" onClick={() => handleCellClick({ approval_status: 'Blank', forecast_category: 'Commit' }, 'Not Submitted (Blank Commit)')}>
               <div className="flex justify-between font-bold text-[var(--text-primary)]"><span>Total Blank Commits</span> <span className="text-rose-600">{acvM(matrix['Blank']?.['Commit']?.acv || 0)}</span></div>
               <div className="text-[10px] text-[var(--text-muted)] mt-1">{matrix['Blank']?.['Commit']?.count || 0} deals at risk</div>
             </div>
          </div>
        </Card>
      </div>

      {modalOpen && (
        <DealListModal
          title={modalTitle}
          deals={dealsData?.deals || []}
          initialFilters={modalFilters}
          onSelectOpp={setSelectedOppId}
          onClose={() => setModalOpen(false)}
        />
      )}
      <OpportunityDrawer oppId={selectedOppId} onClose={() => setSelectedOppId(null)} />
    </motion.div>
  )
}
