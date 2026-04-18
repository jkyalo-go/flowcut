import { render, screen, waitFor } from '@testing-library/react'
import WorkspacePage from '@/pages/workspace'
import { vi, beforeEach } from 'vitest'
import * as apiModule from '@/lib/api'

vi.mock('next/router', () => ({
  useRouter: () => ({ pathname: '/workspace', replace: vi.fn() }),
}))

vi.mock('@/stores/authStore', () => ({
  useAuthStore: vi.fn(() => ({ workspace: { name: 'Acme', plan_tier: 'pro' } })),
}))

describe('WorkspacePage', () => {
  beforeEach(() => {
    vi.spyOn(apiModule.api, 'get').mockResolvedValue([
      { user_id: 'u1', email: 'alice@test.com', name: 'Alice', role: 'owner' },
    ])
  })

  it('renders members after load', async () => {
    render(<WorkspacePage />)
    await waitFor(() => expect(screen.getByText('alice@test.com')).toBeInTheDocument())
    expect(screen.getByText('owner')).toBeInTheDocument()
  })

  it('renders invite form with email input', async () => {
    render(<WorkspacePage />)
    await waitFor(() => expect(screen.getByPlaceholderText(/colleague/i)).toBeInTheDocument())
  })
})
