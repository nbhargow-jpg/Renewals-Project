import { useAppStore } from '@/store/appStore'
import SegmentedControl from '@/components/ui/SegmentedControl'

export default function MetricToggle() {
  const { metricMode, setMetricMode } = useAppStore()

  const options = [
    { value: 'Amount', label: 'Amount' },
    { value: 'Count', label: 'Count' },
    { value: 'Both', label: 'Both' },
  ] as const

  return (
    <SegmentedControl
      size="sm"
      options={options as any}
      value={metricMode}
      onChange={(val) => {
        try {
          setMetricMode(val)
        } catch (e) {
          console.error('Failed to save metric mode', e)
        }
      }}
    />
  )
}
