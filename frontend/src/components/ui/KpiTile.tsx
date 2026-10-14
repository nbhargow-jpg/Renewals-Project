import { useEffect, useRef, useState, useMemo } from 'react'
import { motion } from 'framer-motion'
import { formatACV, formatCount } from '@/utils/format'
import type { ReactNode } from 'react'

interface KpiTileProps {
  label: string
  value: number | null | undefined
  format?: 'acv' | 'count' | 'pct'
  delta?: number | null
  deltaLabel?: string
  caption?: string
  icon?: ReactNode
  accent?: string
  sparklineData?: number[]
  loading?: boolean
}

function useCountUp(target: number, duration = 800) {
  const [current, setCurrent] = useState(0)
  const raf = useRef<number>(0)

  useEffect(() => {
    if (target === 0) {
      setCurrent(0)
      return
    }
    const start = performance.now()
    const step = (now: number) => {
      const progress = Math.min((now - start) / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3) // ease-out cubic
      setCurrent(target * eased)
      if (progress < 1) raf.current = requestAnimationFrame(step)
    }
    raf.current = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf.current)
  }, [target, duration])

  return current
}

function MiniSparkline({ data, color }: { data: number[]; color: string }) {
  const points = useMemo(() => {
    if (!data || data.length < 2) return null
    const min = Math.min(...data)
    const max = Math.max(...data)
    const range = max - min || 1
    const width = 64
    const height = 24

    return data
      .map((val, idx) => {
        const x = (idx / (data.length - 1)) * width
        const y = height - ((val - min) / range) * (height - 6) - 3
        return `${x.toFixed(1)},${y.toFixed(1)}`
      })
      .join(' ')
  }, [data])

  if (!points) return null

  return (
    <svg className="w-16 h-6 overflow-visible opacity-70" viewBox="0 0 64 24">
      <polyline
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
      />
    </svg>
  )
}

export default function KpiTile({
  label,
  value,
  format = 'acv',
  delta,
  deltaLabel,
  caption,
  icon,
  accent = '#00A3AD',
  sparklineData,
  loading = false,
}: KpiTileProps) {
  const animated = useCountUp(value ?? 0)

  const display = () => {
    if (format === 'acv') return formatACV(animated)
    if (format === 'count') return formatCount(Math.round(animated))
    if (format === 'pct') return `${animated.toFixed(1)}%`
    return '—'
  }

  // Default mock sparkline if none provided
  const sparkData = useMemo(() => {
    if (sparklineData && sparklineData.length >= 2) return sparklineData
    const base = value ?? 50
    return [base * 0.92, base * 0.95, base * 0.91, base * 0.98, base * 0.97, base * 1.0]
  }, [sparklineData, value])

  if (loading) {
    return (
      <div className="card p-4 space-y-3">
        <div className="skeleton-shimmer h-3.5 w-24" />
        <div className="skeleton-shimmer h-8 w-36" />
        <div className="skeleton-shimmer h-3 w-28" />
      </div>
    )
  }

  const isPositive = delta != null && delta >= 0

  return (
    <div className="card p-4 relative overflow-hidden">
      {/* Header with label & sparkline */}
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <p className="text-xs font-medium text-[var(--text-muted)] truncate">
          {label}
        </p>
        <div className="flex items-center gap-2 flex-shrink-0">
          <MiniSparkline data={sparkData} color={accent} />
          {icon && (
            <div className="text-[var(--text-muted)]">
              {icon}
            </div>
          )}
        </div>
      </div>

      {/* Value: 24px semibold with tabular numerals */}
      <p className="font-semibold text-2xl tracking-tight tabular-nums text-[var(--text-primary)]">
        {display()}
      </p>

      {/* Delta chip: Green up / Red down, 6px radius */}
      <div className="flex items-center gap-2 mt-2 flex-wrap">
        {delta != null && (
          <div
            className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm text-xs font-medium tabular-nums border ${
              isPositive
                ? 'bg-green-500/10 text-green-700 dark:text-green-400 border-green-500/20'
                : 'bg-red-500/10 text-red-700 dark:text-red-400 border-red-500/20'
            }`}
          >
            <span>{isPositive ? '▲' : '▼'}</span>
            <span>
              {format === 'count'
                ? Math.abs(delta).toLocaleString('en-US')
                : formatACV(Math.abs(delta), false)}
            </span>
          </div>
        )}

        <span className="text-xs text-[var(--text-muted)]">
          {deltaLabel ?? 'vs yesterday'}
        </span>
      </div>

      {caption && (
        <p className="mt-2 text-xs text-[var(--text-muted)] border-t border-[var(--border-subtle)] pt-1.5 leading-snug">
          {caption}
        </p>
      )}
    </div>
  )
}
