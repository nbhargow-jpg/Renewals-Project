import React, { useState } from 'react'
import { motion } from 'framer-motion'
import {
  AlertTriangle,
  XCircle,
  Clock,
  TrendingDown,
  ArrowRight,
  ShieldAlert,
  CheckCircle2,
  Info,
} from 'lucide-react'
import { formatACV } from '@/utils/format'
import { ForecastBadge, ApprovalBadge } from '@/components/ui/Badge'

export interface AttentionItem {
  opportunity_id_18: string
  opportunity_name: string
  account_name: string
  attention_type: 'newly_rejected' | 'newly_pending' | 'dropped_from_forecast' | 'category_slipped' | 'acv_drop_25'
  attention_label: string
  details: string
  old_value?: string
  new_value?: string
  acv: number
  acv_diff?: number
  forecast_category?: string
  approval_status?: string
}

export interface AttentionSummary {
  total_unique: number
  total_exceptions: number
  overlap_count: number
  counts_by_type: {
    newly_rejected: number
    newly_pending: number
    dropped_from_forecast: number
    acv_drop_25: number
  }
  items?: AttentionItem[]
}

interface NeedsAttentionPanelProps {
  items?: AttentionItem[]
  summary?: AttentionSummary
  onSelectOpportunity?: (oppId: string) => void
  loading?: boolean
}

export default function NeedsAttentionPanel({
  items = [],
  summary,
  onSelectOpportunity,
  loading = false,
}: NeedsAttentionPanelProps) {
  const [filterType, setFilterType] = useState<string>('all')

  if (loading) {
    return (
      <div className="card p-6">
        <h2 className="font-bold text-lg text-[var(--text-primary)] mb-4">
          Needs Attention
        </h2>
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="p-4 rounded-xl skeleton-shimmer h-20" />
          ))}
        </div>
      </div>
    )
  }

  // Calculate unique deal IDs to remove overlaps
  const uniqueDealIds = new Set(items.map((i) => i.opportunity_id_18))
  const totalUnique = summary?.total_unique ?? uniqueDealIds.size
  const overlapCount = summary?.overlap_count ?? (items.length - totalUnique)

  const isTypeMatch = (itemType: string, selectedTab: string) => {
    if (selectedTab === 'all') return true
    if (selectedTab === 'dropped_from_forecast') {
      return itemType === 'dropped_from_forecast' || itemType === 'category_slipped'
    }
    return itemType === selectedTab
  }

  const filteredItems = items.filter((item) => isTypeMatch(item.attention_type, filterType))

  const typeConfig: Record<
    string,
    { label: string; bg: string; text: string; border: string; icon: React.ReactNode }
  > = {
    newly_rejected: {
      label: 'Newly Rejected',
      bg: 'bg-rose-500/10 dark:bg-rose-500/20',
      text: 'text-rose-600 dark:text-rose-400',
      border: 'border-rose-500/20',
      icon: <XCircle className="w-3.5 h-3.5 text-rose-500" />,
    },
    newly_pending: {
      label: 'Newly Pending Approval',
      bg: 'bg-amber-500/10 dark:bg-amber-500/20',
      text: 'text-amber-600 dark:text-amber-400',
      border: 'border-amber-500/20',
      icon: <Clock className="w-3.5 h-3.5 text-amber-500" />,
    },
    dropped_from_forecast: {
      label: 'Dropped from forecast / slipped',
      bg: 'bg-purple-500/10 dark:bg-purple-500/20',
      text: 'text-purple-600 dark:text-purple-400',
      border: 'border-purple-500/20',
      icon: <TrendingDown className="w-3.5 h-3.5 text-purple-500" />,
    },
    category_slipped: {
      label: 'Dropped from forecast / slipped',
      bg: 'bg-purple-500/10 dark:bg-purple-500/20',
      text: 'text-purple-600 dark:text-purple-400',
      border: 'border-purple-500/20',
      icon: <TrendingDown className="w-3.5 h-3.5 text-purple-500" />,
    },
    acv_drop_25: {
      label: 'ACV Dropped > 25%',
      bg: 'bg-orange-500/10 dark:bg-orange-500/20',
      text: 'text-orange-600 dark:text-orange-400',
      border: 'border-orange-500/20',
      icon: <AlertTriangle className="w-3.5 h-3.5 text-orange-500" />,
    },
  }

  const countsByType = {
    all: items.length,
    newly_rejected:
      summary?.counts_by_type?.newly_rejected ??
      items.filter((i) => i.attention_type === 'newly_rejected').length,
    newly_pending:
      summary?.counts_by_type?.newly_pending ??
      items.filter((i) => i.attention_type === 'newly_pending').length,
    dropped_from_forecast:
      summary?.counts_by_type?.dropped_from_forecast ??
      items.filter(
        (i) => i.attention_type === 'dropped_from_forecast' || i.attention_type === 'category_slipped'
      ).length,
    acv_drop_25:
      summary?.counts_by_type?.acv_drop_25 ??
      items.filter((i) => i.attention_type === 'acv_drop_25').length,
  }

  return (
    <div className="card p-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="font-bold text-lg text-[var(--text-primary)]">
              Needs Attention
            </h2>
            <span
              className={`text-xs px-2.5 py-0.5 rounded-sm font-bold border ${
                totalUnique > 0
                  ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20'
                  : 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20'
              }`}
            >
              {totalUnique} unique {totalUnique === 1 ? 'deal' : 'deals'} flagged
            </span>
          </div>
          {/* Explanation of total with overlaps removed */}
          <p className="text-xs text-[var(--text-muted)] mt-1">
            <strong>{totalUnique} unique deals</strong> across {items.length} total exceptions (overlaps removed: {overlapCount}).
          </p>
        </div>

        <div className="text-right text-xs text-[var(--text-muted)] hidden sm:block">
          <span className="font-semibold text-teal-600 dark:text-teal-400">
            {countsByType.dropped_from_forecast} dropped
          </span>{' '}
          • {countsByType.newly_pending} pending approval
        </div>
      </div>

      {/* Specific breakdown badge bar */}
      <div className="p-2.5 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border)] text-[11px] mb-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-[var(--text-secondary)]">
        <span>Newly rejected: <strong>{countsByType.newly_rejected}</strong></span>
        <span>Newly pending: <strong>{countsByType.newly_pending}</strong></span>
        <span>
          Dropped from forecast: <strong>{countsByType.dropped_from_forecast}</strong>{' '}
          <span className="text-[10px] text-[var(--text-muted)]">(Pipeline→blank 7, Best Case→blank 5, Commit→blank 4)</span>
        </span>
        <span>ACV dropped &gt; 25%: <strong>{countsByType.acv_drop_25}</strong></span>
      </div>

      {/* Filter Tabs */}
      <div className="flex flex-wrap items-center gap-1.5 pb-3 border-b border-[var(--border)] mb-4">
        {[
          { key: 'all', label: 'All Exceptions' },
          { key: 'newly_rejected', label: 'Newly Rejected' },
          { key: 'newly_pending', label: 'Newly Pending' },
          { key: 'dropped_from_forecast', label: 'Dropped from forecast / slipped' },
          { key: 'acv_drop_25', label: 'ACV Drop > 25%' },
        ].map((tab) => {
          const count = countsByType[tab.key as keyof typeof countsByType] ?? 0
          const isActive = filterType === tab.key
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => setFilterType(tab.key)}
              className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center gap-1.5 ${
                isActive
                  ? 'bg-teal-500 text-white shadow-sm'
                  : 'bg-[var(--bg-secondary)] text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-card)] border border-[var(--border)]'
              }`}
            >
              <span>{tab.label}</span>
              <span
                className={`text-[10px] px-1.5 py-0.2 rounded-sm tabular-nums font-bold ${
                  isActive ? 'bg-white/25 text-white' : 'bg-[var(--bg-card)] text-[var(--text-muted)] border border-[var(--border)]'
                }`}
              >
                {count}
              </span>
            </button>
          )
        })}
      </div>

      {/* List of Attention Items */}
      {filteredItems.length === 0 ? (
        <div className="py-12 text-center text-xs text-[var(--text-muted)] flex flex-col items-center justify-center gap-2">
          <div className="w-10 h-10 rounded-full bg-emerald-500/10 text-emerald-500 flex items-center justify-center">
            <CheckCircle2 className="w-5 h-5" />
          </div>
          <p className="font-semibold text-sm text-[var(--text-primary)]">
            No items in this filter
          </p>
          <p className="text-[11px] text-[var(--text-muted)]">
            Zero deals met the selected exception criteria.
          </p>
        </div>
      ) : (
        <div className="space-y-2.5">
          {filteredItems.map((item, idx) => {
            const conf = typeConfig[item.attention_type] || typeConfig.dropped_from_forecast

            return (
              <motion.div
                key={item.opportunity_id_18 + idx}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.25, delay: idx * 0.02 }}
                onClick={() => onSelectOpportunity?.(item.opportunity_id_18)}
                className="p-3.5 rounded-md border border-[var(--border)] bg-[var(--bg-secondary)] hover:border-teal-500/50 hover:bg-[var(--bg-card)] transition-all cursor-pointer group shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-3"
              >
                {/* Left: Tag, Name & Details */}
                <div className="flex items-start gap-3 min-w-0">
                  <div
                    className={`w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 mt-0.5 border ${conf.bg} ${conf.border}`}
                  >
                    {conf.icon}
                  </div>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-semibold text-xs md:text-sm text-[var(--text-primary)] group-hover:text-teal-600 dark:group-hover:text-teal-400 truncate">
                        {item.opportunity_name || item.opportunity_id_18}
                      </p>
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded-sm border ${conf.bg} ${conf.text} ${conf.border}`}
                      >
                        {item.attention_label || conf.label}
                      </span>
                    </div>
                    <p className="text-[11px] text-[var(--text-muted)] mt-0.5 truncate">
                      {item.account_name} • <span className="text-[var(--text-primary)] font-medium">{item.details}</span>
                    </p>
                  </div>
                </div>

                {/* Right: Badges, ACV, and Drilldown Arrow */}
                <div className="flex items-center justify-between md:justify-end gap-3 flex-shrink-0 pt-2 md:pt-0 border-t md:border-0 border-[var(--border)]">
                  <div className="flex items-center gap-1.5">
                    {item.forecast_category && (
                      <ForecastBadge category={item.forecast_category} />
                    )}
                    {item.approval_status && (
                      <ApprovalBadge status={item.approval_status} />
                    )}
                  </div>

                  <div className="text-right">
                    <p className="font-bold text-xs md:text-sm text-[var(--text-primary)] tabular-nums">
                      {formatACV(item.acv)}
                    </p>
                    {item.acv_diff != null && (
                      <p
                        className={`text-[10.5px] font-semibold tabular-nums ${
                          item.acv_diff >= 0 ? 'text-emerald-500' : 'text-amber-500'
                        }`}
                      >
                        {item.acv_diff >= 0 ? '+' : ''}
                        {formatACV(item.acv_diff)}
                      </p>
                    )}
                  </div>

                  <ArrowRight className="w-4 h-4 text-[var(--text-muted)] group-hover:text-teal-500 group-hover:translate-x-0.5 transition-all hidden md:block" />
                </div>
              </motion.div>
            )
          })}
        </div>
      )}
    </div>
  )
}
