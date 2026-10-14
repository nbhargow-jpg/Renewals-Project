import React, { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Search,
  ArrowUpDown,
  ExternalLink,
  DollarSign,
  Layers,
  Building,
  Globe,
  Calendar,
  AlertCircle,
} from 'lucide-react'
import { getOpportunities, OppFilters } from '@/api/client'
import { formatACV } from '@/utils/format'
import Drawer from '@/components/ui/Drawer'
import Badge, { ForecastBadge, ApprovalBadge } from '@/components/ui/Badge'
import { Skeleton } from '@/components/ui/Skeleton'

interface OpportunitiesListDrawerProps {
  isOpen: boolean
  onClose: () => void
  title: string
  subtitle?: string
  filters: OppFilters
  onSelectOpp: (oppId: string) => void
}

type SortField = 'forecast_acv_amount' | 'opportunity_name' | 'account_name' | 'business_unit_primary' | 'service_expiry_period'
type SortOrder = 'asc' | 'desc'

export default function OpportunitiesListDrawer({
  isOpen,
  onClose,
  title,
  subtitle,
  filters,
  onSelectOpp,
}: OpportunitiesListDrawerProps) {
  const [searchTerm, setSearchTerm] = useState('')
  const [sortField, setSortField] = useState<SortField>('forecast_acv_amount')
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc')

  const { data, isLoading } = useQuery({
    queryKey: ['opportunities-list', filters],
    queryFn: () =>
      getOpportunities({
        ...filters,
        pageSize: 150,
      }),
    enabled: isOpen,
  })

  const items = data?.items || []
  const totalCount = data?.total || items.length

  const filteredAndSortedItems = useMemo(() => {
    let result = [...items]

    if (searchTerm.trim()) {
      const q = searchTerm.toLowerCase()
      result = result.filter(
        (item: any) =>
          item.opportunity_name?.toLowerCase().includes(q) ||
          item.account_name?.toLowerCase().includes(q) ||
          item.opportunity_id_18?.toLowerCase().includes(q) ||
          item.business_unit_primary?.toLowerCase().includes(q) ||
          item.sub_region?.toLowerCase().includes(q)
      )
    }

    result.sort((a: any, b: any) => {
      let valA = a[sortField] ?? ''
      let valB = b[sortField] ?? ''

      if (sortField === 'forecast_acv_amount') {
        valA = Number(valA) || 0
        valB = Number(valB) || 0
      }

      if (valA < valB) return sortOrder === 'asc' ? -1 : 1
      if (valA > valB) return sortOrder === 'asc' ? 1 : -1
      return 0
    })

    return result
  }, [items, searchTerm, sortField, sortOrder])

  const totalAcvSum = useMemo(() => {
    return filteredAndSortedItems.reduce((acc: number, item: any) => acc + (Number(item.forecast_acv_amount) || 0), 0)
  }, [filteredAndSortedItems])

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortField(field)
      setSortOrder('desc')
    }
  }

  return (
    <Drawer
      isOpen={isOpen}
      onClose={onClose}
      title={title}
      subtitle={subtitle || `${totalCount} deals found`}
      size="xl"
    >
      <div className="flex flex-col h-full space-y-4">
        {/* Header Summary & Search Bar */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 p-3 rounded-xl bg-slate-50 dark:bg-white/[0.03] border border-slate-200/80 dark:border-white/10">
          <div className="flex items-center gap-4">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                Filtered Deals
              </p>
              <p className="text-lg font-bold text-slate-900 dark:text-white tabular-nums">
                {filteredAndSortedItems.length}
              </p>
            </div>
            <div className="h-8 w-px bg-slate-200 dark:bg-white/10" />
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                Total ACV
              </p>
              <p className="text-lg font-bold text-teal-600 dark:text-teal-400 tabular-nums">
                {formatACV(totalAcvSum)}
              </p>
            </div>
          </div>

          <div className="relative flex-1 sm:max-w-xs">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search deals, accounts..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 rounded-lg text-xs bg-white dark:bg-slate-900 border border-slate-200 dark:border-white/10 text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500/50"
            />
          </div>
        </div>

        {/* Opportunities Table */}
        <div className="flex-1 overflow-auto rounded-xl border border-slate-200/80 dark:border-white/10 bg-white dark:bg-slate-900/50">
          {isLoading ? (
            <div className="p-4 space-y-3">
              {[...Array(6)].map((_, i) => (
                <Skeleton key={i} className="h-10 w-full rounded-lg" />
              ))}
            </div>
          ) : filteredAndSortedItems.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center text-slate-400">
              <AlertCircle className="w-10 h-10 mb-2 opacity-50" />
              <p className="text-sm font-semibold text-slate-600 dark:text-slate-300">No opportunities found</p>
              <p className="text-xs text-slate-400 mt-1">Try refining your search terms or filters</p>
            </div>
          ) : (
            <table className="w-full text-left border-collapse text-xs">
              <thead className="sticky top-0 bg-slate-100 dark:bg-slate-800/90 z-10 border-b border-slate-200 dark:border-white/10 select-none">
                <tr>
                  <th
                    onClick={() => handleSort('opportunity_name')}
                    className="p-3 font-semibold text-slate-700 dark:text-slate-300 cursor-pointer hover:text-teal-500"
                  >
                    <div className="flex items-center gap-1.5">
                      Opportunity / Account
                      <ArrowUpDown className="w-3 h-3 opacity-60" />
                    </div>
                  </th>
                  <th
                    onClick={() => handleSort('forecast_acv_amount')}
                    className="p-3 font-semibold text-slate-700 dark:text-slate-300 cursor-pointer hover:text-teal-500 text-right"
                  >
                    <div className="flex items-center justify-end gap-1.5">
                      ACV
                      <ArrowUpDown className="w-3 h-3 opacity-60" />
                    </div>
                  </th>
                  <th className="p-3 font-semibold text-slate-700 dark:text-slate-300">Forecast Category</th>
                  <th className="p-3 font-semibold text-slate-700 dark:text-slate-300">Approval Status</th>
                  <th
                    onClick={() => handleSort('business_unit_primary')}
                    className="p-3 font-semibold text-slate-700 dark:text-slate-300 cursor-pointer hover:text-teal-500"
                  >
                    <div className="flex items-center gap-1.5">
                      BU
                      <ArrowUpDown className="w-3 h-3 opacity-60" />
                    </div>
                  </th>
                  <th
                    onClick={() => handleSort('service_expiry_period')}
                    className="p-3 font-semibold text-slate-700 dark:text-slate-300 cursor-pointer hover:text-teal-500"
                  >
                    <div className="flex items-center gap-1.5">
                      Expiry
                      <ArrowUpDown className="w-3 h-3 opacity-60" />
                    </div>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-white/5">
                {filteredAndSortedItems.map((opp: any) => (
                  <tr
                    key={opp.id || opp.opportunity_id_18}
                    onClick={() => onSelectOpp(opp.opportunity_id_18)}
                    className="cursor-pointer hover:bg-slate-50 dark:hover:bg-white/[0.04] transition-colors group"
                  >
                    <td className="p-3 max-w-[240px]">
                      <div className="font-semibold text-slate-900 dark:text-white group-hover:text-teal-600 dark:group-hover:text-teal-400 truncate flex items-center gap-1.5">
                        {opp.opportunity_name || 'Unnamed Opportunity'}
                        <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
                      </div>
                      <div className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
                        {opp.account_name} · <span className="font-mono text-[10px]">{opp.opportunity_id_18}</span>
                      </div>
                    </td>
                    <td className="p-3 text-right font-bold text-slate-900 dark:text-white tabular-nums whitespace-nowrap">
                      {formatACV(opp.forecast_acv_amount)}
                    </td>
                    <td className="p-3 whitespace-nowrap">
                      <ForecastBadge category={opp.forecast_category} />
                    </td>
                    <td className="p-3 whitespace-nowrap">
                      <ApprovalBadge status={opp.approval_status} />
                    </td>
                    <td className="p-3 text-slate-600 dark:text-slate-300 truncate max-w-[120px]">
                      {opp.business_unit_primary || opp.business_unit_raw || '—'}
                    </td>
                    <td className="p-3 font-medium text-slate-700 dark:text-slate-300 whitespace-nowrap">
                      {opp.service_expiry_period || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </Drawer>
  )
}
