import React, { useState, useEffect, useRef } from 'react'
import { useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Calendar,
  GitCompare,
  Filter,
  RotateCcw,
  ChevronDown,
  X,
  Bookmark,
  Check,
  Save,
  Trash2,
  Info,
} from 'lucide-react'
import { useAppStore, FilterSpec, DEFAULT_FILTER_SPEC } from '@/store/appStore'
import { getFilterOptions } from '@/api/client'
import ControlChip from '@/components/ui/ControlChip'

interface FilterBarProps {
  isPageOverride?: boolean
  localFilters?: FilterSpec
  onFiltersChange?: (filters: FilterSpec) => void
  onReset?: () => void
  className?: string
}

export default function FilterBar({
  isPageOverride = false,
  localFilters,
  onFiltersChange,
  onReset,
  className = '',
}: FilterBarProps) {
  const {
    globalFilters,
    setGlobalFilters,
    resetGlobalFilters,
    snapshots,
  } = useAppStore()

  // If localFilters is passed, we operate in page override mode; otherwise global
  const activeFilters = isPageOverride && localFilters ? localFilters : globalFilters
  const setFilters = (f: Partial<FilterSpec>) => {
    if (isPageOverride && onFiltersChange) {
      onFiltersChange({ ...activeFilters, ...f })
    } else {
      setGlobalFilters(f)
    }
  }

  const [moreOpen, setMoreOpen] = useState(false)
  const [viewsOpen, setViewsOpen] = useState(false)
  const [newViewName, setNewViewName] = useState('')
  const [savedViews, setSavedViews] = useState<{ id: string; name: string; filters: FilterSpec }[]>([])
  const moreRef = useRef<HTMLDivElement>(null)
  const viewsRef = useRef<HTMLDivElement>(null)

  // Fetch dynamic filter options from active snapshot
  const { data: filterOpts } = useQuery({
    queryKey: ['filter-options', activeFilters.as_of],
    queryFn: () => getFilterOptions(activeFilters.as_of ?? undefined),
    staleTime: 60_000,
  })

  // Load saved views from localStorage
  useEffect(() => {
    try {
      const v = localStorage.getItem('mobileum_saved_filter_views')
      if (v) setSavedViews(JSON.parse(v))
    } catch (e) {
      // ignore
    }
  }, [])

  // Close popovers on click outside
  useEffect(() => {
    const handleOutside = (e: MouseEvent) => {
      if (moreRef.current && !moreRef.current.contains(e.target as Node)) {
        setMoreOpen(false)
      }
      if (viewsRef.current && !viewsRef.current.contains(e.target as Node)) {
        setViewsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleOutside)
    return () => document.removeEventListener('mousedown', handleOutside)
  }, [])

  const handleSaveView = () => {
    if (!newViewName.trim()) return
    const updated = [
      ...savedViews,
      { id: Date.now().toString(), name: newViewName.trim(), filters: { ...activeFilters } },
    ]
    setSavedViews(updated)
    localStorage.setItem('mobileum_saved_filter_views', JSON.stringify(updated))
    setNewViewName('')
  }

  const handleDeleteView = (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    const updated = savedViews.filter((v) => v.id !== id)
    setSavedViews(updated)
    localStorage.setItem('mobileum_saved_filter_views', JSON.stringify(updated))
  }

  const handleApplyView = (viewFilters: FilterSpec) => {
    setFilters(viewFilters)
    setViewsOpen(false)
  }

  // Toggle helpers for multi-select
  const toggleArrayFilter = (
    field: 'regions' | 'business_units' | 'forecast_categories' | 'approval_statuses',
    value: string
  ) => {
    const current = activeFilters[field] || []
    const next = current.includes(value)
      ? current.filter((v) => v !== value)
      : [...current, value]
    setFilters({ [field]: next } as any)
  }

  // Calculate chip representations for removable active filters
  const chips: { key: string; label: string; onRemove: () => void }[] = []

  if (activeFilters.period !== 'current_quarter') {
    const pLabel =
      filterOpts?.quarters?.find((q: any) => q.value === activeFilters.period)?.label ||
      activeFilters.period
    chips.push({
      key: `period-${activeFilters.period}`,
      label: `Period: ${pLabel}`,
      onRemove: () => setFilters({ period: 'current_quarter' }),
    })
  }

  if (!activeFilters.include_deleted_lost) {
    chips.push({
      key: 'include_deleted_lost',
      label: 'Exclude Deleted/Lost',
      onRemove: () => setFilters({ include_deleted_lost: true }),
    })
  }

  activeFilters.regions?.forEach((r) => {
    chips.push({
      key: `region-${r}`,
      label: `Region: ${r}`,
      onRemove: () => toggleArrayFilter('regions', r),
    })
  })

  activeFilters.business_units?.forEach((bu) => {
    chips.push({
      key: `bu-${bu}`,
      label: `BU: ${bu}`,
      onRemove: () => toggleArrayFilter('business_units', bu),
    })
  })

  activeFilters.forecast_categories?.forEach((fc) => {
    chips.push({
      key: `fc-${fc}`,
      label: `Category: ${fc}`,
      onRemove: () => toggleArrayFilter('forecast_categories', fc),
    })
  })

  activeFilters.approval_statuses?.forEach((st) => {
    chips.push({
      key: `st-${st}`,
      label: `Approval: ${st}`,
      onRemove: () => toggleArrayFilter('approval_statuses', st),
    })
  })

  const hasActiveOverrides = chips.length > 0 || (isPageOverride && Boolean(localFilters))

  const location = useLocation()
  const isExplorer = location.pathname.startsWith('/opportunities') || location.pathname.startsWith('/explore')

  if (isExplorer && !isPageOverride) {
    return (
      <div className={`flex items-center gap-2 py-1 text-xs text-[var(--text-muted)] ${className}`} id="filter-bar-explorer-scope-note">
        <Info className="w-3.5 h-3.5 text-[#00A3AD] flex-shrink-0" />
        <span className="font-medium text-[var(--text-secondary)]">
          Showing the full Excel sheet. Use the filters below.
        </span>
      </div>
    )
  }

  return (
    <div className={`flex flex-col gap-2 ${className}`}>
      {/* Top Filter Bar Controls */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-xs">
        {/* Page Override Badge if applicable */}
        {isPageOverride && (
          <span className="h-9 px-3 rounded-md text-xs font-semibold bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 inline-flex items-center">
            Page Override
          </span>
        )}

        {/* 1. Period Dropdown */}
        <div className="relative inline-flex items-center">
          <ControlChip
            as="div"
            icon={<Calendar className="w-3.5 h-3.5 flex-shrink-0" />}
            label="Period:"
            hasChevron={true}
          >
            <select
              value={activeFilters.period}
              onChange={(e) => setFilters({ period: e.target.value })}
              className="bg-transparent font-medium text-[var(--text-primary)] outline-none cursor-pointer text-xs pr-1"
              id="filter-period-select"
            >
              <option value="current_quarter">Current Quarter (Default)</option>
              <option value="previous_quarter">Previous Quarter</option>
              <option value="next_quarter">Next Quarter</option>
              <option value="all_periods">All Periods</option>
              {filterOpts?.quarters?.map((q: any) => (
                <option key={q.key} value={q.key}>
                  {q.label} ({q.count})
                </option>
              ))}
              {filterOpts?.fiscal_years?.map((fy: any) => (
                <option key={fy.key} value={fy.key}>
                  {fy.label} ({fy.count})
                </option>
              ))}
            </select>
          </ControlChip>
        </div>

        {/* 3. Include Deleted & Lost Checkbox */}
        <label
          className="h-9 px-3 rounded-md border border-[var(--border)] bg-[var(--bg-secondary)] hover:bg-[var(--bg-card)] cursor-pointer transition-colors inline-flex items-center gap-2 select-none"
          title="Toggle inclusion of Deleted and Lost pipeline opportunities"
        >
          <input
            type="checkbox"
            checked={activeFilters.include_deleted_lost}
            onChange={(e) => setFilters({ include_deleted_lost: e.target.checked })}
            className="rounded border-[var(--border)] text-[#00A3AD] focus:ring-0 w-3.5 h-3.5 cursor-pointer"
            id="filter-include-deleted-lost"
          />
          <span className="font-medium text-[var(--text-primary)] text-xs">Include Deleted & Lost</span>
        </label>

        {/* 4. "More Filters" Popover */}
        <div className="relative" ref={moreRef}>
          <button
            type="button"
            onClick={() => setMoreOpen(!moreOpen)}
            className="h-9 px-3 rounded-md border border-[var(--border)] bg-[var(--bg-secondary)] text-[var(--text-primary)] font-medium hover:bg-[var(--bg-card)] transition-colors inline-flex items-center gap-1.5 focus:outline-none"
            id="filter-more-btn"
          >
            <Filter className="w-3.5 h-3.5 text-[#00A3AD] flex-shrink-0" />
            <span>More Filters</span>
            {(activeFilters.regions.length > 0 ||
              activeFilters.business_units.length > 0 ||
              activeFilters.forecast_categories.length > 0 ||
              activeFilters.approval_statuses.length > 0) && (
              <span className="px-1.5 py-0.5 rounded-sm bg-[#00A3AD] text-white flex items-center justify-center text-[10px] font-semibold leading-none">
                {activeFilters.regions.length +
                  activeFilters.business_units.length +
                  activeFilters.forecast_categories.length +
                  activeFilters.approval_statuses.length}
              </span>
            )}
            <ChevronDown className="w-3.5 h-3.5 text-[var(--text-muted)] opacity-70 ml-0.5" />
          </button>

          {moreOpen && (
            <div className="absolute left-0 mt-1 w-80 md:w-96 rounded-lg bg-[var(--bg-card)] border border-[var(--border)] shadow-xl p-3 z-50 flex flex-col gap-3 max-h-[80vh] overflow-y-auto">
              <div className="flex items-center justify-between border-b pb-2 border-[var(--border)]">
                <span className="font-semibold text-xs text-[var(--text-primary)]">Filter Dimensions</span>
                <button
                  type="button"
                  onClick={() => setMoreOpen(false)}
                  className="text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Regions Multi-Select */}
              <div>
                <label className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider block mb-1">
                  Regions
                </label>
                <div className="flex flex-wrap gap-1 max-h-28 overflow-y-auto p-1 border rounded-sm border-[var(--border)] bg-[var(--bg-secondary)]">
                  {filterOpts?.regions?.map((r: any) => {
                    const sel = activeFilters.regions.includes(r.key)
                    return (
                      <button
                        key={r.key}
                        type="button"
                        onClick={() => toggleArrayFilter('regions', r.key)}
                        className={`px-2 py-0.5 rounded-sm text-xs font-medium border transition-colors ${
                          sel
                            ? 'bg-[#12284C] text-white border-[#12284C]'
                            : 'bg-[var(--bg-card)] text-[var(--text-secondary)] border-[var(--border)] hover:bg-[var(--bg-hover)]'
                        }`}
                      >
                        {r.label} ({r.count})
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* Business Units Multi-Select */}
              <div>
                <label className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider block mb-1">
                  Business Units
                </label>
                <div className="flex flex-wrap gap-1 max-h-28 overflow-y-auto p-1 border rounded-sm border-[var(--border)] bg-[var(--bg-secondary)]">
                  {filterOpts?.business_units?.map((bu: any) => {
                    const sel = activeFilters.business_units.includes(bu.key)
                    return (
                      <button
                        key={bu.key}
                        type="button"
                        onClick={() => toggleArrayFilter('business_units', bu.key)}
                        className={`px-2 py-0.5 rounded-sm text-xs font-medium border transition-colors ${
                          sel
                            ? 'bg-[#12284C] text-white border-[#12284C]'
                            : 'bg-[var(--bg-card)] text-[var(--text-secondary)] border-[var(--border)] hover:bg-[var(--bg-hover)]'
                        }`}
                      >
                        {bu.label} ({bu.count})
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* Forecast Categories (5 Canonical) */}
              <div>
                <label className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider block mb-1">
                  Forecast Categories
                </label>
                <div className="flex flex-wrap gap-1">
                  {filterOpts?.forecast_categories?.map((fc: any) => {
                    const sel = activeFilters.forecast_categories.includes(fc.key)
                    return (
                      <button
                        key={fc.key}
                        type="button"
                        onClick={() => toggleArrayFilter('forecast_categories', fc.key)}
                        className={`px-2 py-0.5 rounded-sm text-xs font-medium border transition-colors ${
                          sel
                            ? 'bg-[#12284C] text-white border-[#12284C]'
                            : 'bg-[var(--bg-card)] text-[var(--text-secondary)] border-[var(--border)] hover:bg-[var(--bg-hover)]'
                        }`}
                      >
                        {fc.label} ({fc.count})
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* Approval Statuses */}
              <div>
                <label className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider block mb-1">
                  Approval Statuses
                </label>
                <div className="flex flex-wrap gap-1">
                  {filterOpts?.approval_statuses?.map((st: any) => {
                    const sel = activeFilters.approval_statuses.includes(st.key)
                    return (
                      <button
                        key={st.key}
                        type="button"
                        onClick={() => toggleArrayFilter('approval_statuses', st.key)}
                        className={`px-2 py-0.5 rounded-sm text-xs font-medium border transition-colors ${
                          sel
                            ? 'bg-[#12284C] text-white border-[#12284C]'
                            : 'bg-[var(--bg-card)] text-[var(--text-secondary)] border-[var(--border)] hover:bg-[var(--bg-hover)]'
                        }`}
                      >
                        {st.label} ({st.count})
                      </button>
                    )
                  })}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* 5. Saved Views Dropdown */}
        <div className="relative" ref={viewsRef}>
          <button
            type="button"
            onClick={() => setViewsOpen(!viewsOpen)}
            className="h-9 px-3 rounded-md border border-[var(--border)] bg-[var(--bg-secondary)] text-[var(--text-primary)] font-medium hover:bg-[var(--bg-card)] transition-colors inline-flex items-center gap-1.5 focus:outline-none"
            id="filter-saved-views-btn"
          >
            <Bookmark className="w-3.5 h-3.5 text-[#00A3AD] flex-shrink-0" />
            <span>Saved Views</span>
            <ChevronDown className="w-3.5 h-3.5 text-[var(--text-muted)] opacity-70 ml-0.5" />
          </button>

          {viewsOpen && (
            <div className="absolute left-0 mt-1 w-64 rounded-lg bg-[var(--bg-card)] border border-[var(--border)] shadow-xl p-3 z-50 flex flex-col gap-2">
              <span className="font-semibold text-xs text-[var(--text-primary)]">Custom Filter Views</span>
              <div className="flex gap-1.5">
                <input
                  type="text"
                  placeholder="View name..."
                  value={newViewName}
                  onChange={(e) => setNewViewName(e.target.value)}
                  className="px-2 py-1 rounded-md border text-xs bg-[var(--bg-secondary)] border-[var(--border)] flex-1 text-[var(--text-primary)]"
                />
                <button
                  type="button"
                  onClick={handleSaveView}
                  disabled={!newViewName.trim()}
                  className="px-2.5 py-1 rounded-md bg-[#12284C] text-white text-xs font-medium hover:bg-[#1B365D] disabled:opacity-50"
                >
                  <Save className="w-3.5 h-3.5" />
                </button>
              </div>

              {savedViews.length > 0 && (
                <div className="flex flex-col gap-1 max-h-40 overflow-y-auto border-t border-[var(--border)] pt-2 mt-1">
                  {savedViews.map((v) => (
                    <div
                      key={v.id}
                      onClick={() => handleApplyView(v.filters)}
                      className="flex items-center justify-between px-2 py-1.5 rounded-md hover:bg-[var(--bg-hover)] cursor-pointer text-xs group"
                    >
                      <span className="font-medium text-[var(--text-primary)] truncate">{v.name}</span>
                      <button
                        type="button"
                        onClick={(e) => handleDeleteView(v.id, e)}
                        className="opacity-0 group-hover:opacity-100 text-red-500 hover:text-red-700"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* 6. Reset Filters Button */}
        {hasActiveOverrides && (
          <button
            type="button"
            onClick={() => {
              if (isPageOverride && onReset) {
                onReset()
              } else {
                resetGlobalFilters()
              }
            }}
            className="h-9 px-3 rounded-md border border-rose-500/20 text-rose-600 dark:text-rose-400 hover:bg-rose-500/10 transition-colors font-medium inline-flex items-center gap-1.5 focus:outline-none"
            id="filter-reset-btn"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Reset</span>
          </button>
        )}
      </div>

      {/* Removable Chips */}
      {chips.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 pt-1">
          {chips.map((chip) => (
            <span
              key={chip.key}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm text-xs bg-[var(--bg-secondary)] text-[var(--text-secondary)] border border-[var(--border)] font-medium"
            >
              <span>{chip.label}</span>
              <button
                type="button"
                onClick={chip.onRemove}
                className="hover:text-red-500 transition-colors"
              >
                <X className="w-3 h-3" />
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
