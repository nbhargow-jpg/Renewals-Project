import React from 'react'
import clsx from 'clsx'

interface SkeletonProps {
  className?: string
  variant?: 'text' | 'circular' | 'rectangular' | 'card'
  width?: string | number
  height?: string | number
}

export function Skeleton({
  className = '',
  variant = 'text',
  width,
  height,
}: SkeletonProps) {
  const variantStyles = {
    text: 'h-4 w-full rounded-sm',
    circular: 'rounded-full flex-shrink-0',
    rectangular: 'rounded-md w-full',
    card: 'rounded-md w-full h-32',
  }[variant]

  const inlineStyles: React.CSSProperties = {}
  if (width != null) inlineStyles.width = width
  if (height != null) inlineStyles.height = height

  return (
    <div
      className={clsx('skeleton-shimmer animate-pulse', variantStyles, className)}
      style={inlineStyles}
    />
  )
}

export function SkeletonCard({ rows = 3 }: { rows?: number }) {
  return (
    <div className="card p-4 space-y-3">
      <Skeleton className="h-4 w-32" />
      <Skeleton className="h-7 w-44" />
      <div className="space-y-2 pt-2">
        {Array.from({ length: rows }).map((_, i) => (
          <Skeleton
            key={i}
            className={`h-3 ${i % 2 === 0 ? 'w-full' : 'w-4/5'}`}
          />
        ))}
      </div>
    </div>
  )
}

export function SkeletonChart() {
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-4">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-5 w-24 rounded-sm" />
      </div>
      <Skeleton className="h-64 w-full rounded-md" />
    </div>
  )
}

export default Skeleton
