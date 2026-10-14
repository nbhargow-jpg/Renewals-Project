import React from 'react'
import clsx from 'clsx'

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'subtle'
  hover?: boolean
  padding?: 'none' | 'sm' | 'md' | 'lg'
  children: React.ReactNode
}

export function Card({
  variant = 'default',
  hover = false,
  padding = 'md',
  className,
  children,
  ...props
}: CardProps) {
  const paddingStyles = {
    none: 'p-0',
    sm: 'p-3',
    md: 'p-5', // 20px card internal padding standard
    lg: 'p-6',
  }[padding]

  const variantStyles = {
    default: 'bg-[var(--bg-card)] border border-[var(--border)] shadow-[var(--card-shadow)]',
    subtle: 'bg-[var(--bg-secondary)] border border-[var(--border-subtle)] shadow-[var(--card-shadow)]',
  }[variant]

  return (
    <div
      className={clsx(
        'rounded-xl transition-colors relative overflow-hidden',
        variantStyles,
        paddingStyles,
        hover && 'hover:border-[var(--brand-teal)] transition-colors duration-fast',
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}

export default Card
