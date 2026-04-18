import { render, screen, waitFor } from '@testing-library/react'
import BillingPage from '@pages/billing'
import { vi, beforeEach } from 'vitest'

const mockReplace = vi.fn()
vi.mock('next/router', () => ({
  useRouter: () => ({ pathname: '/billing', replace: mockReplace }),
}))

describe('BillingPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('redirects billing route to workspace plan tab', async () => {
    render(<BillingPage />)
    await waitFor(() => expect(mockReplace).toHaveBeenCalledWith('/workspace?tab=plan'))
  })

  it('renders no standalone billing UI', () => {
    render(<BillingPage />)
    expect(screen.queryByText(/billing/i)).not.toBeInTheDocument()
  })
})
