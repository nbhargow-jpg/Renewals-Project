import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import CompactGrid from './CompactGrid'

describe('CompactGrid', () => {
  const mockTotals = {
    category: { Commit: { count: 10, acv: 1000 } },
    grand: { count: 10, acv: 1000 }
  }
  const mockRows = [
    {
      id: 'Q1-2026',
      label: 'Q1 2026',
      cells: { Commit: { count: 10, acv: 1000 } },
      total: { count: 10, acv: 1000 }
    }
  ]

  it('renders heatmap in Value mode', () => {
    const { container } = render(
      <CompactGrid 
        title="Test Grid" 
        columns={['Commit']} 
        rows={mockRows} 
        totals={mockTotals} 
        metricMode="Amount" 
        heatMode="Value"
        onCellClick={vi.fn()} 
      />
    )
    expect(screen.getAllByText('$1K').length).toBeGreaterThan(0)
    // It should have the intense pale teal background for Value mode
    const td = screen.getAllByText('$1K')[0].closest('td')
    expect(td?.style.backgroundColor).toContain('rgba(14, 165, 233')
  })

  it('renders heatmap in Change mode vs Yesterday', () => {
    const deltas = {
      yesterday: {
        matrix: { 'Q1-2026': { Commit: { count: 1, acv: 100 } } }
      }
    }
    const { container } = render(
      <CompactGrid 
        title="Test Grid" 
        columns={['Commit']} 
        rows={mockRows} 
        totals={mockTotals} 
        deltas={deltas}
        metricMode="Amount" 
        heatMode="Yesterday"
        onCellClick={vi.fn()} 
      />
    )
    expect(screen.getAllByText('+$100').length).toBeGreaterThan(0)
    // Positive delta gets emerald background
    const td = screen.getAllByText('+$100')[0].closest('td')
    expect(td?.style.backgroundColor).toContain('rgba(16, 185, 129')
  })
})
