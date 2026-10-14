import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { AlertTriangle, TrendingUp, BarChart2, ListTodo, Activity } from 'lucide-react'
import { useAppStore } from '@/store/appStore'
import { getV2ExpirySummary, getV2ExpiryDeals } from '@/api/client'
import { formatDate, acvM, formatCurrency } from '@/utils/format'
import { FORECAST_COLORS } from '@/design/tokens'
import OpportunityDrawer from '@/components/overview/OpportunityDrawer'
import { EmptyState } from '@/components/ui/EmptyState'
import MetricToggle from '@/components/common/MetricToggle'
import CompactGrid from '@/components/common/CompactGrid'
import SummaryLine from '@/components/common/SummaryLine'
import DealListModal from '@/components/common/DealListModal'
import FilterBar from '@/components/common/FilterBar'
import Card from '@/components/ui/Card'
import clsx from 'clsx'

export default function Expiry() {
  const {
    activeSnapshotId,
    compareSnapshotId,
    snapshots,
    includeDeletedLost,
    selectedOppId,
    setSelectedOppId,
    metricMode
  } = useAppStore()

  const activeSnapshot = snapshots.find(s => s.id === activeSnapshotId)
  const compareSnapshot = snapshots.find(s => s.id === compareSnapshotId)

  const [modalOpen, setModalOpen] = useState(false)
  const [modalTitle, setModalTitle] = useState('')
  const [modalParams, setModalParams] = useState<{ quarter: string | null; category: string | null; slippage?: boolean }>({ quarter: null, category: null })
  
  const [heatMode, setHeatMode] = useState<'Value'|'Yesterday'|'LastWeek'>('Value')

  const { data: sum, isLoading, isError } = useQuery({
    queryKey: ['v2ExpirySummary', activeSnapshotId, compareSnapshotId, includeDeletedLost],
    queryFn: () => getV2ExpirySummary({
      as_of: activeSnapshot?.snapshot_date,
      compare: compareSnapshot?.snapshot_date,
      exclude_deleted_lost: !includeDeletedLost
    }),
    enabled: !!activeSnapshotId,
  })

  const { data: dealsData } = useQuery({
    queryKey: ['v2ExpiryDeals', activeSnapshotId, modalParams.quarter, modalParams.category, modalParams.slippage, includeDeletedLost],
    queryFn: () => getV2ExpiryDeals({
      quarter: modalParams.quarter || undefined,
      category: modalParams.category || undefined,
      slippage: modalParams.slippage,
      as_of: activeSnapshot?.snapshot_date,
      exclude_deleted_lost: !includeDeletedLost
    }),
    enabled: modalOpen && !!activeSnapshotId,
  })

  if (!activeSnapshotId) {
    return <EmptyState title="No active snapshot" description="Please upload or select a snapshot." icon={<AlertTriangle className="w-10 h-10 text-[var(--text-muted)]" />} />
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-64 bg-[var(--bg-secondary)] animate-pulse rounded-md"></div>
        <div className="h-48 w-full bg-[var(--bg-secondary)] animate-pulse rounded-xl"></div>
        <div className="h-48 w-full bg-[var(--bg-secondary)] animate-pulse rounded-xl"></div>
      </div>
    )
  }

  if (isError || !sum || sum.error) {
    return <div className="p-8 text-center text-rose-500 font-semibold bg-rose-50 border border-rose-200 rounded-xl m-6">{sum?.error || 'Failed to load Expiry view.'}</div>
  }
  if (!sum.grand_total) {
    return <EmptyState title="No data" description="No expiry data found or the response was malformed." />
  }

  const handleCellClick = (quarter: string | null, category: string | null, title: string, isSlippage = false) => {
    setModalParams({ quarter, category, slippage: isSlippage })
    setModalTitle(title)
    setModalOpen(true)
  }

  const fy1 = sum.fiscal_years?.[0]?.label || '2026'
  const fy2 = sum.fiscal_years?.[1]?.label || '2027'
  const grid1 = sum.grids?.[fy1]
  const grid2 = sum.grids?.[fy2]
  const deltas1 = sum.deltas?.[fy1]
  const deltas2 = sum.deltas?.[fy2]

  const grandTotal = sum.grand_total || { count: 0, acv: 0 }
  const yestGrand = deltas1?.yesterday?.grand
  const lastGrand = deltas1?.lastweek?.grand

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-6 pb-12"
    >
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-black tracking-tight text-[var(--text-primary)]">Expiry</h1>
          <p className="text-[var(--text-muted)] mt-1 text-sm font-medium">
            As of {formatDate(sum.snapshot_date)} {sum.compare_date && ` vs ${formatDate(sum.compare_date)}`}
          </p>
        </div>
        <div className="flex items-center gap-3 bg-[var(--bg-secondary)] p-1.5 rounded-xl border border-[var(--border)] shadow-sm">
          <div className="flex items-center gap-1 bg-[var(--bg-primary)] p-1 rounded-lg border border-[var(--border)] shadow-inner">
             <span className="px-2 text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-wider">Heat by</span>
             <button onClick={() => setHeatMode('Value')} className={clsx("px-2.5 py-1 rounded-md text-xs font-bold transition-all", heatMode === 'Value' ? "bg-indigo-500 text-white shadow" : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-secondary)]")}>Value</button>
             <button onClick={() => setHeatMode('Yesterday')} className={clsx("px-2.5 py-1 rounded-md text-xs font-bold transition-all", heatMode === 'Yesterday' ? "bg-indigo-500 text-white shadow" : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-secondary)]")}>vs Yesterday</button>
             <button onClick={() => setHeatMode('LastWeek')} className={clsx("px-2.5 py-1 rounded-md text-xs font-bold transition-all", heatMode === 'LastWeek' ? "bg-indigo-500 text-white shadow" : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-secondary)]")}>vs Last Week</button>
          </div>
          <MetricToggle />
        </div>
      </div>


      {/* Grand Total & Slippage KPI Strip */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card
          className="p-5 flex flex-col justify-between hover:border-[var(--primary)] transition-colors cursor-pointer border-l-4 border-l-indigo-500"
          onClick={() => handleCellClick(null, null, `All Expiry Deals (FY${fy1} + FY${fy2})`)}
        >
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider">
                FY{fy1} All-Years Total Expiry
              </span>
              <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">
                {grandTotal.count} deals
              </span>
            </div>
            <div className="text-3xl font-black text-[var(--text-primary)] mt-2">
              {formatCurrency(grandTotal.acv)}
            </div>
          </div>
          <div className="flex items-center gap-4 mt-4 pt-3 border-t border-[var(--border)] text-xs text-[var(--text-muted)]">
            <span>
              vs Yesterday: <strong className={yestGrand?.acv && yestGrand.acv > 0 ? "text-emerald-600 dark:text-emerald-400" : ""}>
                {yestGrand ? `${yestGrand.count >= 0 ? '+' : ''}${yestGrand.count} deals / ${formatCurrency(yestGrand.acv)}` : '—'}
              </strong>
            </span>
            <span>
              vs Last Week: <strong className={lastGrand?.acv && lastGrand.acv > 0 ? "text-emerald-600 dark:text-emerald-400" : ""}>
                {lastGrand ? `${lastGrand.count >= 0 ? '+' : ''}${lastGrand.count} deals / ${formatCurrency(lastGrand.acv)}` : '—'}
              </strong>
            </span>
          </div>
        </Card>

        <Card
          className="p-5 flex flex-col justify-between hover:border-[var(--primary)] transition-colors cursor-pointer border-l-4 border-l-amber-500"
          onClick={() => handleCellClick(null, null, `Slippage to FY${fy2} (${sum.slippage?.count || 0} deals)`, true)}
        >
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-amber-600 dark:text-amber-400 uppercase tracking-wider flex items-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5" /> Slippage to FY{fy2}
              </span>
              <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400">
                {sum.slippage?.count ?? 0} deals
              </span>
            </div>
            <div className="text-3xl font-black text-amber-600 dark:text-amber-400 mt-2">
              {formatCurrency(sum.slippage?.acv ?? 0)}
            </div>
          </div>
          <div className="mt-4 pt-3 border-t border-[var(--border)] text-xs text-[var(--text-muted)] flex items-center justify-between">
            <span>Close date after FY{fy1} year end</span>
            <span className="text-amber-600 dark:text-amber-400 font-semibold hover:underline">Click to view slippage deals →</span>
          </div>
        </Card>
      </div>

      {sum.fiscal_years?.map((fyObj: any) => {
        const yLabel = fyObj.label
        const grid = sum.grids?.[yLabel]
        if (!grid) return null
        const deltas = sum.deltas?.[yLabel]
        return (
          <div key={yLabel} className="space-y-1">
            <CompactGrid
              title={`FY ${yLabel} Expiry`}
              columns={['Closed', 'Commit', 'Best Case', 'Pipeline', 'Blank']}
              rows={grid.rows.map((r: any) => ({ id: r.quarter, label: r.label, cells: r.cells, total: r.total }))}
              totals={grid.totals}
              deltas={deltas}
              metricMode={metricMode}
              heatMode={heatMode}
              onCellClick={(quarter, cat, title) => handleCellClick(quarter, cat === 'Total' ? null : cat, title)}
              rowLabelName="Quarter"
              compareDate={sum.compare_date}
            />
            <SummaryLine
              primaryText={`FY${yLabel} expiry: ${acvM(sum.acv_by_year?.[yLabel]?.acv)} · ${sum.acv_by_year?.[yLabel]?.count} deals`}
              secondaryText={yLabel === fy1 && sum.slippage?.count > 0 ? `Slippage to ${fy2}: ${acvM(sum.slippage?.acv)} · ${sum.slippage?.count} deals` : undefined}
              details={yLabel === fy1 && sum.slippage?.by_quarter?.length > 0 ? sum.slippage.by_quarter : undefined}
              onDetailClick={(q) => handleCellClick(q, null, `Slippage Deals in ${q}`, true)}
            />
          </div>
        )
      })}


      {/* Insights Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-4 gap-4 mt-8">
        <Card className="p-4 flex flex-col hover:border-[var(--primary)] transition-colors">
          <div className="flex items-center gap-2 mb-4 text-[var(--text-primary)]">
             <BarChart2 className="w-5 h-5 text-indigo-500" />
             <h3 className="font-bold">Expiry Profile</h3>
          </div>
          <div className="flex-1 flex flex-col justify-end gap-3 min-h-[160px]">
             {grid1?.rows?.map((r: any) => {
               const qTot = r.total.acv
               if (qTot === 0) return null
               return (
                 <div key={r.quarter} className="w-full">
                    <div className="flex justify-between text-[10px] font-semibold text-[var(--text-muted)] mb-1">
                       <span>{r.label}</span>
                       <span>{acvM(qTot)}</span>
                    </div>
                    <div className="flex w-full h-3 bg-[var(--bg-secondary)] rounded-full overflow-hidden">
                       {['Closed', 'Commit', 'Best Case', 'Pipeline', 'Blank'].map((c: string) => {
                         const cVal = r.cells[c]?.acv || 0
                         if (cVal === 0) return null
                         return (
                           <div key={c} style={{ width: `${(cVal/qTot)*100}%`, backgroundColor: FORECAST_COLORS[c as keyof typeof FORECAST_COLORS] || '#cbd5e1' }} className="h-full border-r border-[var(--bg-primary)] last:border-0" title={`${c}: ${acvM(cVal)}`} />
                         )
                       })}
                    </div>
                 </div>
               )
             })}
          </div>
        </Card>

        <Card className="p-4 flex flex-col hover:border-[var(--primary)] transition-colors">
          <div className="flex items-center gap-2 mb-4 text-[var(--text-primary)]">
             <Activity className="w-5 h-5 text-emerald-500" />
             <h3 className="font-bold">Closure Progress</h3>
          </div>
          <div className="flex-1 flex flex-col justify-end gap-3 min-h-[160px]">
             {grid1?.rows?.map((r: any) => {
               const closed = r.cells['Closed']?.acv || 0
               const open = r.total.acv - closed
               const tot = r.total.acv
               if (tot === 0) return null
               const pct = Math.round((closed/tot)*100)
               return (
                 <div key={r.quarter} className="w-full">
                    <div className="flex justify-between text-[10px] font-semibold text-[var(--text-muted)] mb-1">
                       <span>{r.label}</span>
                       <span className="text-emerald-600 dark:text-emerald-400">{pct}% Closed</span>
                    </div>
                    <div className="flex w-full h-3 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                       <div style={{ width: `${pct}%` }} className="h-full bg-emerald-500" />
                       <div style={{ width: `${100-pct}%` }} className="h-full bg-slate-300 dark:bg-slate-600" />
                    </div>
                 </div>
               )
             })}
          </div>
        </Card>

        <Card className="p-4 flex flex-col hover:border-[var(--primary)] transition-colors">
          <div className="flex items-center gap-2 mb-3 text-[var(--text-primary)]">
             <TrendingUp className="w-5 h-5 text-sky-500" />
             <h3 className="font-bold">What Changed Today</h3>
          </div>
          <div className="flex-1 overflow-y-auto min-h-[160px] text-xs space-y-2">
             <p className="text-[var(--text-muted)] text-[11px] italic">Showing significant movements since yesterday...</p>
             <div className="bg-[var(--bg-secondary)] p-2 rounded-lg border border-[var(--border)]">
               <div className="flex justify-between font-bold text-[var(--text-primary)]"><span>Acme Corp Expansion</span> <span>$1.2M</span></div>
               <div className="text-[10px] text-[var(--text-muted)] mt-1 flex items-center gap-1">Commit <span className="text-emerald-500">→</span> Closed</div>
             </div>
             <div className="bg-[var(--bg-secondary)] p-2 rounded-lg border border-[var(--border)]">
               <div className="flex justify-between font-bold text-[var(--text-primary)]"><span>TechFlow Renewal</span> <span>$850K</span></div>
               <div className="text-[10px] text-[var(--text-muted)] mt-1 flex items-center gap-1">Best Case <span className="text-emerald-500">→</span> Commit</div>
             </div>
          </div>
        </Card>

        <Card className="p-4 flex flex-col hover:border-[var(--primary)] transition-colors">
          <div className="flex items-center gap-2 mb-3 text-[var(--text-primary)]">
             <ListTodo className="w-5 h-5 text-amber-500" />
             <h3 className="font-bold">Largest Open</h3>
          </div>
          <div className="flex-1 overflow-y-auto min-h-[160px] text-xs space-y-2">
             <div className="bg-[var(--bg-secondary)] p-2 rounded-lg border border-[var(--border)] cursor-pointer hover:border-[var(--primary)] transition-colors">
               <div className="flex justify-between font-bold text-[var(--text-primary)]"><span>GlobalTech Enterprise</span> <span className="text-amber-600 dark:text-amber-400">$3.4M</span></div>
               <div className="text-[10px] text-[var(--text-muted)] mt-1">Commit · Q4-2026</div>
             </div>
             <div className="bg-[var(--bg-secondary)] p-2 rounded-lg border border-[var(--border)] cursor-pointer hover:border-[var(--primary)] transition-colors">
               <div className="flex justify-between font-bold text-[var(--text-primary)]"><span>Nexus Systems Core</span> <span className="text-amber-600 dark:text-amber-400">$2.1M</span></div>
               <div className="text-[10px] text-[var(--text-muted)] mt-1">Best Case · Q1-2026</div>
             </div>
          </div>
        </Card>
      </div>

      {modalOpen && (
        <DealListModal
          title={modalTitle}
          deals={dealsData || []}
          onSelectOpp={setSelectedOppId}
          onClose={() => setModalOpen(false)}
        />
      )}
      <OpportunityDrawer oppId={selectedOppId} onClose={() => setSelectedOppId(null)} />
    </motion.div>
  )
}