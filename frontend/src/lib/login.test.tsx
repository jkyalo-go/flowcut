import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import * as apiModule from '@/lib/api'

const mockReplace = vi.fn()

// Mock next/router at module level (required for vi.mock hoisting)
vi.mock('next/router', () => ({
  useRouter: () => ({ replace: mockReplace }),
}))

// Lazy import LoginPage after mocks
describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('shows Sign in with Google button', async () => {
    const { default: LoginPage } = await import('@/pages/login')
    render(<LoginPage />)
    expect(screen.getByRole('button', { name: /google/i })).toBeInTheDocument()
  })

  it('dev login stores token and navigates', async () => {
    // Expose dev-only button in test environment
    vi.stubEnv('NODE_ENV', 'development')
    vi.spyOn(apiModule.api, 'post').mockResolvedValue({
      token: 'test-token-123',
      user: { id: '1', email: 'demo@flowcut.local', name: 'Demo', user_type: 'admin' },
      workspace: { id: 'ws1', name: 'Default', slug: 'default', plan_tier: 'starter', lifecycle_status: 'trial' },
    })
    const { default: LoginPage } = await import('@/pages/login')
    render(<LoginPage />)
    const devBtn = screen.getByRole('button', { name: /dev login/i })
    fireEvent.click(devBtn)
    await waitFor(() => expect(localStorage.getItem('flowcut_token')).toBe('test-token-123'))
  })
})
