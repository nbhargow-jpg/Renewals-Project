import { describe, it, expect } from 'vitest'
import axios from 'axios'

describe('V2 Overview Deals API Contract & Click Targets', () => {
  const base = 'http://localhost:8000/api/v2/overview/deals'

  it('Total ACV click target: 348 deals / $40,068,990.09', async () => {
    const res = await axios.get(base)
    expect(res.status).toBe(200)
    const data = res.data
    expect(data.count).toBe(348)
    expect(data.acv).toBeCloseTo(40068990.09, 2)
    expect(data.deals.length).toBe(348)
    expect(data.filters_applied).toBeDefined()
  })

  it('Category click targets: Closed, Commit, Best Case, Blank (Not yet proposed), Pipeline (Other)', async () => {
    const rClosed = await axios.get(base, { params: { category: 'Closed' } })
    expect(rClosed.data.count).toBe(0)
    expect(rClosed.data.acv).toBe(0)

    const rCommit = await axios.get(base, { params: { category: 'Commit' } })
    expect(rCommit.data.count).toBe(308)
    expect(rCommit.data.acv).toBeCloseTo(30349636.71, 2)

    const rBC = await axios.get(base, { params: { category: 'Best Case' } })
    expect(rBC.data.count).toBe(34)
    expect(rBC.data.acv).toBeCloseTo(9456843.36, 2)

    const rBlank = await axios.get(base, { params: { category: 'Blank' } })
    expect(rBlank.data.count).toBe(5)
    expect(rBlank.data.acv).toBeCloseTo(212772.40, 2)

    const rPipe = await axios.get(base, { params: { category: 'Pipeline' } })
    expect(rPipe.data.count).toBe(1)
    expect(rPipe.data.acv).toBeCloseTo(49737.62, 2)

    // Sum check across all categories equals 348 / $40.07M
    const sumCount = rClosed.data.count + rCommit.data.count + rBC.data.count + rBlank.data.count + rPipe.data.count
    const sumAcv = rClosed.data.acv + rCommit.data.acv + rBC.data.acv + rBlank.data.acv + rPipe.data.acv
    expect(sumCount).toBe(348)
    expect(sumAcv).toBeCloseTo(40068990.09, 2)
  })

  it('Slipped to next year click targets for both comparisons', async () => {
    const rY = await axios.get(base, { params: { kind: 'slipped', compare: 'yesterday' } })
    expect(rY.data.count).toBe(2)
    expect(rY.data.acv).toBeCloseTo(59514.21, 2)
    expect(rY.data.deals.length).toBe(2)

    const rLW = await axios.get(base, { params: { kind: 'slipped', compare: 'last_week' } })
    expect(rLW.data.count).toBe(5)
    expect(rLW.data.acv).toBeCloseTo(1315839.07, 2)
    expect(rLW.data.deals.length).toBe(5)
  })

  it('Delta chips reconciliation: delta_yesterday (+2 / +$476.2K) and delta_lastweek (+14 / +$904.1K)', async () => {
    const rY = await axios.get(base, { params: { kind: 'delta_yesterday' } })
    const dY = rY.data
    expect(dY.count).toBe(2)
    expect(dY.acv).toBeCloseTo(476219.18, 2)
    expect(dY.delta_groups).toBeDefined()
    expect(dY.delta_groups.added.count).toBe(4)
    expect(dY.delta_groups.added.acv).toBeCloseTo(538915.01, 2)
    expect(dY.delta_groups.left.count).toBe(2)
    expect(dY.delta_groups.left.acv).toBeCloseTo(59514.21, 2)
    expect(dY.delta_groups.amount_changed.count).toBe(2)
    expect(dY.delta_groups.amount_changed.acv).toBeCloseTo(-3181.62, 2)
    // Reconciliation check
    expect(dY.delta_groups.added.count - dY.delta_groups.left.count).toBe(dY.count)
    expect(dY.delta_groups.added.acv - dY.delta_groups.left.acv + dY.delta_groups.amount_changed.acv).toBeCloseTo(dY.acv, 2)

    const rLW = await axios.get(base, { params: { kind: 'delta_lastweek' } })
    const dLW = rLW.data
    expect(dLW.count).toBe(14)
    expect(dLW.acv).toBeCloseTo(904132.33, 2)
    expect(dLW.delta_groups).toBeDefined()
    expect(dLW.delta_groups.added.count).toBe(20)
    expect(dLW.delta_groups.added.acv).toBeCloseTo(2118711.22, 2)
    expect(dLW.delta_groups.left.count).toBe(6)
    expect(dLW.delta_groups.left.acv).toBeCloseTo(1391391.20, 2)
    expect(dLW.delta_groups.amount_changed.count).toBe(10)
    expect(dLW.delta_groups.amount_changed.acv).toBeCloseTo(176812.31, 2)
    // Reconciliation check
    expect(dLW.delta_groups.added.count - dLW.delta_groups.left.count).toBe(dLW.count)
    expect(dLW.delta_groups.added.acv - dLW.delta_groups.left.acv + dLW.delta_groups.amount_changed.acv).toBeCloseTo(dLW.acv, 2)
  })
})
