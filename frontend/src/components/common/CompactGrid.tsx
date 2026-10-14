import React from 'react'
import { motion } from 'framer-motion'
import { getForecastCategoryLabel, getApprovalStatusLabel } from '@/utils/format'

function acvM(v: number | null | undefined): string {
  if (v == null) return '—'
  const abs = Math.abs(v)
  const sign = v < 0 ? '-' : ''
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(2)}M`
  if (abs >= 1_000)     return `${sign}$${(abs / 1_000).toFixed(0)}K`
  return `${sign}$${abs.toFixed(0)}`
}

function formatDelta(val: number, isCount: boolean) {
  const sign = val > 0 ? '+' : ''
  const color = val > 0 ? 'text-emerald-600 dark:text-emerald-400' : val < 0 ? 'text-red-600 dark:text-red-400' : 'text-[var(--text-muted)]'
  const text = isCount ? `${sign}${val}` : `${sign}${acvM(val)}`
  return <span className={color}>{text}</span>
}

export interface CellData { count: number; acv: number }

export interface CompactGridProps {
  title: string
  columns: string[]
  rows: {
    id: string
    label: string
    cells: Record<string, CellData>
    total: CellData
  }[]
  totals: {
    category: Record<string, CellData>
    grand: CellData
  }
  deltas?: any
  metricMode: 'Amount' | 'Count' | 'Both'
  onCellClick: (rowId: string | null, colId: string | null, title: string) => void
  rowLabelName?: string
  compareDate?: string | null
  yesterdayDate?: string | null
  lastweekDate?: string | null
  heatMode?: 'Value' | 'Yesterday' | 'LastWeek'
}

export default function CompactGrid({
  title, columns, rows, totals, deltas, metricMode, onCellClick, rowLabelName = 'Row', compareDate, yesterdayDate, lastweekDate, heatMode = 'Value'
}: CompactGridProps) {
  
  // 1. Keep all columns passed (Pipeline and 0-value columns always shown)
  const activeColumns = columns

  // 2. Max value/delta for heatmap
  let maxVal = 0
  let maxAbsDelta = 0
  rows.forEach(r => {
    activeColumns.forEach(c => {
      const cell = r.cells?.[c]
      if (cell) {
        const val = metricMode === 'Count' ? (cell.count || 0) : (cell.acv || 0)
        if (val > maxVal) maxVal = val
      }
      if (heatMode === 'Yesterday' || heatMode === 'LastWeek') {
        const dObj = heatMode === 'Yesterday' ? deltas?.yesterday : deltas?.lastweek
        const dCell = dObj?.matrix?.[r.id]?.[c]
        if (dCell) {
          const dv = metricMode === 'Count' ? (dCell.count || 0) : (dCell.acv || 0)
          if (Math.abs(dv) > maxAbsDelta) maxAbsDelta = Math.abs(dv)
        }
      }
    })
  })

  const renderVal = (count: number, acv: number) => {
    if (count === 0 && acv === 0) return <span className="text-[var(--text-muted)] opacity-50">–</span>
    if (metricMode === 'Amount') return <span className="font-semibold">{acvM(acv)}</span>
    if (metricMode === 'Count') return <span className="font-semibold">{count}</span>
    return (
      <span className="font-semibold">
        {acvM(acv)} <span className="text-[var(--text-muted)] text-[11px] font-normal">({count})</span>
      </span>
    )
  }

  const renderDeltas = (d: any) => {
    if (!d) return null
    const parts: any[] = []
    const renderDeltaPart = (dObj: any, dateStr: string | null | undefined, fallbackLabel: string) => {
      const hasCount = !!dObj?.count
      const hasAcv = !!dObj?.acv
      if (!hasCount && !hasAcv) return null

      const dateLabel = dateStr ? new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : fallbackLabel
      const countPart = formatDelta(dObj.count, true)
      const acvPart = formatDelta(dObj.acv, false)
      
      const valPart = metricMode === 'Count' ? countPart : metricMode === 'Amount' ? acvPart : <>{countPart} · {acvPart}</>
      return <span key={fallbackLabel}>vs {dateLabel} {valPart}</span>
    }

    if (d.custom) {
      const part = renderDeltaPart(d.custom, compareDate, 'Custom')
      if (part) parts.push(part)
    } else {
      if (d.yesterday) {
        const part = renderDeltaPart(d.yesterday, yesterdayDate, '1d')
        if (part) parts.push(part)
      }
      if (d.lastweek) {
        const part = renderDeltaPart(d.lastweek, lastweekDate, '7d')
        if (part) parts.push(part)
      }
    }
    
    if (parts.length === 0) return null
    return (
      <div className="text-[10px] text-[var(--text-muted)] mt-0.5 leading-tight flex justify-center gap-1.5">
        {parts.map((p, i) => <React.Fragment key={i}>{p}{i < parts.length - 1 && '·'}</React.Fragment>)}
      </div>
    )
  }

  return (
    <div className="card overflow-hidden border border-[var(--border)]">
      <div className="px-4 py-2 bg-[var(--bg-secondary)] border-b border-[var(--border)]">
        <h3 className="font-semibold text-sm">{title}</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-[13px] whitespace-nowrap">
          <thead>
            <tr className="bg-[var(--bg-secondary)] border-b border-[var(--border)]">
              <th className="px-3 py-2 text-left font-medium text-[var(--text-muted)]">{rowLabelName}</th>
              {activeColumns.map(c => {
                const label = rowLabelName === 'Status' ? getForecastCategoryLabel(c) : (c === 'Blank' ? 'Not yet proposed' : c)
                return (
                  <th key={c} className="px-3 py-2 text-center font-medium text-[var(--text-muted)]">{label}</th>
                )
              })}
              <th className="px-3 py-2 text-center font-semibold text-[var(--text-primary)] border-l border-[var(--border)]">Total</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.id} className="border-b border-[var(--border)] last:border-0 group">
                <td 
                  className="px-3 py-2 font-medium bg-[var(--bg-secondary)] border-r border-[var(--border)] cursor-pointer hover:text-[var(--primary)] transition-colors h-[36px]"
                  onClick={() => onCellClick(r.id, null, `${r.label} Expiry`)}
                >
                  {r.label}
                </td>
                {activeColumns.map(c => {
                  const cell = r.cells[c] || { count: 0, acv: 0 }
                  const val = metricMode === 'Count' ? cell.count : cell.acv
                  
                  let bgColor = ''
                  let cellContent = renderVal(cell.count, cell.acv)
                  
                  if (heatMode === 'Value') {
                    const ratio = maxVal > 0 ? val / maxVal : 0
                    const intensity = Math.min(ratio * 0.4, 0.4)
                    if (val > 0) bgColor = `rgba(14, 165, 233, ${intensity})` // pale teal -> deep blue scale
                  } else {
                    // Change mode
                    const dObj = heatMode === 'Yesterday' ? deltas?.yesterday : deltas?.lastweek
                    const dCell = dObj?.matrix?.[r.id]?.[c] || { count: 0, acv: 0 }
                    const dVal = metricMode === 'Count' ? dCell.count : dCell.acv
                    if (dVal !== 0) {
                      const ratio = maxAbsDelta > 0 ? Math.abs(dVal) / maxAbsDelta : 0
                      const intensity = Math.min(ratio * 0.5, 0.5)
                      bgColor = dVal > 0 ? `rgba(16, 185, 129, ${intensity})` : `rgba(239, 68, 68, ${intensity})`
                      
                      // Text: delta main, current value small
                      const sign = dVal > 0 ? '+' : ''
                      cellContent = (
                        <div className="flex flex-col items-center leading-tight">
                          <span className="font-bold text-[var(--text-primary)]">
                            {sign}{metricMode === 'Count' ? dVal : acvM(dVal)}
                          </span>
                          <span className="text-[9px] text-[var(--text-muted)] opacity-80 mt-0.5">
                            {renderVal(cell.count, cell.acv)}
                          </span>
                        </div>
                      )
                    } else if (val > 0) {
                       cellContent = (
                        <div className="flex flex-col items-center leading-tight">
                          <span className="font-medium text-[var(--text-muted)] opacity-70">
                            No change
                          </span>
                          <span className="text-[9px] text-[var(--text-muted)] opacity-60 mt-0.5">
                            {renderVal(cell.count, cell.acv)}
                          </span>
                        </div>
                      )
                    }
                  }

                  return (
                    <td
                      key={c}
                      onClick={() => onCellClick(r.id, c, `${r.label} - ${c}`)}
                      className="px-3 py-1 text-center cursor-pointer transition-all hover:ring-2 hover:ring-[var(--primary)] hover:z-10 relative text-[var(--text-primary)] h-[36px]"
                      style={bgColor ? { backgroundColor: bgColor } : {}}
                    >
                      {cellContent}
                    </td>
                  )
                })}
                <td
                  onClick={() => onCellClick(r.id, null, `${r.label} Total`)}
                  className="px-3 py-1 text-center cursor-pointer bg-[var(--bg-secondary)] border-l border-[var(--border)] hover:bg-slate-100 dark:hover:bg-slate-800 h-[36px]"
                >
                  <div>{renderVal(r.total?.count || 0, r.total?.acv || 0)}</div>
                  {renderDeltas({
                    yesterday: deltas?.yesterday?.quarters?.[r.id] || deltas?.yesterday?.rows?.[r.id],
                    lastweek: deltas?.lastweek?.quarters?.[r.id] || deltas?.lastweek?.rows?.[r.id],
                    custom: deltas?.custom?.quarters?.[r.id] || deltas?.custom?.rows?.[r.id]
                  })}
                </td>
              </tr>
            ))}
            <tr className="border-t-2 border-[var(--border)] bg-[var(--bg-secondary)]">
              <td 
                className="px-3 py-2 font-semibold border-r border-[var(--border)] cursor-pointer hover:text-[var(--primary)] h-[36px]"
                onClick={() => onCellClick(null, null, `${title} Total`)}
              >
                TOTAL
              </td>
              {activeColumns.map(c => (
                <td
                  key={c}
                  onClick={() => onCellClick(null, c, `Total - ${c}`)}
                  className="px-3 py-1 text-center cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-800 h-[36px]"
                >
                  <div>{renderVal(totals.category[c]?.count || 0, totals.category[c]?.acv || 0)}</div>
                  {renderDeltas({
                    yesterday: deltas?.yesterday?.category?.[c],
                    lastweek: deltas?.lastweek?.category?.[c],
                    custom: deltas?.custom?.category?.[c]
                  })}
                </td>
              ))}
              <td
                onClick={() => onCellClick(null, null, `${title} Grand Total`)}
                className="px-3 py-1 text-center cursor-pointer border-l border-[var(--border)] hover:bg-slate-100 dark:hover:bg-slate-800 h-[36px]"
              >
                <div>{renderVal(totals.grand.count, totals.grand.acv)}</div>
                {renderDeltas({
                  yesterday: deltas?.yesterday?.grand,
                  lastweek: deltas?.lastweek?.grand,
                  custom: deltas?.custom?.grand
                })}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}
