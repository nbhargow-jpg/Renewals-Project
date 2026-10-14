import React, { useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Search, ArrowUpDown, ArrowUp, ArrowDown, Download, FilterX } from 'lucide-react'
import { formatCurrency, formatNumber, formatDate, getForecastCategoryLabel, getApprovalStatusLabel } from '@/utils/format'
import { FORECAST_COLORS } from '@/design/tokens'
import { useAppStore } from '@/store/appStore'

interface Deal {
  id: string
  opportunity_id_18: string
  opportunity_name: string
  account_name: string
  forecast_category: string
  forecast_acv_amount: number
  approval_status: string
  reason_for_approval?: string
  sub_region?: string
  business_unit_primary?: string
  close_date?: string
  owner?: string
  stage?: string
  delta_group?: string
  delta_acv_change?: number
}

interface DealListModalProps {
  title: string
  deals: Deal[]
  initialFilters?: {
    forecast_category?: string | null
    approval_status?: string | null
    stage?: string | null
    sub_region?: string | null
    business_unit_primary?: string | null
    owner?: string | null
  }
  deltaGroups?: {
    added: { name: string; count: number; acv: number; deals: any[] }
    left: { name: string; count: number; acv: number; deals: any[] }
    amount_changed: { name: string; count: number; acv: number; deals: any[] }
    net: { count: number; acv: number }
  }
  onSelectOpp: (id: string) => void
  onClose: () => void
}

export default function DealListModal({ title, deals, initialFilters, deltaGroups, onSelectOpp, onClose }: DealListModalProps) {
  const [selectedGroup, setSelectedGroup] = useState<'All' | 'added' | 'left' | 'amount_changed'>('All')
  const [search, setSearch] = useState('')
  const [sortField, setSortField] = useState<keyof Deal | null>(null)
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')

  
  const [filterFC, setFilterFC] = useState<string>(initialFilters?.forecast_category || 'All')
  const [filterStatus, setFilterStatus] = useState<string>(initialFilters?.approval_status || 'All')
  const [filterStage, setFilterStage] = useState<string>(initialFilters?.stage || 'All')
  const [filterRegion, setFilterRegion] = useState<string>(initialFilters?.sub_region || 'All')
  const [filterBU, setFilterBU] = useState<string>(initialFilters?.business_unit_primary || 'All')
  const [filterOwner, setFilterOwner] = useState<string>(initialFilters?.owner || 'All')

  const uniqueValues = (field: keyof Deal) => {
    const vals = new Set(deals.map(d => d[field]).filter(Boolean) as string[])
    return ['All', ...Array.from(vals)].sort()
  }

  const fcOptions = ['All', 'Closed', 'Commit', 'Best Case', 'Pipeline', 'Blank']
  const statusOptions = uniqueValues('approval_status')
  const stageOptions = uniqueValues('stage')
  const regionOptions = uniqueValues('sub_region')
  const buOptions = uniqueValues('business_unit_primary')
  const ownerOptions = uniqueValues('owner')

  const handleSort = (field: keyof Deal) => {
    if (sortField === field) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDir('desc')
    }
  }

  const filteredDeals = useMemo(() => {
    let result = deals.filter(d => {
      if (deltaGroups && selectedGroup !== 'All') {
        if (selectedGroup === 'added' && d.delta_group !== 'Added to Q4') return false
        if (selectedGroup === 'left' && d.delta_group !== 'Left Q4 – moved or lost') return false
        if (selectedGroup === 'amount_changed' && d.delta_group !== 'Amount changed') return false
      }
      if (filterFC !== 'All' && d.forecast_category !== filterFC) return false
      if (filterStatus !== 'All' && d.approval_status !== filterStatus) return false
      if (filterStage !== 'All' && d.stage !== filterStage) return false
      if (filterRegion !== 'All' && d.sub_region !== filterRegion) return false
      if (filterBU !== 'All' && d.business_unit_primary !== filterBU) return false
      if (filterOwner !== 'All' && d.owner !== filterOwner) return false
      
      if (search) {
        const q = search.toLowerCase()
        if (!d.opportunity_name?.toLowerCase().includes(q) &&
            !d.account_name?.toLowerCase().includes(q) &&
            !d.opportunity_id_18?.toLowerCase().includes(q) &&
            !d.owner?.toLowerCase().includes(q)) {
          return false
        }
      }
      return true
    })
    
    if (sortField) {
      result.sort((a, b) => {
        const valA = a[sortField] || ''
        const valB = b[sortField] || ''
        if (valA < valB) return sortDir === 'asc' ? -1 : 1
        if (valA > valB) return sortDir === 'asc' ? 1 : -1
        return 0
      })
    }
    return result
  }, [deals, search, filterFC, filterStatus, filterStage, filterRegion, filterBU, filterOwner, sortField, sortDir, deltaGroups, selectedGroup])

  const totalAcv = filteredDeals.reduce((sum, d) => sum + (d.forecast_acv_amount || 0), 0)

  const handleExport = () => {
    const headers = ['Opportunity ID', 'Opportunity Name', 'Account', 'Forecast Category', 'Approval Status', 'ACV', 'Close Date', 'Stage', 'Region', 'BU', 'Owner']
    const csvContent = [
      headers.join(','),
      ...filteredDeals.map(d => [
        `"${d.opportunity_id_18 || ''}"`,
        `"${(d.opportunity_name || '').replace(/"/g, '""')}"`,
        `"${(d.account_name || '').replace(/"/g, '""')}"`,
        `"${d.forecast_category || ''}"`,
        `"${d.approval_status || ''}"`,
        d.forecast_acv_amount || 0,
        `"${d.close_date || ''}"`,
        `"${d.stage || ''}"`,
        `"${d.sub_region || ''}"`,
        `"${d.business_unit_primary || ''}"`,
        `"${d.owner || ''}"`
      ].join(','))
    ].join('\n')
    
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    const url = URL.createObjectURL(blob)
    link.setAttribute('href', url)
    link.setAttribute('download', `deals_export_${new Date().getTime()}.csv`)
    link.style.visibility = 'hidden'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const clearFilters = () => {
    setFilterFC(initialFilters?.forecast_category || 'All')
    setFilterStatus(initialFilters?.approval_status || 'All')
    setFilterStage(initialFilters?.stage || 'All')
    setFilterRegion(initialFilters?.sub_region || 'All')
    setFilterBU(initialFilters?.business_unit_primary || 'All')
    setFilterOwner(initialFilters?.owner || 'All')
    setSelectedGroup('All')
    setSearch('')
  }

  const hasActiveFilters = 
    filterFC !== (initialFilters?.forecast_category || 'All') ||
    filterStatus !== (initialFilters?.approval_status || 'All') ||
    filterStage !== (initialFilters?.stage || 'All') ||
    filterRegion !== (initialFilters?.sub_region || 'All') ||
    filterBU !== (initialFilters?.business_unit_primary || 'All') ||
    filterOwner !== (initialFilters?.owner || 'All') ||
    selectedGroup !== 'All' ||
    search !== ''

  const { globalFilters } = useAppStore()

  const activeChips = []
  // Inherited active global filters
  if (globalFilters.period && globalFilters.period !== 'current_quarter') {
    activeChips.push({ label: 'Period', value: globalFilters.period })
  }
  if (globalFilters.sales_types?.length > 0 && !(globalFilters.sales_types.length === 1 && globalFilters.sales_types[0] === 'Renewals')) {
    activeChips.push({ label: 'Sales Type', value: globalFilters.sales_types.join(', ') })
  }
  if (!globalFilters.include_deleted_lost) {
    activeChips.push({ label: 'Deleted/Lost', value: 'Excluded' })
  }
  globalFilters.regions?.forEach(r => activeChips.push({ label: 'Region Filter', value: r }))
  globalFilters.business_units?.forEach(bu => activeChips.push({ label: 'BU Filter', value: bu }))

  // Local modal filters
  if (selectedGroup !== 'All') activeChips.push({ label: 'Group', value: selectedGroup === 'added' ? 'Added' : selectedGroup === 'left' ? 'Left' : 'Amount changed', onRemove: () => setSelectedGroup('All') })
  if (filterFC !== 'All') activeChips.push({ label: 'Category', value: filterFC, onRemove: () => setFilterFC('All') })
  if (filterStatus !== 'All') activeChips.push({ label: 'Status', value: filterStatus, onRemove: () => setFilterStatus('All') })
  if (filterStage !== 'All') activeChips.push({ label: 'Stage', value: filterStage, onRemove: () => setFilterStage('All') })
  if (filterRegion !== 'All') activeChips.push({ label: 'Region', value: filterRegion, onRemove: () => setFilterRegion('All') })
  if (filterBU !== 'All') activeChips.push({ label: 'BU', value: filterBU, onRemove: () => setFilterBU('All') })
  if (filterOwner !== 'All') activeChips.push({ label: 'Owner', value: filterOwner, onRemove: () => setFilterOwner('All') })

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60"
        onClick={onClose}
      >
        <motion.div
          initial={{ scale: 0.97, y: 12 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.97, y: 12 }}
          transition={{ duration: 0.15, ease: 'easeOut' }}
          className="w-full max-w-6xl max-h-[90vh] flex flex-col bg-[var(--bg-primary)] rounded-2xl shadow-xl overflow-hidden border border-[var(--border)]"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between p-5 border-b border-[var(--border)] gap-3 bg-[var(--bg-secondary)]">
            <div>
              <h3 className="font-semibold text-base text-[var(--text-primary)] flex items-center gap-2">
                {title}
              </h3>
              <p className="text-[var(--text-muted)] text-xs mt-0.5 font-normal">
                Showing {formatNumber(filteredDeals.length)} deals · <span className="font-semibold text-[var(--text-primary)] tabular-nums">{formatCurrency(totalAcv)}</span>
              </p>
              {deltaGroups && (
                <div className="mt-2.5 flex flex-wrap items-center gap-2">
                  <span className="text-xs font-medium text-teal-700 dark:text-teal-300 bg-teal-500/10 border border-teal-500/20 px-2 py-0.5 rounded-sm tabular-nums">
                    Net: {deltaGroups.net.count >= 0 ? `+${deltaGroups.net.count}` : deltaGroups.net.count} deals / {deltaGroups.net.acv >= 0 ? `+$${(deltaGroups.net.acv / 1000).toFixed(1)}K` : `-$${(Math.abs(deltaGroups.net.acv) / 1000).toFixed(1)}K`} ({formatCurrency(deltaGroups.net.acv)})
                  </span>
                  <div className="inline-flex rounded-md border border-[var(--border)] bg-[var(--bg-primary)] p-0.5 text-xs font-medium">
                    <button
                      onClick={() => setSelectedGroup('All')}
                      className={`px-2.5 py-1 rounded-sm transition-colors ${selectedGroup === 'All' ? 'bg-[#12284C] text-white' : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'}`}
                    >
                      All ({deals.length})
                    </button>
                    <button
                      onClick={() => setSelectedGroup('added')}
                      className={`px-2.5 py-1 rounded-sm transition-colors ${selectedGroup === 'added' ? 'bg-emerald-600 text-white' : 'text-emerald-700 dark:text-emerald-300 hover:text-emerald-800'}`}
                    >
                      Added to Q4 ({deltaGroups.added.count})
                    </button>
                    <button
                      onClick={() => setSelectedGroup('left')}
                      className={`px-2.5 py-1 rounded-sm transition-colors ${selectedGroup === 'left' ? 'bg-rose-600 text-white' : 'text-rose-700 dark:text-rose-300 hover:text-rose-800'}`}
                    >
                      Left Q4 – moved or lost ({deltaGroups.left.count})
                    </button>
                    <button
                      onClick={() => setSelectedGroup('amount_changed')}
                      className={`px-2.5 py-1 rounded-sm transition-colors ${selectedGroup === 'amount_changed' ? 'bg-amber-600 text-white' : 'text-amber-700 dark:text-amber-300 hover:text-amber-800'}`}
                    >
                      Amount changed ({deltaGroups.amount_changed.count})
                    </button>
                  </div>
                </div>
              )}
              {activeChips.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {activeChips.map(chip => (
                    <div key={chip.label} className="flex items-center gap-1.5 px-2 py-0.5 rounded-sm bg-[var(--bg-primary)] border border-[var(--border)] text-[11px] font-medium text-[var(--text-primary)]">
                      <span className="text-[var(--text-muted)]">{chip.label}:</span> {chip.value}
                      <button onClick={chip.onRemove} className="text-[var(--text-muted)] hover:text-red-500"><X className="w-3 h-3" /></button>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button 
                onClick={handleExport}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-[var(--bg-primary)] border border-[var(--border)] text-[var(--text-primary)] text-xs font-medium hover:bg-[var(--bg-secondary)] transition-colors"
              >
                <Download className="w-3.5 h-3.5" /> Export CSV
              </button>
              <button onClick={onClose} className="p-1.5 rounded-md hover:bg-[var(--bg-secondary)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors">
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Filters Area */}
          <div className="p-3.5 border-b border-[var(--border)] bg-[var(--bg-primary)] flex flex-wrap gap-2 items-center">
            <div className="relative flex-grow min-w-[200px] max-w-sm">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--text-muted)]" />
              <input 
                type="text" 
                placeholder="Search deals..." 
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 text-xs bg-[var(--bg-secondary)] border border-[var(--border)] rounded-md focus:outline-none focus:border-[#00A3AD] text-[var(--text-primary)] transition-colors"
              />
            </div>
            
            <select value={filterFC} onChange={e => setFilterFC(e.target.value)} className="text-xs py-1.5 px-2.5 rounded-md bg-[var(--bg-secondary)] border border-[var(--border)] text-[var(--text-primary)] focus:outline-none cursor-pointer">
              {fcOptions.map(o => <option key={o} value={o}>{o === 'All' ? 'All Categories' : getForecastCategoryLabel(o)}</option>)}
            </select>
            <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)} className="text-xs py-1.5 px-2.5 rounded-md bg-[var(--bg-secondary)] border border-[var(--border)] text-[var(--text-primary)] focus:outline-none cursor-pointer">
              {statusOptions.map(o => <option key={o} value={o}>{o === 'All' ? 'All Statuses' : getApprovalStatusLabel(o)}</option>)}
            </select>
            <select value={filterStage} onChange={e => setFilterStage(e.target.value)} className="text-xs py-1.5 px-2.5 rounded-md bg-[var(--bg-secondary)] border border-[var(--border)] text-[var(--text-primary)] focus:outline-none cursor-pointer">
              {stageOptions.map(o => <option key={o} value={o}>{o === 'All' ? 'All Stages' : o}</option>)}
            </select>
            <select value={filterRegion} onChange={e => setFilterRegion(e.target.value)} className="text-xs py-1.5 px-2.5 rounded-md bg-[var(--bg-secondary)] border border-[var(--border)] text-[var(--text-primary)] focus:outline-none cursor-pointer">
              {regionOptions.map(o => <option key={o} value={o}>{o === 'All' ? 'All Regions' : o}</option>)}
            </select>
            <select value={filterBU} onChange={e => setFilterBU(e.target.value)} className="text-xs py-1.5 px-2.5 rounded-md bg-[var(--bg-secondary)] border border-[var(--border)] text-[var(--text-primary)] focus:outline-none cursor-pointer">
              {buOptions.map(o => <option key={o} value={o}>{o === 'All' ? 'All BUs' : o}</option>)}
            </select>
            
            {(hasActiveFilters) && (
              <button onClick={clearFilters} className="flex items-center gap-1.5 text-xs text-red-600 dark:text-red-400 font-medium hover:underline ml-auto whitespace-nowrap">
                <FilterX className="w-3.5 h-3.5" /> Reset filters
              </button>
            )}
          </div>

          {/* Table */}
          <div className="overflow-y-auto flex-1 bg-[var(--bg-primary)]">
            {filteredDeals.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
                <div className="w-12 h-12 rounded-sm bg-[var(--bg-secondary)] border border-[var(--border)] flex items-center justify-center mb-3">
                  <Search className="w-5 h-5 text-[var(--text-muted)] opacity-60" />
                </div>
                <h4 className="text-sm font-semibold text-[var(--text-primary)] mb-1">No deals found</h4>
                <p className="text-xs text-[var(--text-muted)] max-w-sm">Try adjusting your filters or search query to find what you're looking for.</p>
              </div>
            ) : (
              <table className="w-full text-xs text-left whitespace-nowrap">
                <thead className="sticky top-0 bg-[var(--bg-secondary)] border-b border-[var(--border)] z-10">
                  <tr>
                    <th className="px-3 py-2 font-medium text-[var(--text-muted)] cursor-pointer hover:text-[var(--text-primary)] group" onClick={() => handleSort('opportunity_name')}>
                      <div className="flex items-center gap-1">Opportunity {sortField === 'opportunity_name' ? (sortDir === 'asc' ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />) : <ArrowUpDown className="w-3 h-3 opacity-0 group-hover:opacity-50" />}</div>
                    </th>
                    <th className="px-3 py-2 font-medium text-[var(--text-muted)]">Account / BU</th>
                    <th className="px-3 py-2 font-medium text-[var(--text-muted)] text-right cursor-pointer hover:text-[var(--text-primary)] group" onClick={() => handleSort('forecast_acv_amount')}>
                      <div className="flex items-center justify-end gap-1">ACV {sortField === 'forecast_acv_amount' ? (sortDir === 'asc' ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />) : <ArrowUpDown className="w-3 h-3 opacity-0 group-hover:opacity-50" />}</div>
                    </th>
                    <th className="px-3 py-2 font-medium text-[var(--text-muted)] cursor-pointer hover:text-[var(--text-primary)] group" onClick={() => handleSort('close_date')}>
                      <div className="flex items-center gap-1">Close Date {sortField === 'close_date' ? (sortDir === 'asc' ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />) : <ArrowUpDown className="w-3 h-3 opacity-0 group-hover:opacity-50" />}</div>
                    </th>
                    <th className="px-3 py-2 font-medium text-[var(--text-muted)] text-center">Category</th>
                    <th className="px-3 py-2 font-medium text-[var(--text-muted)] text-center">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {filteredDeals.map(d => (
                    <tr
                      key={d.opportunity_id_18}
                      className="hover:bg-[var(--bg-secondary)] cursor-pointer transition-colors"
                      onClick={() => {
                        onSelectOpp(d.opportunity_id_18)
                        onClose()
                      }}
                    >
                      <td className="px-3 py-2">
                        <div className="font-medium text-[var(--text-primary)] max-w-xs truncate" title={d.opportunity_name || d.opportunity_id_18}>
                          {d.opportunity_name || d.opportunity_id_18}
                        </div>
                        <div className="text-[10px] text-[var(--text-muted)] mt-0.5 font-mono">{d.opportunity_id_18}</div>
                      </td>
                      <td className="px-3 py-2">
                        <div className="font-normal text-[var(--text-primary)] max-w-[150px] truncate" title={d.account_name}>{d.account_name || '—'}</div>
                        <div className="text-[10px] text-[var(--text-muted)] mt-0.5 max-w-[150px] truncate">{d.business_unit_primary || '—'}</div>
                      </td>
                      <td className="px-3 py-2 text-right font-semibold text-[var(--text-primary)] tabular-nums">
                        {formatCurrency(d.forecast_acv_amount)}
                      </td>
                      <td className="px-3 py-2 text-[var(--text-secondary)] font-normal tabular-nums">
                        {formatDate(d.close_date)}
                      </td>
                      <td className="px-3 py-2 text-center">
                        <span className="inline-block px-2 py-0.5 rounded-sm text-[10px] font-medium"
                          style={{
                            backgroundColor: `${FORECAST_COLORS[d.forecast_category as keyof typeof FORECAST_COLORS] || '#cbd5e1'}20`,
                            color: FORECAST_COLORS[d.forecast_category as keyof typeof FORECAST_COLORS] || '#64748b'
                          }}
                        >
                          {getForecastCategoryLabel(d.forecast_category)}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-center">
                        <span className={`inline-block px-2 py-0.5 rounded-sm text-[10px] font-medium border ${
                          d.approval_status === 'Approved' ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/20' :
                          d.approval_status === 'Pending Approval' ? 'bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/20' :
                          'bg-slate-500/10 text-slate-700 dark:text-slate-300 border-slate-500/20'
                        }`}>
                          {getApprovalStatusLabel(d.approval_status)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}
