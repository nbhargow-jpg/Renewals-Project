import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface SnapshotItem {
  id: string
  label: string
  snapshot_date: string
  yesterday_date?: string | null
  row_count: number
  active_row_count?: number
  is_active_today: boolean
  uploaded_at?: string
  source_file_summary?: string | null
  source_file_comparison?: string | null
  last_week_source?: string | null
  last_week_is_partial?: boolean
}

export interface FilterSpec {
  as_of?: string | null
  compare?: string
  period: string
  sales_types: string[]
  regions: string[]
  business_units: string[]
  forecast_categories: string[]
  approval_statuses: string[]
  include_deleted_lost: boolean
}

export const DEFAULT_FILTER_SPEC: FilterSpec = {
  as_of: null,
  compare: 'yesterday',
  period: 'current_quarter',
  sales_types: ['Renewals'],
  regions: [],
  business_units: [],
  forecast_categories: [],
  approval_statuses: [],
  include_deleted_lost: true,
}

interface AppState {
  // Theme (persisted)
  darkMode: boolean
  toggleDarkMode: () => void

  // Sidebar collapsed state (persisted)
  sidebarCollapsed: boolean
  toggleSidebarCollapsed: () => void

  // Global FilterSpec (replaces static scope)
  globalFilters: FilterSpec
  setGlobalFilters: (filters: Partial<FilterSpec>) => void
  resetGlobalFilters: () => void

  // Backwards compatibility helpers
  includeDeletedLost: boolean
  setIncludeDeletedLost: (val: boolean) => void

  // Metric Toggle Mode (persisted)
  metricMode: 'Amount' | 'Count' | 'Both'
  setMetricMode: (mode: 'Amount' | 'Count' | 'Both') => void

  // Active snapshot ("View as of")
  activeSnapshotId: string | null
  setActiveSnapshotId: (id: string | null) => void

  // Admin Auth State (in-memory only - Addendum D)
  isAdmin: boolean
  adminToken: string | null
  setIsAdmin: (isAdmin: boolean, token?: string | null) => void

  // Compare snapshot ("Compare with")
  compareSnapshotId: string | null
  setCompareSnapshotId: (id: string | null) => void

  // All available snapshots
  snapshots: SnapshotItem[]
  setSnapshots: (snapshots: SnapshotItem[]) => void

  // Command palette
  commandPaletteOpen: boolean
  setCommandPaletteOpen: (open: boolean) => void

  // Opportunity drawer
  selectedOppId: string | null
  setSelectedOppId: (id: string | null) => void

  // Opportunity filters
  filters: {
    forecastCategory: string[]
    approvalStatus: string[]
    subRegion: string[]
    businessUnit: string[]
    search: string
  }
  setFilters: (filters: Partial<AppState['filters']>) => void
  clearFilters: () => void
}

const DEFAULT_FILTERS = {
  forecastCategory: [],
  approvalStatus: [],
  subRegion: [],
  businessUnit: [],
  search: '',
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      darkMode: false,
      toggleDarkMode: () =>
        set((s) => {
          const next = !s.darkMode
          document.documentElement.classList.toggle('dark', next)
          return { darkMode: next }
        }),

      sidebarCollapsed: false,
      toggleSidebarCollapsed: () =>
        set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),

      globalFilters: DEFAULT_FILTER_SPEC,
      setGlobalFilters: (f) =>
        set((s) => ({
          globalFilters: { ...s.globalFilters, ...f, sales_types: ['Renewals'] },
          includeDeletedLost: f.include_deleted_lost !== undefined ? f.include_deleted_lost : s.includeDeletedLost,
        })),
      resetGlobalFilters: () => set({ globalFilters: DEFAULT_FILTER_SPEC, includeDeletedLost: true }),

      includeDeletedLost: true,
      setIncludeDeletedLost: (includeDeletedLost) =>
        set((s) => ({
          includeDeletedLost,
          globalFilters: { ...s.globalFilters, include_deleted_lost: includeDeletedLost },
        })),

      metricMode: 'Amount',
      setMetricMode: (metricMode) => set({ metricMode }),

      activeSnapshotId: null,
      setActiveSnapshotId: (id) =>
        set((s) => ({
          activeSnapshotId: id,
          globalFilters: { ...s.globalFilters, as_of: id },
        })),

      isAdmin: false,
      adminToken: null,
      setIsAdmin: (isAdmin, token = null) => set({ isAdmin, adminToken: token }),

      compareSnapshotId: null,
      setCompareSnapshotId: (id) =>
        set((s) => ({
          compareSnapshotId: id,
          globalFilters: { ...s.globalFilters, compare: id || 'yesterday' },
        })),

      snapshots: [],
      setSnapshots: (snapshots) => set({ snapshots }),

      commandPaletteOpen: false,
      setCommandPaletteOpen: (open) => set({ commandPaletteOpen: open }),

      selectedOppId: null,
      setSelectedOppId: (id) => set({ selectedOppId: id }),

      filters: DEFAULT_FILTERS,
      setFilters: (f) =>
        set((s) => ({ filters: { ...s.filters, ...f } })),
      clearFilters: () => set({ filters: DEFAULT_FILTERS }),
    }),
    {
      name: 'mobileum-app-v2',
      partialize: (s) => ({
        darkMode: s.darkMode,
        globalFilters: s.globalFilters,
        includeDeletedLost: s.includeDeletedLost,
        metricMode: s.metricMode,
        activeSnapshotId: s.activeSnapshotId,
        compareSnapshotId: s.compareSnapshotId,
        sidebarCollapsed: s.sidebarCollapsed,
      }),
    }
  )
)
