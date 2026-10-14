import { useEffect, useRef } from 'react'
import * as d3 from 'd3'
import { sankey, sankeyLinkHorizontal } from 'd3-sankey'
import { useQuery } from '@tanstack/react-query'
import { getForecastMovement } from '@/api/client'
import { FORECAST_COLORS } from '@/design/tokens'
import { formatACV, formatCount } from '@/utils/format'
import { SkeletonChart } from '@/components/ui/Skeleton'
import InsightCaption from '@/components/ui/InsightCaption'
import { useAppStore } from '@/store/appStore'

interface Props { snapshotId?: string; compareTo?: string }

const CATEGORIES = ['Closed', 'Commit', 'Best Case', 'Pipeline', 'Blank']
// Suffix "'" for "to" nodes so they have unique IDs
const TO_SUFFIX = "'"

export default function ForecastMovementSankey({ snapshotId, compareTo }: Props) {
  const svgRef = useRef<SVGSVGElement>(null)
  const activeId = useAppStore(s => s.activeSnapshotId)
  const snapId = snapshotId ?? activeId ?? undefined

  const { data, isLoading } = useQuery({
    queryKey: ['forecast-movement', snapId, compareTo],
    queryFn: () => getForecastMovement(snapId, compareTo),
  })

  useEffect(() => {
    if (!svgRef.current || !data?.links?.length) return
    drawSankey(svgRef.current, data.links)
  }, [data])

  if (isLoading) return <SkeletonChart />

  const links: any[] = data?.links ?? []
  if (!links.length) {
    return (
      <div className="card p-5">
        <h3 className="font-semibold text-sm mb-2" style={{ color: 'var(--text-primary)' }}>
          Forecast Category Movement
        </h3>
        <p className="text-xs text-center py-12" style={{ color: 'var(--text-muted)' }}>
          No movement data — upload both today and yesterday snapshots.
        </p>
      </div>
    )
  }

  const totalMoved = links.reduce((s, l) => s + l.count, 0)

  return (
    <div className="card p-5">
      <h3 className="font-semibold text-sm mb-1" style={{ color: 'var(--text-primary)' }}>
        Forecast Category Movement
      </h3>
      <p className="text-xs mb-3" style={{ color: 'var(--text-muted)' }}>
        How opportunities moved between categories since yesterday
      </p>
      <svg ref={svgRef} width="100%" height="300" />
      <InsightCaption
        text={`${formatCount(totalMoved)} opportunities changed forecast category since yesterday`}
      />
    </div>
  )
}

function drawSankey(svg: SVGSVGElement, links: any[]) {
  const el = svg
  const W = el.clientWidth || 600
  const H = 300

  d3.select(el).selectAll('*').remove()

  // Build node list
  const nodeNames = new Set<string>()
  links.forEach(l => {
    nodeNames.add(l.from)
    nodeNames.add(l.to + TO_SUFFIX)
  })

  const nodes = Array.from(nodeNames).map(name => ({ name }))
  const nodeIndex = (name: string) => nodes.findIndex(n => n.name === name)

  const sankeyLinks = links.map(l => ({
    source: nodeIndex(l.from),
    target: nodeIndex(l.to + TO_SUFFIX),
    value: Math.max(l.acv, 1),
    count: l.count,
    fromCat: l.from,
    toCat: l.to,
  }))

  const sankeyGen = sankey()
    .nodeWidth(16)
    .nodePadding(12)
    .extent([[24, 12], [W - 24, H - 12]])

  const { nodes: sNodes, links: sLinks } = sankeyGen({
    nodes: nodes.map(d => ({ ...d })),
    links: sankeyLinks.map(d => ({ ...d })),
  } as any)

  const svgEl = d3.select(el)
    .attr('viewBox', `0 0 ${W} ${H}`)

  // Links
  svgEl.append('g')
    .selectAll('path')
    .data(sLinks)
    .join('path')
    .attr('d', sankeyLinkHorizontal() as any)
    .attr('fill', 'none')
    .attr('stroke', (d: any) => FORECAST_COLORS[d.fromCat] ?? '#94A3B8')
    .attr('stroke-opacity', 0.35)
    .attr('stroke-width', (d: any) => Math.max(1, (d as any).width))

  // Nodes
  svgEl.append('g')
    .selectAll('rect')
    .data(sNodes)
    .join('rect')
    .attr('x', (d: any) => d.x0)
    .attr('y', (d: any) => d.y0)
    .attr('height', (d: any) => Math.max(1, d.y1 - d.y0))
    .attr('width', (d: any) => d.x1 - d.x0)
    .attr('fill', (d: any) => {
      const cat = (d.name as string).replace(TO_SUFFIX, '')
      return FORECAST_COLORS[cat] ?? '#94A3B8'
    })
    .attr('rx', 3)

  // Labels
  svgEl.append('g')
    .selectAll('text')
    .data(sNodes)
    .join('text')
    .attr('x', (d: any) => d.x0 < W / 2 ? d.x1 + 6 : d.x0 - 6)
    .attr('y', (d: any) => (d.y1 + d.y0) / 2)
    .attr('dy', '0.35em')
    .attr('text-anchor', (d: any) => d.x0 < W / 2 ? 'start' : 'end')
    .attr('font-size', 10)
    .attr('fill', 'currentColor')
    .attr('opacity', 0.8)
    .text((d: any) => (d.name as string).replace(TO_SUFFIX, ''))
}
