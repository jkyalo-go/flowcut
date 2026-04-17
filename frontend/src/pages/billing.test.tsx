import { render, screen, waitFor } from '@testing-library/react'
import BillingPage from '@pages/billing'
import { vi, beforeEach } from 'vitest'
import * as apiModule from '@/lib/api'

vi.mock('next/router', () => ({
  useRouter: () => ({ pathname: '/billing', replace: vi.fn() }),
}))

describe('BillingPage', () => {
  beforeEach(() => {
    vi.spyOn(apiModule.api, 'get').mockImplementation((path: string) => {
      if (path.includes('plans')) return Promise.resolve([
        { id: 'p1', key: 'starter', name: 'Starter', monthly_price_usd: 0, quotas_json: '{}', features_json: '{}' },
        { id: 'p2', key: 'creator', name: 'Creator', monthly_price_usd: 29, quotas_json: '{}', features_json: '{}' },
      ])
      if (path.includes('subscription')) return Promise.resolve({ status: 'trial', plan_id: 'p1' })
      if (path.includes('usage')) return Promise.resolve([])
      if (path.includes('quota')) return Promise.resolve({ storage_quota_mb: 10240, ai_spend_cap_usd: 5, render_minutes_quota: 60, connected_platforms_quota: 2, team_seats_quota: 3, retained_footage_days: 30 })
      return Promise.resolve([])
    })
  })

  it('shows plan names after load', async () => {
    render(<BillingPage />)
    await waitFor(() => expect(screen.getByText('Starter')).toBeInTheDocument())
    expect(screen.getByText('Creator')).toBeInTheDocument()
  })

  it('shows current quota', async () => {
    render(<BillingPage />)
    await waitFor(() => expect(screen.getByText('Current quota')).toBeInTheDocument())
    expect(screen.getByText('10 GB')).toBeInTheDocument()
  })
})
