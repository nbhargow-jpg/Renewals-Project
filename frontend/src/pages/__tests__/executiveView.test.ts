import { describe, it, expect } from 'vitest'
import axios from 'axios'

describe('Executive View Contract & Exact Metric Tests', () => {
  const baseOverview = 'http://localhost:8000/api/v2/overview/summary'
  const baseDelayed = 'http://localhost:8000/api/v2/delayed/summary?compare=yesterday'

  it('Headline numbers equal Overview endpoint for Oct 7 (348 deals / $40,068,990.09)', async () => {
    const res = await axios.get(baseOverview)
    expect(res.status).toBe(200)
    const total = res.data.total
    expect(total.count).toBe(348)
    expect(total.acv).toBeCloseTo(40068990.09, 2)
  })

  it('Forecast categories equal Overview endpoint (Commit, Best Case, Pipeline, Not yet proposed)', async () => {
    const res = await axios.get(baseOverview)
    const cats = res.data.categories

    // Commit: 308 / $30,349,636.71
    expect(cats.Commit.count).toBe(308)
    expect(cats.Commit.acv).toBeCloseTo(30349636.71, 2)

    // Best Case: 34 / $9,456,843.36
    expect(cats['Best Case'].count).toBe(34)
    expect(cats['Best Case'].acv).toBeCloseTo(9456843.36, 2)

    // Pipeline: 1 / $49,737.62
    expect(cats.Pipeline.count).toBe(1)
    expect(cats.Pipeline.acv).toBeCloseTo(49737.62, 2)

    // Not yet proposed (Blank): 5 / $212,772.40
    expect(cats.Blank.count).toBe(5)
    expect(cats.Blank.acv).toBeCloseTo(212772.40, 2)
  })

  it(
    'Delayed total and Risk block counts equal Delayed endpoint (Delayed total 9 / $339,305.70)',
    async () => {
      const res = await axios.get(baseDelayed)
      expect(res.status).toBe(200)
      const data = res.data

      // Delayed total: 9 / $339,305.70
      expect(data.total.count).toBe(9)
      expect(data.total.acv).toBeCloseTo(339305.70, 2)

      // Overdue: 6 deals / $228,071.49
      expect(data.overdue.count).toBe(6)
      expect(data.overdue.acv).toBeCloseTo(228071.49, 2)

      // Slipped to next year: 2 deals / $59,514.21
      expect(data.slipped.count).toBe(2)
      expect(data.slipped.acv).toBeCloseTo(59514.21, 2)

      // Lost / Removed: 0 deals
      expect(data.lost.count).toBe(0)
      expect(data.lost.acv).toBe(0)
    },
    20000
  )
})
