import React, { useMemo } from 'react'
import { motion } from 'framer-motion'
import {
  DollarSign,
  Target,
  CheckCircle2,
  TrendingUp,
  Briefcase,
  Compass,
  ArrowUpRight,
  ArrowDownRight,
} from 'lucide-react'
import { formatACV, formatCount } from '@/utils/format'
import { Skeleton } from '@/components/ui/Skeleton'

interface SnapshotPoint {
  date: string
  value: number
}

export interface KpiStripItem {
  key: string
  label: string
  value: number
  format?: 'acv' | 'count' | 'pct'
  delta_compare: number | null
  delta_compare_count?: number | null
  delta_compare_label: string
  delta_last_week: number | null
  delta_last_week_count?: number | null
  delta_last_week_label: string
  points: SnapshotPoint[]
  accent: string
}

interface OverviewKpiStripProps {
  kpis: KpiStripItem[]
  loading?: boolean
}

const iconsMap: Record<string, React.ReactNode> = {
  total_acv: <DollarSign className="w-4 h-4" />,
  total_count: <Target className="w-4 h-4" />,
  closed_acv: <CheckCircle2 className="w-4 h-4" />,
  commit_acv: <TrendingUp className="w-4 h-4" />,
  best_case_acv: <Briefcase className="w-4 h-4" />,
  pipeline_acv: <Compass className="w-4 h-4" />,
}

function MiniSparklineWithHistory({
  points,
  color,
}: {
  points: SnapshotPoint[]
  color: string
}) {
  const data = points?.map((p) => p.value) || []
  const count = data.length

  const path = useMemo(() => {
    if (count < 2) return null
    const min = Math.min(...data)
    const max = Math.max(...data)
    const range = max - min || 1
    const width = 68
    const height = 24

    return data
      .map((val, idx) => {
        const x = (idx / (count - 1)) * width
        const y = height - ((val - min) / range) * (height - 6) - 3
        return `${x.toFixed(1)},${y.toFixed(1)}`
      })
      .join(' ')
  }, [data, count])

  if (!path) {
    return (
      <span className="text-[10px] text-[var(--text-muted)] italic">
        1 snapshot
      </span>
    )
  }

  return (
    <div className="flex flex-col items-end">
      <svg className="w-16 h-6 overflow-visible opacity-80" viewBox="0 0 68 24">
        <polyline
          fill="none"
          stroke={color}
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
          points={path}
        />
        {/* Draw a subtle dot on the last point */}
        {data.length > 0 && (
          <circle
            cx="68"
            cy={path.split(' ').pop()?.split(',')[1] || '12'}
            r="2.5"
            fill={color}
          />
        )}
      </svg>
      {count < 7 && (
        <span className="text-[9px] text-[var(--text-muted)] mt-0.5 tracking-tight font-medium">
          {count} snapshots
        </span>
      )}
    </div>
  )
}

function AnimatedTile({ item, idx }: { item: KpiStripItem; idx: number }) {
  const isCount = item.format === 'count'
  const formattedVal = isCount ? formatCount(item.value) : formatACV(item.value)

  const isPosCompare = item.delta_compare != null && item.delta_compare >= 0
  const isPosLW = item.delta_last_week != null && item.delta_last_week >= 0

  const formatDelta = (delta: number | null, countDelta?: number | null) => {
    if (delta == null) return '—'
    const sign = delta >= 0 ? '+' : '-'
    if (isCount) {
      return `${sign}${formatCount(Math.abs(delta))}`
    }
    const acvStr = `${sign}${formatACV(Math.abs(delta))}`
    if (countDelta != null) {
      const cSign = countDelta >= 0 ? '+' : ''
      return `${acvStr} (${cSign}${countDelta})`
    }
    return acvStr
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: idx * 0.05 }}
      whileHover={{ y: -3 }}
      className="card p-4 md:p-5 relative overflow-hidden flex flex-col justify-between group shadow-sm hover:shadow-md transition-all"
    >
      {/* Top accent line */}
      <div
        className="absolute top-0 left-0 right-0 h-[2.5px]"
        style={{
          background: `linear-gradient(90deg, ${item.accent} 0%, rgba(128,128,255,0.7) 60%, transparent 100%)`,
        }}
      />

      {/* Top row: Label, Sparkline, Icon */}
      <div>
        <div className="flex items-start justify-between gap-1 mb-2">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)] truncate">
            {item.label}
          </span>
          <div className="flex items-center gap-2 flex-shrink-0">
            <MiniSparklineWithHistory points={item.points} color={item.accent} />
            <div
              className="w-7 h-7 rounded-lg flex items-center justify-center opacity-85 group-hover:opacity-100 transition-opacity"
              style={{ background: `${item.accent}15`, color: item.accent }}
            >
              {iconsMap[item.key] || <DollarSign className="w-4 h-4" />}
            </div>
          </div>
        </div>

        {/* Big formatted number */}
        <p className="font-extrabold text-2xl lg:text-3xl tracking-tight text-[var(--text-primary)] tabular-nums my-1">
          {formattedVal}
        </p>
      </div>

      {/* Deltas: vs compare date & vs last week */}
      <div className="pt-2 border-t border-[var(--border)] mt-2 flex flex-col gap-1 text-[11px]">
        {/* Delta 1: vs selected compare date */}
        <div className="flex items-center justify-between">
          <span className="text-[var(--text-muted)] truncate">
            {item.delta_compare_label}:
          </span>
          <span
            className={`font-semibold tabular-nums inline-flex items-center gap-0.5 ${
              isPosCompare
                ? 'text-emerald-600 dark:text-emerald-400'
                : 'text-amber-600 dark:text-amber-400'
            }`}
          >
            {isPosCompare ? (
              <ArrowUpRight className="w-3 h-3" />
            ) : (
              <ArrowDownRight className="w-3 h-3" />
            )}
            {formatDelta(item.delta_compare, item.delta_compare_count)}
          </span>
        </div>

        {/* Delta 2: vs last week */}
        {item.delta_last_week != null && (
          <div className="flex items-center justify-between text-[10.5px]">
            <span className="text-[var(--text-muted)] truncate">
              {item.delta_last_week_label}:
            </span>
            <span
              className={`font-medium tabular-nums inline-flex items-center gap-0.5 ${
                isPosLW
                  ? 'text-emerald-600/90 dark:text-emerald-400/90'
                  : 'text-amber-600/90 dark:text-amber-400/90'
              }`}
            >
              {formatDelta(item.delta_last_week, item.delta_last_week_count)}
            </span>
          </div>
        )}
      </div>
    </motion.div>
  )
}

export default function OverviewKpiStrip({
  kpis = [],
  loading = false,
}: OverviewKpiStripProps) {
  if (loading || kpis.length === 0) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3.5">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="card p-4 space-y-3">
            <Skeleton variant="text" width="60%" height="12px" />
            <Skeleton variant="text" width="85%" height="28px" />
            <Skeleton variant="text" width="70%" height="10px" />
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3.5">
      {kpis.map((item, idx) => (
        <AnimatedTile key={item.key} item={item} idx={idx} />
      ))}
    </div>
  )
}
