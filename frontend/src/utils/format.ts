/** Format a USD ACV number like $120.51M, $500.00K, $999 */
export function formatACV(val: number | null | undefined, showSign = false): string {
  if (val == null) return '—'
  const sign = showSign ? (val >= 0 ? '+' : '') : ''
  const abs = Math.abs(val)
  if (abs >= 1_000_000) return `${sign}${val < 0 ? '-' : ''}$${(abs / 1_000_000).toFixed(2)}M`
  if (abs >= 1_000)     return `${sign}${val < 0 ? '-' : ''}$${(abs / 1_000).toFixed(2)}K`
  return `${sign}${val < 0 ? '-' : ''}$${abs.toFixed(2)}`
}

export function acvM(v: number | null | undefined): string {
  if (v == null) return '—'
  const abs = Math.abs(v)
  const sign = v < 0 ? '-' : ''
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(2)}M`
  if (abs >= 1_000)     return `${sign}$${(abs / 1_000).toFixed(0)}K`
  return `${sign}$${abs.toFixed(0)}`
}

/** Format count with thousands separator: 1234567 → "1,234,567" */
export function formatCount(val: number | null | undefined): string {
  if (val == null) return '—'
  return val.toLocaleString('en-US')
}

/** Format percentage: 0.755 → "75.5%" */
export function formatPct(val: number | null | undefined): string {
  if (val == null) return '—'
  return `${val.toFixed(1)}%`
}

/** Format date string to "Oct 5, 2026" */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const dateStr = iso.length === 10 ? iso + 'T00:00:00' : iso
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

/** Get delta direction */
export function deltaClass(val: number): string {
  if (val > 0) return 'delta-positive'
  if (val < 0) return 'delta-negative'
  return 'delta-neutral'
}

/** Get delta icon */
export function deltaIcon(val: number): string {
  if (val > 0) return '▲'
  if (val < 0) return '▼'
  return '—'
}

/** Format delta value with sign and units */
export function formatDelta(
  val: number | null | undefined,
  isCurrency = true,
  countDelta?: number | null
): string {
  if (val == null) return '—'
  const sign = val >= 0 ? '+' : '-'
  const abs = Math.abs(val)
  const base = isCurrency ? formatACV(abs) : formatCount(abs)
  const formatted = `${sign}${base}`
  if (countDelta != null) {
    const cSign = countDelta >= 0 ? '+' : ''
    return `${formatted} (${cSign}${countDelta})`
  }
  return formatted
}

/** Format exact currency with standard USD locale formatting */
export function formatCurrency(val: number | null | undefined): string {
  if (val == null) return '—'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  }).format(val)
}

/** Format number with commas: 12345 → "12,345" */
export function formatNumber(val: number | null | undefined): string {
  if (val == null) return '—'
  return val.toLocaleString('en-US')
}

/** Display label for forecast category (Blank -> Not yet proposed) */
export function getForecastCategoryLabel(cat: string | null | undefined): string {
  if (!cat || cat === 'Blank' || cat === 'blank') return 'Not yet proposed'
  return cat
}

/** Display label for approval status (Blank -> Not submitted) */
export function getApprovalStatusLabel(status: string | null | undefined): string {
  if (!status || status === 'Blank' || status === 'blank') return 'Not submitted'
  return status
}

