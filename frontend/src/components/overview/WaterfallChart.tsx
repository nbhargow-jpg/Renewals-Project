import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  CheckCircle,
  PlusCircle,
  TrendingUp,
  TrendingDown,
  MinusCircle,
  Layers,
  ArrowRight,
  Info,
  X,
  ExternalLink,
} from 'lucide-react'
import { formatACV, formatCount } from '@/utils/format'
import { Card } from '@/components/ui/Card'
import Drawer from '@/components/ui/Drawer'
import Badge, { ForecastBadge, ApprovalBadge } from '@/components/ui/Badge'

export interface WaterfallData {
  start_acv: number
  start_count: number
  new_acv: number
  new_count: number
  new_opportunities: any[]
  increases_acv: number
  increases_count: number
  increase_opportunities: any[]
  decreases_acv: number
  decreases_count: number
  decrease_opportunities: any[]
  removed_acv: number
  removed_count: number
  removed_opportunities: any[]
  end_acv: number
  end_count: number
  reconciled_acv: number
  is_reconciled: boolean
}

interface WaterfallChartProps {
  data?: WaterfallData
  fromLabel?: string
  toLabel?: string
  onSelectOpportunity?: (oppId: string) => void
  loading?: boolean
}

interface BarStage {
  id: 'start' | 'new' | 'increases' | 'decreases' | 'removed' | 'end'
  label: string
  sublabel: string
  type: 'total' | 'positive' | 'negative'
  amount: number
  count: number
  opps: any[]
  color: string
  startVal: number
  endVal: number
}

export default function WaterfallChart({
  data,
  fromLabel = 'Compare Date',
  toLabel = 'Selected Date',
  onSelectOpportunity,
  loading = false,
}: WaterfallChartProps) {
  const [selectedBar, setSelectedBar] = useState<BarStage | null>(null)
  const [hoveredBar, setHoveredBar] = useState<string | null>(null)

  if (loading || !data) {
    return (
      <div className="card p-6 h-96 flex items-center justify-center">
        <div className="skeleton-shimmer w-full h-full rounded-md" />
      </div>
    )
  }

  // Calculate cumulative steps for visual height
  const start = data.start_acv
  const stepNew = start + data.new_acv
  const stepInc = stepNew + data.increases_acv
  const stepDec = stepInc - data.decreases_acv
  const stepRem = stepDec - data.removed_acv
  const end = data.end_acv

  const stages: BarStage[] = [
    {
      id: 'start',
      label: `${fromLabel} ACV`,
      sublabel: 'Baseline total',
      type: 'total',
      amount: start,
      count: data.start_count,
      opps: [],
      color: '#334155', // Slate
      startVal: 0,
      endVal: start,
    },
    {
      id: 'new',
      label: 'New Opportunities',
      sublabel: 'Net additions',
      type: 'positive',
      amount: data.new_acv,
      count: data.new_count,
      opps: data.new_opportunities,
      color: '#10B981', // Emerald
      startVal: start,
      endVal: stepNew,
    },
    {
      id: 'increases',
      label: 'ACV Increases',
      sublabel: 'Deal expansions',
      type: 'positive',
      amount: data.increases_acv,
      count: data.increases_count,
      opps: data.increase_opportunities,
      color: '#00A3AD', // Brand Teal
      startVal: stepNew,
      endVal: stepInc,
    },
    {
      id: 'decreases',
      label: 'ACV Decreases',
      sublabel: 'Reductions',
      type: 'negative',
      amount: data.decreases_acv,
      count: data.decreases_count,
      opps: data.decrease_opportunities,
      color: '#F59E0B', // Amber
      startVal: stepInc,
      endVal: stepDec,
    },
    {
      id: 'removed',
      label: 'Removed Deals',
      sublabel: 'Lapsed or closed out',
      type: 'negative',
      amount: data.removed_acv,
      count: data.removed_count,
      opps: data.removed_opportunities,
      color: '#EF4444', // Rose/Red
      startVal: stepDec,
      endVal: stepRem,
    },
    {
      id: 'end',
      label: `${toLabel} ACV`,
      sublabel: 'Final reconciled total',
      type: 'total',
      amount: end,
      count: data.end_count,
      opps: [],
      color: '#12284C', // Brand Navy
      startVal: 0,
      endVal: end,
    },
  ]

  // Find max value to calibrate bar heights
  const maxScale = Math.max(start, end, stepInc, stepNew) * 1.08 || 1

  return (
    <div className="card p-6">
      {/* Header with Title and Reconciled Badge */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="font-bold text-lg text-[var(--text-primary)]">
              ACV Movement Waterfall
            </h2>
            <span className="text-xs px-2.5 py-0.5 rounded-sm font-semibold bg-teal-500/10 text-teal-600 dark:text-teal-400 border border-teal-500/20">
              Interactive
            </span>
          </div>
          <p className="text-xs text-[var(--text-muted)] mt-0.5">
            Exact bridge from {fromLabel} to {toLabel}. Click any component to inspect the underlying deals.
          </p>
        </div>

        {/* Reconciliation Check Badge */}
        <div
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-semibold tabular-nums ${
            data.is_reconciled
              ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20'
              : 'bg-rose-500/10 text-rose-600 border-rose-500/20'
          }`}
        >
          <CheckCircle className="w-4 h-4 flex-shrink-0" />
          <span>
            {data.is_reconciled
              ? `Reconciled: ${formatACV(data.reconciled_acv)}`
              : 'Unreconciled Variance'}
          </span>
        </div>
      </div>

      {/* Main Chart Area */}
      <div className="h-64 flex items-end gap-2 md:gap-4 pt-6 pb-2 border-b border-[var(--border)] px-2">
        {stages.map((stage) => {
          const isTotal = stage.type === 'total'
          const isNegative = stage.type === 'negative'
          const isHovered = hoveredBar === stage.id

          // Visual bar height and bottom offset
          const barHeightPct = Math.max(
            (stage.amount / maxScale) * 100,
            stage.amount > 0 ? 3 : 0
          )
          const bottomPct = isTotal
            ? 0
            : isNegative
            ? (stage.endVal / maxScale) * 100
            : (stage.startVal / maxScale) * 100

          const hasOpps = stage.opps.length > 0

          return (
            <div
              key={stage.id}
              className="flex-1 h-full flex flex-col justify-end items-center relative group cursor-pointer"
              onMouseEnter={() => setHoveredBar(stage.id)}
              onMouseLeave={() => setHoveredBar(null)}
              onClick={() => {
                if (hasOpps) setSelectedBar(stage)
              }}
            >
              {/* Tooltip on hover */}
              <AnimatePresence>
                {isHovered && (
                  <motion.div
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 6 }}
                    className="absolute -top-12 z-20 px-2.5 py-1.5 rounded-lg bg-[var(--bg-card)] border border-[var(--border)] shadow-xl text-center pointer-events-none whitespace-nowrap"
                  >
                    <p className="text-[11px] font-bold text-[var(--text-primary)] tabular-nums">
                      {formatACV(stage.amount)}
                    </p>
                    <p className="text-[10px] text-[var(--text-muted)]">
                      {stage.count} {stage.count === 1 ? 'deal' : 'deals'}
                      {hasOpps && ' • Click to view'}
                    </p>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Bar Column Container */}
              <div className="w-full relative h-full flex items-end">
                <div
                  className="w-full rounded-t-lg transition-all relative overflow-hidden"
                  style={{
                    height: `${barHeightPct}%`,
                    marginBottom: `${bottomPct}%`,
                    backgroundColor: stage.color,
                    boxShadow: isHovered
                      ? `0 0 16px ${stage.color}60`
                      : 'none',
                    opacity: isHovered || !hoveredBar ? 1 : 0.6,
                  }}
                >
                  {/* Subtle glass reflection highlight */}
                  <div className="absolute inset-0 pointer-events-none" />
                </div>
              </div>

              {/* Amount Label above / below */}
              <div className="mt-2 text-center">
                <span className="font-bold text-xs md:text-sm text-[var(--text-primary)] tabular-nums block">
                  {stage.type === 'negative' && stage.amount > 0 ? '-' : ''}
                  {formatACV(stage.amount)}
                </span>
                <span className="text-[10px] text-[var(--text-muted)] font-medium hidden md:block truncate max-w-[85px]">
                  {stage.label}
                </span>
              </div>
            </div>
          )
        })}
      </div>

      {/* Explanatory Caption / Legend */}
      <div className="flex flex-wrap items-center justify-between gap-3 mt-4 text-xs text-[var(--text-muted)]">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-[#10B981]" />
            <span>New Adds</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-[#00A3AD]" />
            <span>Increases</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-[#F59E0B]" />
            <span>Decreases</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-[#EF4444]" />
            <span>Removed</span>
          </div>
        </div>
        <span className="text-[11px] italic">
          Click any bar to inspect underlying opportunity records
        </span>
      </div>

      {/* Slide-out Drawer for Bar Opportunity Drilldown */}
      <Drawer
        isOpen={!!selectedBar}
        onClose={() => setSelectedBar(null)}
        title={`${selectedBar?.label || ''} Breakdown`}
        subtitle={`${selectedBar?.count ?? 0} opportunities totaling ${formatACV(
          selectedBar?.amount ?? 0
        )}`}
        size="md"
      >
        <div className="space-y-3">
          {selectedBar?.opps.map((o: any, idx: number) => {
            const hasDiff = o.acv_diff != null
            return (
              <div
                key={o.opportunity_id_18 || idx}
                onClick={() => {
                  setSelectedBar(null)
                  onSelectOpportunity?.(o.opportunity_id_18)
                }}
                className="p-3.5 rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] hover:border-teal-500/50 hover:bg-[var(--bg-card)] transition-all cursor-pointer group shadow-sm"
              >
                <div className="flex items-start justify-between gap-2 mb-1">
                  <div className="min-w-0">
                    <p className="font-semibold text-xs text-[var(--text-primary)] group-hover:text-teal-600 dark:group-hover:text-teal-400 truncate">
                      {o.opportunity_name || o.opportunity_id_18}
                    </p>
                    <p className="text-[11px] text-[var(--text-muted)] truncate">
                      {o.account_name || 'N/A'}
                    </p>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <p className="font-bold text-xs text-[var(--text-primary)] tabular-nums">
                      {formatACV(o.new_acv ?? o.acv ?? 0)}
                    </p>
                    {hasDiff && (
                      <p
                        className={`text-[10px] font-semibold tabular-nums ${
                          o.acv_diff >= 0 ? 'text-emerald-500' : 'text-amber-500'
                        }`}
                      >
                        {o.acv_diff >= 0 ? '+' : ''}
                        {formatACV(o.acv_diff)}
                      </p>
                    )}
                  </div>
                </div>

                <div className="flex items-center justify-between pt-2 border-t border-[var(--border)] text-[10.5px]">
                  <div className="flex items-center gap-1.5">
                    <ForecastBadge category={o.forecast_category ?? 'Blank'} />
                    <ApprovalBadge status={o.approval_status ?? 'Blank'} />
                  </div>
                  <span className="text-teal-600 dark:text-teal-400 font-semibold inline-flex items-center gap-0.5 group-hover:translate-x-0.5 transition-transform">
                    View timeline <ArrowRight className="w-3 h-3" />
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      </Drawer>
    </div>
  )
}
