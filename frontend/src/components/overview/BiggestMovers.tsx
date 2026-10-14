import React from 'react'
import { motion } from 'framer-motion'
import { ArrowUpRight, ArrowDownRight, Plus, Minus, ArrowRight, ExternalLink } from 'lucide-react'
import { formatACV } from '@/utils/format'
import { ForecastBadge, ApprovalBadge } from '@/components/ui/Badge'

export interface MoverItem {
  opportunity_id_18: string
  opportunity_name: string
  account_name: string
  tag: 'New' | 'Increase' | 'Decrease' | 'Removed'
  old_acv: number
  new_acv: number
  acv_diff: number
  abs_diff: number
  forecast_category?: string
  approval_status?: string
}

interface BiggestMoversProps {
  movers?: MoverItem[]
  onSelectOpportunity?: (oppId: string) => void
  loading?: boolean
}

export default function BiggestMovers({
  movers = [],
  onSelectOpportunity,
  loading = false,
}: BiggestMoversProps) {
  if (loading) {
    return (
      <div className="card p-6">
        <h2 className="font-bold text-lg text-[var(--text-primary)] mb-4">
          Biggest ACV Movers
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="p-4 rounded-xl border border-[var(--border)] skeleton-shimmer h-28" />
          ))}
        </div>
      </div>
    )
  }

  const tagConfig: Record<
    string,
    { bg: string; text: string; border: string; icon: React.ReactNode }
  > = {
    New: {
      bg: 'bg-emerald-500/10 dark:bg-emerald-500/20',
      text: 'text-emerald-600 dark:text-emerald-400',
      border: 'border-emerald-500/20',
      icon: <Plus className="w-3 h-3" />,
    },
    Increase: {
      bg: 'bg-teal-500/10 dark:bg-teal-500/20',
      text: 'text-teal-600 dark:text-teal-400',
      border: 'border-teal-500/20',
      icon: <ArrowUpRight className="w-3 h-3" />,
    },
    Decrease: {
      bg: 'bg-amber-500/10 dark:bg-amber-500/20',
      text: 'text-amber-600 dark:text-amber-400',
      border: 'border-amber-500/20',
      icon: <ArrowDownRight className="w-3 h-3" />,
    },
    Removed: {
      bg: 'bg-rose-500/10 dark:bg-rose-500/20',
      text: 'text-rose-600 dark:text-rose-400',
      border: 'border-rose-500/20',
      icon: <Minus className="w-3 h-3" />,
    },
  }

  return (
    <div className="card p-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 mb-5">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="font-bold text-lg text-[var(--text-primary)]">
              Biggest ACV Movers
            </h2>
            <span className="text-xs px-2.5 py-0.5 rounded-sm font-semibold bg-violet-500/10 text-violet-600 dark:text-violet-400 border border-violet-500/20">
              Top 10
            </span>
          </div>
          <p className="text-xs text-[var(--text-muted)] mt-0.5">
            Largest shifts by absolute deal value. Click any card to inspect the full timeline.
          </p>
        </div>
      </div>

      {movers.length === 0 ? (
        <div className="py-12 text-center text-xs text-[var(--text-muted)]">
          No significant ACV movements between selected snapshots.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
          {movers.map((m, idx) => {
            const conf = tagConfig[m.tag] || tagConfig.Increase
            const maxVal = Math.max(m.old_acv, m.new_acv, 1)
            const oldWidthPct = Math.max((m.old_acv / maxVal) * 100, m.old_acv > 0 ? 6 : 0)
            const newWidthPct = Math.max((m.new_acv / maxVal) * 100, m.new_acv > 0 ? 6 : 0)

            return (
              <motion.div
                key={m.opportunity_id_18 || idx}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: idx * 0.04 }}
                whileHover={{ y: -2 }}
                onClick={() => onSelectOpportunity?.(m.opportunity_id_18)}
                className="p-4 rounded-md border border-[var(--border)] bg-[var(--bg-secondary)] hover:border-teal-500/50 hover:bg-[var(--bg-card)] transition-all cursor-pointer group shadow-sm flex flex-col justify-between"
              >
                {/* Top: Name, Account, and Tag */}
                <div>
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="min-w-0">
                      <p className="font-semibold text-xs md:text-sm text-[var(--text-primary)] group-hover:text-teal-600 dark:group-hover:text-teal-400 truncate transition-colors">
                        {m.opportunity_name || m.opportunity_id_18}
                      </p>
                      <p className="text-[11px] text-[var(--text-muted)] truncate mt-0.5">
                        {m.account_name || 'N/A'}
                      </p>
                    </div>

                    <span
                      className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-sm text-[11px] font-bold border flex-shrink-0 ${conf.bg} ${conf.text} ${conf.border}`}
                    >
                      {conf.icon}
                      {m.tag}
                    </span>
                  </div>

                  {/* Old -> New Mini Bar */}
                  <div className="my-3 space-y-1.5 p-2.5 rounded-xl bg-[var(--bg-card)] border border-[var(--border)]">
                    {/* Old bar */}
                    <div className="flex items-center gap-2 text-[10.5px]">
                      <span className="w-8 text-[var(--text-muted)]">Old</span>
                      <div className="flex-1 h-2 rounded-full bg-[var(--bg-secondary)] overflow-hidden">
                        <div
                          className="h-full rounded-full bg-slate-400 dark:bg-slate-500"
                          style={{ width: `${oldWidthPct}%` }}
                        />
                      </div>
                      <span className="font-medium text-[var(--text-muted)] tabular-nums w-16 text-right">
                        {formatACV(m.old_acv)}
                      </span>
                    </div>

                    {/* New bar */}
                    <div className="flex items-center gap-2 text-[10.5px]">
                      <span className="w-8 font-semibold text-[var(--text-primary)]">New</span>
                      <div className="flex-1 h-2 rounded-full bg-[var(--bg-secondary)] overflow-hidden">
                        <div
                          className={`h-full rounded-full ${
                            m.acv_diff >= 0 ? 'bg-teal-500' : 'bg-amber-500'
                          }`}
                          style={{ width: `${newWidthPct}%` }}
                        />
                      </div>
                      <span className="font-bold text-[var(--text-primary)] tabular-nums w-16 text-right">
                        {formatACV(m.new_acv)}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Bottom: Delta & Details */}
                <div className="flex items-center justify-between pt-2 border-t border-[var(--border)] text-xs">
                  <div className="flex items-center gap-1.5">
                    {m.forecast_category && (
                      <ForecastBadge category={m.forecast_category} />
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    <span
                      className={` font-extrabold text-xs md:text-sm tabular-nums ${
                        m.acv_diff >= 0
                          ? 'text-emerald-600 dark:text-emerald-400'
                          : 'text-amber-600 dark:text-amber-400'
                      }`}
                    >
                      {m.acv_diff >= 0 ? '+' : ''}
                      {formatACV(m.acv_diff)}
                    </span>
                    <ArrowRight className="w-3.5 h-3.5 text-[var(--text-muted)] group-hover:text-teal-500 group-hover:translate-x-0.5 transition-all" />
                  </div>
                </div>
              </motion.div>
            )
          })}
        </div>
      )}
    </div>
  )
}
