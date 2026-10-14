import { describe, it, expect } from 'vitest'
import axios from 'axios'

describe('V2 Expiry API Contract', () => {
  it('returns all required keys matching frontend expectations and excludes none', async () => {
    const res = await axios.get('http://localhost:8000/api/v2/expiry/summary')
    expect(res.status).toBe(200)
    const data = res.data

    // 1. Mandatory top-level keys
    const requiredKeys = [
      'snapshot_date',
      'compare_date',
      'data_slice',
      'data_slice_key',
      'fiscal_years',
      'categories',
      'grids',
      'acv_by_year',
      'grand_total',
      'slippage',
      'deltas'
    ]
    for (const key of requiredKeys) {
      expect(data).toHaveProperty(key)
      expect(data[key]).not.toBeUndefined()
    }

    // Notice: Frontend MUST NOT read 'total' directly on summary (it must read 'grand_total')
    expect(data.grand_total).toBeDefined()
    expect(typeof data.grand_total.count).toBe('number')
    expect(typeof data.grand_total.acv).toBe('number')

    // 2. Exact contract values for active dataset
    expect(data.grand_total.count).toBe(957)
    expect(data.grand_total.acv).toBeCloseTo(102527193.24, 1)

    // 3. Slippage contract
    expect(data.slippage).toBeDefined()
    expect(data.slippage.count).toBe(105)
    expect(data.slippage.acv).toBeCloseTo(12415568.47, 1)
    expect(Array.isArray(data.slippage.by_quarter)).toBe(true)

    // 4. Fiscal years and grids
    expect(data.fiscal_years.length).toBeGreaterThanOrEqual(2)
    const fy1 = data.fiscal_years[0].label
    const fy2 = data.fiscal_years[1].label
    expect(data.grids[fy1]).toBeDefined()
    expect(data.grids[fy2]).toBeDefined()
    expect(data.acv_by_year[fy1]).toBeDefined()
    expect(data.acv_by_year[fy2]).toBeDefined()

    // 5. Deltas contract
    expect(data.deltas[fy1]).toBeDefined()
    expect(data.deltas[fy1].yesterday).toBeDefined()
    expect(data.deltas[fy1].lastweek).toBeDefined()
  }, 15000)

  it('serves deals endpoint with slippage and category filters', async () => {
    // Slippage deals
    const slipRes = await axios.get('http://localhost:8000/api/v2/expiry/deals?slippage=true')
    expect(slipRes.status).toBe(200)
    expect(Array.isArray(slipRes.data)).toBe(true)
    expect(slipRes.data.length).toBe(105)

    // All deals
    const allRes = await axios.get('http://localhost:8000/api/v2/expiry/deals')
    expect(allRes.status).toBe(200)
    expect(allRes.data.length).toBe(957)
  })
})
