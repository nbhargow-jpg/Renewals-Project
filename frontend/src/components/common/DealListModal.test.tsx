import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import DealListModal from './DealListModal'

describe('DealListModal', () => {
  const mockDeals = [
    {
      id: '1',
      opportunity_id_18: 'OPP1',
      opportunity_name: 'Deal A',
      account_name: 'Acme',
      forecast_category: 'Commit',
      forecast_acv_amount: 1000,
      approval_status: 'Approved',
    },
    {
      id: '2',
      opportunity_id_18: 'OPP2',
      opportunity_name: 'Deal B',
      account_name: 'Globex',
      forecast_category: 'Best Case',
      forecast_acv_amount: 500,
      approval_status: 'Pending Approval',
    }
  ]

  it('filters deals by forecast category', () => {
    render(<DealListModal title="Test Modal" deals={mockDeals} onSelectOpp={vi.fn()} onClose={vi.fn()} />)
    
    // Initially shows both
    expect(screen.getByText('Deal A')).toBeDefined()
    expect(screen.getByText('Deal B')).toBeDefined()
    expect(screen.getByText(/Showing 2 deals/)).toBeDefined()

    // Filter by Commit
    const fcSelect = screen.getAllByRole('combobox')[0]
    fireEvent.change(fcSelect, { target: { value: 'Commit' } })

    // Now only shows Deal A
    expect(screen.queryByText('Deal B')).toBeNull()
    expect(screen.getByText(/Showing 1 deals/)).toBeDefined()
  })
})
