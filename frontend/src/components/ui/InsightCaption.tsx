import React from 'react'
import { Sparkles, TrendingUp, AlertTriangle, CheckCircle2 } from 'lucide-react'
import clsx from 'clsx'

interface InsightCaptionProps {
  text: string
  title?: string
  type?: 'ai' | 'trend' | 'warning' | 'success'
  className?: string
  tag?: string
}

export function InsightCaption({
  text,
  title,
  type = 'ai',
  className,
  tag,
}: InsightCaptionProps) {
  const configs = {
    ai: {
      icon: <Sparkles className="w-3.5 h-3.5 text-teal-500 flex-shrink-0" />,
      border: 'border-teal-500/25',
      bg: 'bg-teal-500/5',
      badge: tag ?? 'AI Insight',
      badgeColor: 'bg-teal-500/10 text-teal-600 dark:text-teal-400',
    },
    trend: {
      icon: <TrendingUp className="w-3.5 h-3.5 text-violet-500 flex-shrink-0" />,
      border: 'border-violet-500/25',
      bg: 'bg-violet-500/5',
      badge: tag ?? 'Pipeline Trend',
      badgeColor: 'bg-violet-500/10 text-violet-600 dark:text-violet-400',
    },
    warning: {
      icon: <AlertTriangle className="w-3.5 h-3.5 text-amber-500 flex-shrink-0" />,
      border: 'border-amber-500/25',
      bg: 'bg-amber-500/5',
      badge: tag ?? 'Attention',
      badgeColor: 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
    },
    success: {
      icon: <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 flex-shrink-0" />,
      border: 'border-emerald-500/25',
      bg: 'bg-emerald-500/5',
      badge: tag ?? 'On Track',
      badgeColor: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
    },
  }[type]

  return (
    <div
      className={clsx(
        'flex items-start gap-2.5 px-3.5 py-2.5 rounded-xl border text-xs leading-relaxed transition-all',
        configs.border,
        configs.bg,
        className
      )}
    >
      <div className="mt-0.5">{configs.icon}</div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          {title && (
            <span className="font-semibold text-[var(--text-primary)]">
              {title}
            </span>
          )}
          <span
            className={clsx(
              'px-1.5 py-0.2 rounded text-[10px] font-bold uppercase tracking-wider',
              configs.badgeColor
            )}
          >
            {configs.badge}
          </span>
        </div>
        <p className="text-[var(--text-secondary)]">{text}</p>
      </div>
    </div>
  )
}

export default InsightCaption
