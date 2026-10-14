import React from 'react'
import { motion } from 'framer-motion'
import { Sparkles, TrendingUp, TrendingDown, ArrowUpRight, ArrowDownRight, AlertTriangle, CheckCircle, Info } from 'lucide-react'

interface InsightChip {
  label: string
  value: string
  type?: 'positive' | 'negative' | 'warning' | 'neutral'
}

interface HeadlineBannerProps {
  headlineText?: string
  chips?: InsightChip[]
  compareLabel?: string
  loading?: boolean
}

export default function HeadlineBanner({
  headlineText,
  chips = [],
  compareLabel = 'yesterday',
  loading = false,
}: HeadlineBannerProps) {
  if (loading) {
    return (
      <div className="rounded-md p-6 bg-[#12284C] animate-pulse h-36 border border-[var(--border)]" />
    )
  }

  const defaultText = `ACV is tracking firmly since ${compareLabel}. View category transitions and waterfall breakdown below.`

  return (
    <div
      className="relative rounded-md p-5 md:p-6 overflow-hidden border border-[#1B365D] bg-[#12284C] text-white"
    >
      <div className="relative z-10 max-w-5xl">
        {/* Subtle executive badge */}
        <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm bg-white/10 border border-white/15 mb-3">
          <Sparkles className="w-3 h-3 text-[#00A3AD]" />
          <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-200">
            Executive Shift Summary
          </span>
        </div>

        {/* Dynamic hero headline sentence */}
        <h1 className="font-semibold text-lg md:text-xl text-white tracking-tight leading-snug">
          {headlineText || defaultText}
        </h1>

        {/* Secondary insight chips */}
        {chips.length > 0 && (
          <div className="flex flex-wrap items-center gap-2.5 mt-5">
            {chips.map((chip, idx) => {
              const isPositive = chip.type === 'positive'
              const isWarning = chip.type === 'warning'
              const isNegative = chip.type === 'negative'

              return (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.15 + idx * 0.08 }}
                  className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-xl bg-white/10 hover:bg-white/15 border border-white/15 transition-all text-xs text-white/95 shadow-sm"
                >
                  {isPositive && <CheckCircle className="w-3.5 h-3.5 text-emerald-300" />}
                  {isWarning && <AlertTriangle className="w-3.5 h-3.5 text-amber-300" />}
                  {isNegative && <TrendingDown className="w-3.5 h-3.5 text-rose-300" />}
                  {!isPositive && !isWarning && !isNegative && (
                    <Info className="w-3.5 h-3.5 text-cyan-200" />
                  )}

                  <span className="text-white/75 font-medium">{chip.label}:</span>
                  <span className="font-bold text-white tabular-nums">{chip.value}</span>
                </motion.div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
