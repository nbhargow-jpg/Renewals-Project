import React, { useState, useMemo } from 'react'
import { ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react'
import clsx from 'clsx'

export interface Column<T = any> {
  key: string
  label: string
  sortable?: boolean
  align?: 'left' | 'center' | 'right'
  width?: string
  colorAccent?: string // Hex or color code for top border or accent bar
  render?: (value: any, row: T) => React.ReactNode
}

interface DataTableProps<T = any> {
  columns: Column<T>[]
  data: T[]
  keyField?: string
  stickyFirstColumn?: boolean
  maxHeight?: string
  emptyMessage?: string
  className?: string
  onRowClick?: (row: T) => void
}

export function DataTable<T extends Record<string, any>>({
  columns,
  data,
  keyField = 'id',
  stickyFirstColumn = true,
  maxHeight = '600px',
  emptyMessage = 'No records found',
  className,
  onRowClick,
}: DataTableProps<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null)
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')

  const handleSort = (key: string) => {
    if (sortKey === key) {
      if (sortDir === 'asc') setSortDir('desc')
      else {
        setSortKey(null)
        setSortDir('asc')
      }
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  const sortedData = useMemo(() => {
    if (!sortKey) return data
    return [...data].sort((a, b) => {
      const aVal = a[sortKey]
      const bVal = b[sortKey]
      if (aVal == null) return 1
      if (bVal == null) return -1

      if (typeof aVal === 'number' && typeof bVal === 'number') {
        return sortDir === 'asc' ? aVal - bVal : bVal - aVal
      }
      const strA = String(aVal).toLowerCase()
      const strB = String(bVal).toLowerCase()
      return sortDir === 'asc' ? strA.localeCompare(strB) : strB.localeCompare(strA)
    })
  }, [data, sortKey, sortDir])

  return (
    <div
      className={clsx(
        'relative rounded-md border border-[var(--border)] bg-[var(--bg-card)] shadow-sm overflow-hidden flex flex-col',
        className
      )}
    >
      <div
        className="overflow-auto relative w-full"
        style={{ maxHeight }}
      >
        <table className="w-full text-sm text-left border-collapse tabular-nums">
          {/* Sticky Header */}
          <thead className="sticky top-0 z-20 bg-[var(--bg-card)] border-b border-[var(--border)] shadow-sm">
            <tr>
              {columns.map((col, idx) => {
                const isStickyCol = stickyFirstColumn && idx === 0
                const isSorted = sortKey === col.key

                return (
                  <th
                    key={col.key}
                    style={{ width: col.width }}
                    className={clsx(
                      'px-4 py-3 text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] select-none transition-colors relative',
                      col.align === 'right' && 'text-right',
                      col.align === 'center' && 'text-center',
                      isStickyCol &&
                        'sticky left-0 z-30 bg-[var(--bg-card)] shadow-[2px_0_5px_rgba(0,0,0,0.03)] border-r border-[var(--border)]',
                      col.sortable && 'cursor-pointer hover:text-[var(--text-primary)] hover:bg-[var(--bg-secondary)]'
                    )}
                    onClick={() => col.sortable && handleSort(col.key)}
                  >
                    {/* Top color accent */}
                    {col.colorAccent && (
                      <div
                        className="absolute top-0 left-0 right-0 h-[2px]"
                        style={{ backgroundColor: col.colorAccent }}
                      />
                    )}

                    <div
                      className={clsx(
                        'flex items-center gap-1.5',
                        col.align === 'right' && 'justify-end',
                        col.align === 'center' && 'justify-center'
                      )}
                    >
                      <span>{col.label}</span>
                      {col.sortable && (
                        <span className="text-[var(--text-muted)]">
                          {isSorted ? (
                            sortDir === 'asc' ? (
                              <ArrowUp className="w-3.5 h-3.5 text-teal-500" />
                            ) : (
                              <ArrowDown className="w-3.5 h-3.5 text-teal-500" />
                            )
                          ) : (
                            <ArrowUpDown className="w-3.5 h-3.5 opacity-40 hover:opacity-100" />
                          )}
                        </span>
                      )}
                    </div>
                  </th>
                )
              })}
            </tr>
          </thead>

          {/* Table Body */}
          <tbody className="divide-y divide-[var(--border-subtle)]">
            {sortedData.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-6 py-12 text-center text-[var(--text-muted)]"
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              sortedData.map((row, rowIdx) => (
                <tr
                  key={row[keyField] ?? rowIdx}
                  onClick={() => onRowClick && onRowClick(row)}
                  className={clsx(
                    'transition-colors group',
                    onRowClick && 'cursor-pointer',
                    'hover:bg-[var(--bg-card-hover)]'
                  )}
                >
                  {columns.map((col, colIdx) => {
                    const isStickyCol = stickyFirstColumn && colIdx === 0
                    const rawVal = row[col.key]

                    return (
                      <td
                        key={col.key}
                        className={clsx(
                          'px-4 py-3 whitespace-nowrap transition-colors',
                          col.align === 'right' && 'text-right font-medium',
                          col.align === 'center' && 'text-center',
                          isStickyCol &&
                            'sticky left-0 z-10 bg-[var(--bg-card)] group-hover:bg-[var(--bg-card-hover)] shadow-[2px_0_5px_rgba(0,0,0,0.03)] border-r border-[var(--border)] font-semibold text-[var(--text-primary)]'
                        )}
                      >
                        {col.render ? col.render(rawVal, row) : rawVal ?? '—'}
                      </td>
                    )
                  })}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default DataTable
