import React, { useState, useRef, useEffect } from 'react'
import { acvM } from '@/utils/format'

interface SummaryLineProps {
  primaryText: string
  secondaryText?: string
  details?: { quarter: string; count: number; acv: number }[]
  onDetailClick?: (quarter: string) => void
}

export default function SummaryLine({ primaryText, secondaryText, details, onDetailClick }: SummaryLineProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  return (
    <div className="text-sm text-[var(--text-muted)] mt-2 flex items-center gap-2 px-2" ref={ref}>
      <span>{primaryText}</span>
      {secondaryText && (
        <>
          <span className="text-[var(--border)]">|</span>
          <span>{secondaryText}</span>
        </>
      )}
      {details && details.length > 0 && (
        <div className="relative inline-block">
          <button 
            className="text-[var(--primary)] hover:underline ml-1 focus:outline-none"
            onClick={() => setOpen(!open)}
          >
            (details)
          </button>
          
          {open && (
            <div className="absolute left-0 bottom-full mb-2 w-64 bg-[var(--bg-primary)] border border-[var(--border)] shadow-xl rounded-lg z-50 overflow-hidden">
              <div className="bg-[var(--bg-secondary)] px-3 py-2 border-b border-[var(--border)]">
                <span className="text-xs font-semibold text-[var(--text-primary)]">By Quarter</span>
              </div>
              <div className="max-h-60 overflow-y-auto p-1">
                {details.map(d => (
                  <button
                    key={d.quarter}
                    className="w-full flex justify-between items-center px-3 py-2 text-xs hover:bg-[var(--bg-secondary)] transition-colors rounded-md focus:outline-none text-left"
                    onClick={() => {
                      setOpen(false)
                      if (onDetailClick) onDetailClick(d.quarter)
                    }}
                  >
                    <span className="font-medium text-[var(--text-primary)]">{d.quarter}</span>
                    <span className="text-[var(--text-muted)]">{acvM(d.acv)} · {d.count} deals</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
