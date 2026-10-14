/**
 * Design tokens — single source of truth for "Mobileum Horizon".
 * Strict professional enterprise theme: navy #12284C, teal #00A3AD accent,
 * cool-grey scale, zero gradients, 6px/8px/12px/16px radii, WCAG AA contrast.
 */

export const colors = {
  // Brand palette
  navy: {
    DEFAULT: '#12284C',
    light: '#1B3B6F',
    dark: '#0A172C',
    deep: '#050D19',
  },

  teal: {
    DEFAULT: '#00A3AD',
    light: '#00C4D0',
    dark: '#007A82',
  },

  // Status & semantic colors
  success: '#15803D',
  warning: '#D97706',
  danger: '#B91C1C',
  info: '#1D4ED8',

  // Light theme surface & text
  light: {
    bgPrimary: '#F8FAFC',
    bgSecondary: '#F1F5F9',
    bgCard: '#FFFFFF',
    border: '#E2E8F0',
    borderSubtle: '#EDF2F7',
    textPrimary: '#0F172A',
    textSecondary: '#475569',
    textMuted: '#64748B',
  },

  // Dark theme surface & text (WCAG AA compliant: muted #8A9BB5 >= 4.5:1 against #0B111E / #111A2E)
  dark: {
    bgPrimary: '#0B111E',
    bgSecondary: '#18233C',
    bgCard: '#111A2E',
    border: '#223252',
    borderSubtle: '#18253E',
    textPrimary: '#F8FAFC',
    textSecondary: '#CBD5E1',
    textMuted: '#8A9BB5',
  },
} as const

export const shadows = {
  none: 'none',
  card: '0 1px 2px rgba(16, 24, 40, 0.05), 0 1px 3px rgba(16, 24, 40, 0.08)',
  elevation: '0 4px 16px rgba(16, 24, 40, 0.12)',
} as const

export const radius = {
  badge: '6px',   // badges and delta chips
  control: '8px', // buttons, inputs, selects
  card: '12px',   // cards, tables, panels (rounded-xl)
  modal: '16px',  // modals and drawers
  full: '9999px', // circular avatars, spinners only
} as const

export const typography = {
  fontUi: 'Inter, system-ui, -apple-system, sans-serif',
} as const

export const motionTokens = {
  duration: 0.14,
  ease: 'easeOut',
} as const

/** Forecast category → colour-blind safe flat palette */
export const FORECAST_COLORS: Record<string, string> = {
  Closed: '#0E7490',      // deep teal
  Commit: '#1D4ED8',      // navy blue
  'Best Case': '#3B82F6',  // mid blue
  Pipeline: '#D97706',    // amber
  Blank: '#64748B',       // cool grey
}

/** Approval status → flat palette */
export const APPROVAL_COLORS: Record<string, string> = {
  Approved: '#16A34A',
  'Approved - 2nd': '#00A3AD',
  'Pending Approval': '#D97706',
  Rejected: '#DC2626',
  Blank: '#64748B',
}

export const FORECAST_ORDER = ['Closed', 'Commit', 'Best Case', 'Pipeline', 'Blank'] as const
export const APPROVAL_ORDER = ['Approved', 'Approved - 2nd', 'Pending Approval', 'Rejected', 'Blank'] as const

export type ForecastCategory = typeof FORECAST_ORDER[number]
export type ApprovalStatus = typeof APPROVAL_ORDER[number]
