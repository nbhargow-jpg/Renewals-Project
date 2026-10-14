import React from 'react'
import clsx from 'clsx'

export interface KpiCardProps {
  title: string
  count?: number | null
  acv?: number | null
  icon: React.ElementType
  accentColor?: 'amber' | 'rose' | 'slate' | 'teal' | 'indigo' | 'emerald'
  delta?: React.ReactNode
  onClick?: () => void
  metricMode?: 'Amount' | 'Count' | 'Both'
  className?: string
}

export function KpiCard({
  title,
  count,
  acv,
  icon: Icon,
  accentColor = 'teal',
  delta,
  onClick,
  metricMode = 'Both',
  className,
}: KpiCardProps) {
  // 4px left accent bar colors
  const accentBorderMap = {
    amber: 'border-l-amber-500',
    rose: 'border-l-rose-500',
    slate: 'border-l-slate-400',
    teal: 'border-l-[#00A3AD]',
    indigo: 'border-l-indigo-500',
    emerald: 'border-l-emerald-500',
  }

  // 32px rounded-lg icon tile colors with soft tint
  const iconTileMap = {
    amber: 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
    rose: 'bg-rose-500/10 text-rose-600 dark:text-rose-400',
    slate: 'bg-slate-500/10 text-slate-600 dark:text-slate-300',
    teal: 'bg-[#00A3AD]/10 text-[#00A3AD]',
    indigo: 'bg-indigo-500/10 text-indigo-600 dark:text-indigo-400',
    emerald: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  }

  return (
    <div
      onClick={onClick}
      className={clsx(
        'rounded-xl bg-[var(--bg-card)] border border-[var(--border)] border-l-4 shadow-[var(--card-shadow)]',
        accentBorderMap[accentColor],
        'p-5 flex flex-col justify-between h-full items-stretch transition-colors select-none',
        onClick && 'cursor-pointer hover:border-[var(--brand-teal)] hover:bg-[var(--bg-secondary)]/50',
        className
      )}
    >
      <div>
        {/* Header: Title and small 32px rounded-lg icon tile */}
        <div className="flex items-center justify-between gap-2 mb-3">
          <span className="text-xs font-medium text-[var(--text-muted)] truncate">
            {title}
          </span>
          <div className={clsx('w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0', iconTileMap[accentColor])}>
            <Icon className="w-4 h-4" strokeWidth={1.75} />
          </div>
        </div>

        {/* Value: Aligned baseline across all cards */}
        <div className="space-y-0.5 mb-3">
          {(metricMode === 'Count' || metricMode === 'Both') && count != null && (
            <div className="text-2xl font-semibold tracking-tight text-[var(--text-primary)] tabular-nums">
              {count.toLocaleString('en-US')}
            </div>
          )}
          {(metricMode === 'Amount' || metricMode === 'Both') && acv != null && (
            <div className="text-sm font-medium text-[var(--text-muted)] tabular-nums">
              ${(acv).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
          )}
        </div>
      </div>

      {/* Delta Row */}
      {delta && (
        <div className="pt-2 border-t border-[var(--border-subtle)] flex items-center gap-1.5 flex-wrap">
          {delta}
        </div>
      )}
    </div>
  )
}

export default KpiCard
