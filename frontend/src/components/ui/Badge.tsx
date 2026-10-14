import React from 'react'
import { clsx } from 'clsx'
import { FORECAST_COLORS, APPROVAL_COLORS } from '@/design/tokens'

export type BadgeVariant =
  | 'forecast'
  | 'approval'
  | 'neutral'
  | 'outline'
  | 'success'
  | 'warning'
  | 'danger'
  | 'brand'
  | 'teal'
  | 'violet'

interface BadgeProps {
  label?: string
  variant?: BadgeVariant
  size?: 'sm' | 'md'
  dot?: boolean
  className?: string
  children?: React.ReactNode
}

export function Badge({
  label,
  variant = 'neutral',
  size = 'md',
  dot = false,
  className,
  children,
}: BadgeProps) {
  let color = '#94A3B8'

  if (variant === 'forecast') {
    color = FORECAST_COLORS[label || ''] || '#94A3B8'
  } else if (variant === 'approval') {
    color = APPROVAL_COLORS[label || ''] || '#94A3B8'
  } else if (variant === 'success') {
    color = '#10B981'
  } else if (variant === 'warning') {
    color = '#F59E0B'
  } else if (variant === 'danger') {
    color = '#EF4444'
  } else if (variant === 'teal') {
    color = '#00A3AD'
  } else if (variant === 'violet') {
    color = '#8080FF'
  } else if (variant === 'brand') {
    color = '#12284C'
  } else if (variant === 'outline') {
    color = '#64748B'
  }

  const sizeClasses = {
    sm: 'text-[10px] px-2 py-0.5',
    md: 'text-xs px-2.5 py-0.5',
  }[size]

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-sm font-medium border select-none transition-colors tabular-nums',
        variant === 'outline'
          ? 'bg-transparent text-[var(--text-secondary)] border-[var(--border)]'
          : undefined,
        sizeClasses,
        className
      )}
      style={
        variant === 'outline'
          ? undefined
          : {
              backgroundColor: `${color}18`,
              color,
              borderColor: `${color}38`,
            }
      }
    >
      {dot && (
        <span
          className="w-1.5 h-1.5 rounded-full flex-shrink-0"
          style={{ backgroundColor: color }}
        />
      )}
      {children || label}
    </span>
  )
}

export function ForecastBadge({
  category,
  size = 'sm',
}: {
  category: string
  size?: 'sm' | 'md'
}) {
  return <Badge label={category} variant="forecast" size={size} dot />
}

export function ApprovalBadge({
  status,
  size = 'sm',
}: {
  status: string
  size?: 'sm' | 'md'
}) {
  return <Badge label={status} variant="approval" size={size} dot />
}

export default Badge
