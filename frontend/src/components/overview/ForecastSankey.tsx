import React, { useEffect, useRef, useState } from 'react'
import * as d3 from 'd3'
import { sankey, sankeyLinkHorizontal } from 'd3-sankey'
import { motion, AnimatePresence } from 'framer-motion'
import { GitCommit, ArrowRight, X, ExternalLink, Info } from 'lucide-react'
import { FORECAST_COLORS } from '@/design/tokens'
import { formatACV, formatCount } from '@/utils/format'
import Drawer from '@/components/ui/Drawer'
import { ForecastBadge, ApprovalBadge } from '@/components/ui/Badge'

export interface SankeyFlow {
  from: string
  to: string
  count: number
  acv: number
  opportunities?: any[]
}

interface ForecastSankeyProps {
  flows?: SankeyFlow[]
  fromLabel?: string
  toLabel?: string
  onSelectOpportunity?: (oppId: string) => void
  loading?: boolean
}

const TO_SUFFIX = "'_target"

export default function ForecastSankey({
  flows = [],
  fromLabel = 'Yesterday',
  toLabel = 'Today',
  onSelectOpportunity,
  loading = false,
}: ForecastSankeyProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const [selectedFlow, setSelectedFlow] = useState<SankeyFlow | null>(null)
  const [hoveredFlow, setHoveredFlow] = useState<{
    from: string
    to: string
    count: number
    acv: number
    x: number
    y: number
  } | null>(null)

  // Normalise category label for display
  const normaliseCat = (cat: string) => {
    if (!cat || cat.trim() === '' || cat.toLowerCase() === 'blank') {
      return '(Blank)'
    }
    return cat
  }

  useEffect(() => {
    if (!svgRef.current || flows.length === 0) return
    renderSankeyChart()
  }, [flows])

  const renderSankeyChart = () => {
    const el = svgRef.current
    if (!el) return
    const width = el.clientWidth || 640
    const height = 300

    d3.select(el).selectAll('*').remove()

    // Filter flows with count > 0
    const validFlows = flows.filter((f) => f.count > 0)
    if (validFlows.length === 0) return

    // Collect unique source and target node names
    const sourceNodes = new Set<string>()
    const targetNodes = new Set<string>()

    validFlows.forEach((f) => {
      sourceNodes.add(normaliseCat(f.from))
      targetNodes.add(normaliseCat(f.to) + TO_SUFFIX)
    })

    const allNodes = [
      ...Array.from(sourceNodes).map((name) => ({ name, isTarget: false })),
      ...Array.from(targetNodes).map((name) => ({ name, isTarget: true })),
    ]

    const nodeIndex = (name: string) => allNodes.findIndex((n) => n.name === name)

    const sankeyLinks = validFlows.map((f) => ({
      source: nodeIndex(normaliseCat(f.from)),
      target: nodeIndex(normaliseCat(f.to) + TO_SUFFIX),
      // Prompt 4: "Node width = opportunity count, hover shows ACV"
      value: Math.max(f.count, 1),
      realCount: f.count,
      acv: f.acv,
      fromCat: normaliseCat(f.from),
      toCat: normaliseCat(f.to),
      rawFlow: f,
    }))

    const sankeyGenerator = sankey()
      .nodeWidth(16)
      .nodePadding(14)
      .extent([
        [40, 16],
        [width - 40, height - 16],
      ])

    let sNodes: any[] = []
    let sLinks: any[] = []

    try {
      const res = sankeyGenerator({
        nodes: allNodes.map((d) => ({ ...d })),
        links: sankeyLinks.map((d) => ({ ...d })),
      } as any)
      sNodes = res.nodes
      sLinks = res.links
    } catch (err) {
      console.warn('Sankey layout error', err)
      return
    }

    const svg = d3
      .select(el)
      .attr('viewBox', `0 0 ${width} ${height}`)
      .attr('width', '100%')
      .attr('height', height)

    // Defs for link gradients
    const defs = svg.append('defs')

    sLinks.forEach((link: any, i: number) => {
      const gradId = `sankey-grad-${i}`
      const grad = defs
        .append('linearGradient')
        .attr('id', gradId)
        .attr('gradientUnits', 'userSpaceOnUse')
        .attr('x1', link.source.x1)
        .attr('x2', link.target.x0)

      const colorFrom =
        FORECAST_COLORS[link.fromCat.replace('(Blank)', 'Blank')] || '#8080FF'
      const colorTo =
        FORECAST_COLORS[link.toCat.replace('(Blank)', 'Blank')] || '#00A3AD'

      grad.append('stop').attr('offset', '0%').attr('stop-color', colorFrom)
      grad.append('stop').attr('offset', '100%').attr('stop-color', colorTo)
    })

    // Draw Links
    svg
      .append('g')
      .selectAll('path')
      .data(sLinks)
      .join('path')
      .attr('d', sankeyLinkHorizontal() as any)
      .attr('fill', 'none')
      .attr('stroke', (_: any, i: number) => `url(#sankey-grad-${i})`)
      .attr('stroke-opacity', 0.45)
      .attr('stroke-width', (d: any) => Math.max(2, d.width))
      .style('cursor', 'pointer')
      .on('mouseenter', function (event, d: any) {
        d3.select(this).attr('stroke-opacity', 0.85).attr('stroke-width', Math.max(3, d.width + 2))
        const rect = el.getBoundingClientRect()
        setHoveredFlow({
          from: d.fromCat,
          to: d.toCat,
          count: d.realCount,
          acv: d.acv,
          x: event.clientX - rect.left,
          y: event.clientY - rect.top,
        })
      })
      .on('mouseleave', function (event, d: any) {
        d3.select(this).attr('stroke-opacity', 0.45).attr('stroke-width', Math.max(2, d.width))
        setHoveredFlow(null)
      })
      .on('click', (_: any, d: any) => {
        setSelectedFlow(d.rawFlow)
      })

    // Draw Nodes
    svg
      .append('g')
      .selectAll('rect')
      .data(sNodes)
      .join('rect')
      .attr('x', (d: any) => d.x0)
      .attr('y', (d: any) => d.y0)
      .attr('height', (d: any) => Math.max(2, d.y1 - d.y0))
      .attr('width', (d: any) => d.x1 - d.x0)
      .attr('fill', (d: any) => {
        const cat = d.name.replace(TO_SUFFIX, '').replace('(Blank)', 'Blank')
        return FORECAST_COLORS[cat] || '#8080FF'
      })
      .attr('rx', 4)
      .attr('opacity', 0.95)

    // Node labels
    svg
      .append('g')
      .selectAll('text')
      .data(sNodes)
      .join('text')
      .attr('x', (d: any) => (d.x0 < width / 2 ? d.x0 - 8 : d.x1 + 8))
      .attr('y', (d: any) => (d.y1 + d.y0) / 2)
      .attr('dy', '0.35em')
      .attr('text-anchor', (d: any) => (d.x0 < width / 2 ? 'end' : 'start'))
      .attr('font-size', '11px')
      .attr('font-weight', '600')
      .attr('fill', 'var(--text-primary)')
      .text((d: any) => d.name.replace(TO_SUFFIX, ''))
  }

  const totalMoves = flows.reduce((sum, f) => sum + f.count, 0)
  const totalMoveACV = flows.reduce((sum, f) => sum + f.acv, 0)

  return (
    <div className="card p-6 relative">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="font-bold text-lg text-[var(--text-primary)]">
              Forecast Category Movement
            </h2>
            <span className="text-xs px-2.5 py-0.5 rounded-sm font-semibold bg-teal-500/10 text-teal-600 dark:text-teal-400 border border-teal-500/20">
              Sankey
            </span>
          </div>
          <p className="text-xs text-[var(--text-muted)] mt-0.5">
            Transitions from {fromLabel} to {toLabel}. Node width indicates deal count; hover reveals ACV.
          </p>
        </div>

        <div className="text-right">
          <p className="text-xs font-semibold text-[var(--text-muted)] uppercase">
            Total Shifts
          </p>
          <p className="font-bold text-sm text-teal-600 dark:text-teal-400 tabular-nums">
            {formatCount(totalMoves)} deals ({formatACV(totalMoveACV)})
          </p>
        </div>
      </div>

      {/* Sankey Chart SVG Container */}
      <div className="relative min-h-[300px] w-full flex items-center justify-center">
        {loading ? (
          <div className="skeleton-shimmer w-full h-[300px] rounded-xl" />
        ) : flows.length === 0 ? (
          <div className="py-16 text-center text-xs text-[var(--text-muted)]">
            No category movements recorded between these snapshot dates.
          </div>
        ) : (
          <>
            <svg ref={svgRef} className="w-full h-[300px] overflow-visible" />

            {/* Hover Tooltip */}
            <AnimatePresence>
              {hoveredFlow && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  style={{
                    position: 'absolute',
                    left: Math.min(hoveredFlow.x + 10, 480),
                    top: Math.max(hoveredFlow.y - 45, 10),
                    pointerEvents: 'none',
                  }}
                  className="z-30 px-3 py-2 rounded-xl bg-[var(--bg-card)] border border-[var(--border)] shadow-xl text-xs"
                >
                  <p className="font-bold text-[var(--text-primary)] flex items-center gap-1.5">
                    <span>{hoveredFlow.from}</span>
                    <ArrowRight className="w-3 h-3 text-teal-500" />
                    <span>{hoveredFlow.to}</span>
                  </p>
                  <div className="flex items-center gap-3 mt-1 text-[11px] text-[var(--text-muted)]">
                    <span>
                      Deals:{' '}
                      <strong className="text-[var(--text-primary)] tabular-nums">
                        {hoveredFlow.count}
                      </strong>
                    </span>
                    <span>
                      ACV:{' '}
                      <strong className="text-teal-600 dark:text-teal-400 tabular-nums">
                        {formatACV(hoveredFlow.acv)}
                      </strong>
                    </span>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </>
        )}
      </div>

      {/* Footer hint */}
      <div className="flex items-center justify-between text-xs text-[var(--text-muted)] pt-3 border-t border-[var(--border)] mt-2">
        <span className="font-semibold text-[11px] uppercase tracking-wider text-[var(--text-muted)]">
          {fromLabel} (Source)
        </span>
        <span className="text-[11px] italic">
          Click any flow ribbon to open the complete list of opportunities
        </span>
        <span className="font-semibold text-[11px] uppercase tracking-wider text-[var(--text-muted)]">
          {toLabel} (Target)
        </span>
      </div>

      {/* Flow Drilldown Drawer */}
      <Drawer
        isOpen={!!selectedFlow}
        onClose={() => setSelectedFlow(null)}
        title={`${normaliseCat(selectedFlow?.from || '')} → ${normaliseCat(
          selectedFlow?.to || ''
        )} Movement`}
        subtitle={`${selectedFlow?.count ?? 0} deals totaling ${formatACV(
          selectedFlow?.acv ?? 0
        )}`}
        size="md"
      >
        <div className="space-y-3">
          {(!selectedFlow?.opportunities || selectedFlow.opportunities.length === 0) ? (
            <div className="py-8 text-center text-xs text-[var(--text-muted)]">
              No individual opportunity details cached for this movement.
            </div>
          ) : (
            selectedFlow.opportunities.map((opp: any, idx: number) => (
              <div
                key={opp.opportunity_id_18 || idx}
                onClick={() => {
                  setSelectedFlow(null)
                  onSelectOpportunity?.(opp.opportunity_id_18)
                }}
                className="p-3.5 rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] hover:border-teal-500/50 hover:bg-[var(--bg-card)] transition-all cursor-pointer group shadow-sm"
              >
                <div className="flex items-start justify-between gap-2 mb-1.5">
                  <div className="min-w-0">
                    <p className="font-semibold text-xs text-[var(--text-primary)] group-hover:text-teal-600 dark:group-hover:text-teal-400 truncate">
                      {opp.opportunity_name || opp.opportunity_id_18}
                    </p>
                    <p className="text-[11px] text-[var(--text-muted)] truncate">
                      {opp.account_name || 'N/A'}
                    </p>
                  </div>
                  <p className="font-bold text-xs text-teal-600 dark:text-teal-400 tabular-nums flex-shrink-0">
                    {formatACV(opp.acv ?? 0)}
                  </p>
                </div>

                <div className="flex items-center justify-between pt-2 border-t border-[var(--border)] text-[10.5px]">
                  <div className="flex items-center gap-1.5">
                    <span className="px-2 py-0.5 rounded font-medium bg-[var(--bg-card)] text-[var(--text-muted)] border border-[var(--border)]">
                      {normaliseCat(opp.old_category)}
                    </span>
                    <ArrowRight className="w-3 h-3 text-teal-500" />
                    <ForecastBadge category={normaliseCat(opp.new_category)} />
                  </div>
                  <span className="text-teal-600 dark:text-teal-400 font-semibold inline-flex items-center gap-0.5 group-hover:translate-x-0.5 transition-transform">
                    View timeline <ArrowRight className="w-3 h-3" />
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </Drawer>
    </div>
  )
}
