import React from 'react'
import { FolderSearch } from 'lucide-react'
import clsx from 'clsx'

interface EmptyStateProps {
  icon?: React.ReactNode
  title: string
  description?: string
  action?: {
    label: string
    onClick: () => void
    variant?: 'primary' | 'secondary'
  }
  className?: string
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={clsx(
        'flex flex-col items-center justify-center p-8 text-center rounded-md border border-[var(--border)] bg-[var(--bg-card)]',
        className
      )}
    >
      <div className="text-[var(--text-muted)] mb-3">
        {icon || <FolderSearch className="w-6 h-6" strokeWidth={1.75} />}
      </div>
      <h4 className="font-semibold text-sm text-[var(--text-primary)]">
        {title}
      </h4>
      {description && (
        <p className="text-xs text-[var(--text-muted)] max-w-sm mt-1 leading-relaxed">
          {description}
        </p>
      )}
      {action && (
        <button
          type="button"
          onClick={action.onClick}
          className={clsx(
            'mt-4 px-3.5 py-1.5 rounded-sm text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-[var(--brand-teal)]',
            action.variant === 'secondary'
              ? 'bg-[var(--bg-secondary)] text-[var(--text-primary)] border border-[var(--border)] hover:bg-[var(--bg-card)]'
              : 'bg-[var(--brand-navy)] text-white hover:bg-slate-800'
          )}
        >
          {action.label}
        </button>
      )}
    </div>
  )
}

export default EmptyState
