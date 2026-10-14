import React from 'react'
import { ChevronDown } from 'lucide-react'

export interface ControlChipProps extends React.HTMLAttributes<HTMLElement> {
  label?: string
  chipValue?: React.ReactNode
  icon?: React.ReactNode
  suffix?: React.ReactNode
  hasChevron?: boolean
  as?: 'button' | 'div'
  children?: React.ReactNode
}

export default function ControlChip({
  label,
  chipValue,
  icon,
  suffix,
  hasChevron = false,
  as = 'button',
  children,
  className = '',
  ...props
}: ControlChipProps) {
  const baseClasses = `h-9 px-3 rounded-md text-sm border border-[var(--border)] bg-[var(--bg-secondary)] hover:bg-[var(--bg-card)] text-[var(--text-primary)] inline-flex items-center gap-1.5 font-medium transition-colors select-none focus:outline-none ${className}`

  if (as === 'div') {
    return (
      <div className={baseClasses} {...props}>
        {icon && <span className="flex-shrink-0 text-[#00A3AD]">{icon}</span>}
        {label && <span className="text-[var(--text-muted)] font-medium text-xs">{label}</span>}
        {chipValue && <span className="font-semibold text-xs text-[var(--text-primary)]">{chipValue}</span>}
        {children}
        {suffix}
        {hasChevron && <ChevronDown className="w-3.5 h-3.5 text-[var(--text-muted)] opacity-70 ml-0.5" />}
      </div>
    )
  }

  return (
    <button
      type="button"
      className={baseClasses}
      {...(props as React.ButtonHTMLAttributes<HTMLButtonElement>)}
    >
      {icon && <span className="flex-shrink-0 text-[#00A3AD]">{icon}</span>}
      {label && <span className="text-[var(--text-muted)] font-medium text-xs">{label}</span>}
      {chipValue && <span className="font-semibold text-xs text-[var(--text-primary)]">{chipValue}</span>}
      {children}
      {suffix}
      {hasChevron && <ChevronDown className="w-3.5 h-3.5 text-[var(--text-muted)] opacity-70 ml-0.5" />}
    </button>
  )
}
