import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer,
} from 'recharts'
import { useQuery } from '@tanstack/react-query'
import { getExpiryQuarters } from '@/api/client'
import { FORECAST_COLORS, FORECAST_ORDER } from '@/design/tokens'
import { formatACV } from '@/utils/format'
import { SkeletonChart } from '@/components/ui/Skeleton'
import InsightCaption from '@/components/ui/InsightCaption'
import { useAppStore } from '@/store/appStore'

interface Props { snapshotId?: string }

export default function ExpiryQuarterBar({ snapshotId }: Props) {
  const activeId = useAppStore(s => s.activeSnapshotId)
  const snapId = snapshotId ?? activeId ?? undefined

  const { data, isLoading } = useQuery({
    queryKey: ['expiry-quarters', snapId],
    queryFn: () => getExpiryQuarters(snapId),
  })

  if (isLoading) return <SkeletonChart />

  const raw: any[] = data?.rows ?? []

  // Pivot: {expiry_period: {Closed: X, Commit: Y, ...}}
  const pivotMap: Record<string, Record<string, number>> = {}
  for (const r of raw) {
    if (!pivotMap[r.service_expiry_period]) pivotMap[r.service_expiry_period] = {}
    pivotMap[r.service_expiry_period][r.forecast_category] = r.acv
  }

  // Sort quarters
  const quarters = Object.keys(pivotMap).sort()
  const chartData = quarters.map(q => ({
    quarter: q,
    ...pivotMap[q],
    total: Object.values(pivotMap[q]).reduce((a, b) => a + b, 0),
  }))

  const peakQ = chartData.reduce((a, b) => (b.total > a.total ? b : a), chartData[0])

  return (
    <div className="card p-5">
      <h3 className="font-semibold text-sm mb-1" style={{ color: 'var(--text-primary)' }}>
        Pipeline by Expiry Quarter
      </h3>
      <p className="text-xs mb-4" style={{ color: 'var(--text-muted)' }}>
        ACV stacked by forecast category per service expiry period
      </p>

      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={chartData} margin={{ bottom: 12 }}>
          <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="3 3" />
          <XAxis
            dataKey="quarter"
            tick={{ fontSize: 11, fill: 'var(--text-muted)' }}
            angle={-30}
            textAnchor="end"
            height={48}
          />
          <YAxis tickFormatter={(v) => formatACV(v)} tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
          <Tooltip
            content={({ payload, label }) => {
              if (!payload?.length) return null
              return (
                <div className="card px-3 py-2 text-xs space-y-1 min-w-40">
                  <p className="font-semibold">{label}</p>
                  {payload.map((p: any) => (
                    <div key={p.dataKey} className="flex justify-between gap-4">
                      <span style={{ color: p.fill }}>{p.dataKey}</span>
                      <span>{formatACV(p.value)}</span>
                    </div>
                  ))}
                </div>
              )
            }}
          />
          <Legend iconType="circle" iconSize={8}
            formatter={(v) => <span className="text-xs" style={{ color: 'var(--text-primary)' }}>{v}</span>}
          />
          {FORECAST_ORDER.map((cat) => (
            <Bar
              key={cat}
              dataKey={cat}
              stackId="stack"
              fill={FORECAST_COLORS[cat]}
              animationDuration={800}
              radius={cat === 'Blank' ? [4, 4, 0, 0] : [0, 0, 0, 0]}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>

      {peakQ && (
        <InsightCaption
          text={`${peakQ.quarter} has the largest expiry ACV at ${formatACV(peakQ.total)}`}
        />
      )}
    </div>
  )
}
