import React from 'react'
import { formatACV, formatCount } from '@/utils/format'
import { clsx } from 'clsx'

export interface DeltaChipProps {
  value: number | null | undefined
  previousValue?: number | null
  label?: string
  showIcon?: boolean
  isCurrency?: boolean
  isBadDirectionIncrease?: boolean // if true, increase is bad (e.g. delays/slippage)
  size?: 'sm' | 'md'
  className?: string
}

export default function DeltaChip({
  value,
  previousValue,
  label,
  showIcon = true,
  isCurrency = false,
  isBadDirectionIncrease = false,
  size = 'md',
  className,
}: DeltaChipProps) {
  if (value == null) return null
  const isZero = value === 0
  const isPositive = value > 0

  const formattedValue = isCurrency
    ? formatACV(Math.abs(value))
    : formatCount(Math.abs(value))

  const pct =
    previousValue != null && previousValue !== 0
      ? ((Math.abs(value) / Math.abs(previousValue)) * 100).toFixed(1)
      : null

  const sizeClasses = size === 'sm' ? 'text-[10px] px-1.5 py-0.5' : 'text-xs px-2 py-0.5'

  // Soft muted tint styling per design correction
  let colorClasses = 'bg-slate-100 text-slate-700 dark:bg-slate-800/60 dark:text-[#8A9BB5]'
  if (!isZero) {
    if (isBadDirectionIncrease) {
      // bad direction: increase -> rose-50/rose-700; decrease -> emerald-50/emerald-700
      colorClasses = isPositive
        ? 'bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-400'
        : 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400'
    } else {
      // standard: increase -> emerald-50/emerald-700; decrease -> rose-50/rose-700
      colorClasses = isPositive
        ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400'
        : 'bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-400'
    }
  }

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 font-medium rounded-sm select-none tabular-nums transition-colors',
        sizeClasses,
        colorClasses,
        className
      )}
    >
      {showIcon && !isZero && <span>{isPositive ? '▲' : '▼'}</span>}
      <span>{isPositive ? '+' : isZero ? '' : '-'}{formattedValue}</span>
      {pct && <span className="opacity-75 font-normal">({pct}%)</span>}
      {label && <span className="opacity-70">{label}</span>}
    </span>
  )
}
