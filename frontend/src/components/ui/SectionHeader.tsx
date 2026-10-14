import React from 'react'
import clsx from 'clsx'

export interface SectionHeaderProps {
  title: string
  subtitle?: string
  actions?: React.ReactNode
  className?: string
}

export function SectionHeader({
  title,
  subtitle,
  actions,
  className,
}: SectionHeaderProps) {
  return (
    <div className={clsx('flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3', className)}>
      <div>
        <h2 className="text-base font-semibold text-[var(--text-primary)] tracking-tight">
          {title}
        </h2>
        {subtitle && (
          <p className="text-xs text-[var(--text-muted)] mt-0.5 font-normal">
            {subtitle}
          </p>
        )}
      </div>
      {actions && (
        <div className="flex items-center gap-2 flex-shrink-0">
          {actions}
        </div>
      )}
    </div>
  )
}

export default SectionHeader
