import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer, Cell,
} from 'recharts'
import { useQuery } from '@tanstack/react-query'
import { getTopRegions } from '@/api/client'
import { formatACV, formatCount } from '@/utils/format'
import { SkeletonChart } from '@/components/ui/Skeleton'
import InsightCaption from '@/components/ui/InsightCaption'
import { useAppStore } from '@/store/appStore'

interface Props { snapshotId?: string; topN?: number }

const BAR_COLORS = [
  '#00A3AD','#8080FF','#22C55E','#F59E0B','#EF4444',
  '#3B82F6','#A78BFA','#34D399','#FBBF24','#F87171',
]

export default function RegionBarChart({ snapshotId, topN = 10 }: Props) {
  const activeId = useAppStore(s => s.activeSnapshotId)
  const snapId = snapshotId ?? activeId ?? undefined

  const { data, isLoading } = useQuery({
    queryKey: ['top-regions', snapId, topN],
    queryFn: () => getTopRegions(snapId, topN),
  })

  if (isLoading) return <SkeletonChart />

  const rows = (data?.rows ?? []).sort((a: any, b: any) => b.acv - a.acv)
  const topRegion = rows[0]

  return (
    <div className="card p-5">
      <h3 className="font-semibold text-sm mb-1" style={{ color: 'var(--text-primary)' }}>
        Top {topN} Regions by ACV
      </h3>
      <p className="text-xs mb-4" style={{ color: 'var(--text-muted)' }}>
        Total Forecast ACV per sub-region
      </p>

      <ResponsiveContainer width="100%" height={320}>
        <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 24 }}>
          <CartesianGrid horizontal={false} stroke="var(--border)" strokeDasharray="3 3" />
          <XAxis
            type="number"
            tickFormatter={(v) => formatACV(v)}
            tick={{ fontSize: 11, fill: 'var(--text-muted)' }}
          />
          <YAxis
            type="category"
            dataKey="sub_region"
            width={110}
            tick={{ fontSize: 11, fill: 'var(--text-primary)' }}
          />
          <Tooltip
            cursor={{ fill: 'rgba(0,163,173,0.06)' }}
            content={({ payload }) => {
              if (!payload?.length) return null
              const d = payload[0].payload
              return (
                <div className="card px-3 py-2 text-xs space-y-1">
                  <p className="font-semibold">{d.sub_region}</p>
                  <p>ACV: {formatACV(d.acv)}</p>
                  <p>Count: {formatCount(d.count)}</p>
                </div>
              )
            }}
          />
          <Bar dataKey="acv" radius={[0, 6, 6, 0]} animationDuration={800}>
            {rows.map((_: any, i: number) => (
              <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {topRegion && (
        <InsightCaption
          text={`${topRegion.sub_region} leads with ${formatACV(topRegion.acv)} across ${formatCount(topRegion.count)} opportunities`}
        />
      )}
    </div>
  )
}
