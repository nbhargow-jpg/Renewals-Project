import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer,
} from 'recharts'
import { useQuery } from '@tanstack/react-query'
import { getApprovalByBu } from '@/api/client'
import { APPROVAL_COLORS, APPROVAL_ORDER } from '@/design/tokens'
import { formatACV, formatCount } from '@/utils/format'
import { SkeletonChart } from '@/components/ui/Skeleton'
import InsightCaption from '@/components/ui/InsightCaption'
import { useAppStore } from '@/store/appStore'

interface Props { snapshotId?: string }

export default function ApprovalBuChart({ snapshotId }: Props) {
  const activeId = useAppStore(s => s.activeSnapshotId)
  const snapId = snapshotId ?? activeId ?? undefined

  const { data, isLoading } = useQuery({
    queryKey: ['approval-by-bu', snapId],
    queryFn: () => getApprovalByBu(snapId),
  })

  if (isLoading) return <SkeletonChart />

  const rows: any[] = data?.rows ?? []
  const statuses: string[] = data?.statuses ?? APPROVAL_ORDER

  if (!rows.length) return (
    <div className="card p-5">
      <p className="text-sm text-center py-8" style={{ color: 'var(--text-muted)' }}>No data</p>
    </div>
  )

  return (
    <div className="card p-5">
      <h3 className="font-semibold text-sm mb-1" style={{ color: 'var(--text-primary)' }}>
        Approval Status × Business Unit
      </h3>
      <p className="text-xs mb-4" style={{ color: 'var(--text-muted)' }}>
        ACV breakdown by BU — colour coded by approval status
      </p>

      <ResponsiveContainer width="100%" height={340}>
        <BarChart data={rows} margin={{ bottom: 16, left: 8 }}>
          <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="3 3" />
          <XAxis
            dataKey="business_unit"
            tick={{ fontSize: 10, fill: 'var(--text-muted)' }}
            angle={-25}
            textAnchor="end"
            height={56}
          />
          <YAxis tickFormatter={(v) => formatACV(v)} tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
          <Tooltip
            content={({ payload, label }) => {
              if (!payload?.length) return null
              return (
                <div className="card px-3 py-2 text-xs space-y-1 min-w-44">
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
          <Legend
            iconType="circle"
            iconSize={8}
            formatter={(v) => <span className="text-xs" style={{ color: 'var(--text-primary)' }}>{v}</span>}
          />
          {statuses.map((status) => (
            <Bar
              key={status}
              dataKey={status}
              stackId="stack"
              fill={APPROVAL_COLORS[status] ?? '#94A3B8'}
              animationDuration={700}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>

      <InsightCaption
        text="ACV stacked by approval status per business unit. Hover for exact values."
      />
    </div>
  )
}
