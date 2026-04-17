import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { PlatformsPage } from './PlatformsPage'
import { vi, afterEach } from 'vitest'
import * as apiModule from '@/lib/api'

afterEach(() => vi.restoreAllMocks())

describe('PlatformsPage', () => {
  it('shows connected platforms after load', async () => {
    vi.spyOn(apiModule.api, 'get').mockImplementation((path: string) => {
      if (path === '/api/platforms') {
        return Promise.resolve([
          {
            id: 'conn-1',
            platform: 'youtube',
            display_name: 'My YouTube Channel',
            status: 'active',
            scopes: ['upload'],
          },
        ])
      }
      return Promise.resolve([])
    })

    render(<PlatformsPage />)

    await waitFor(() =>
      expect(screen.getByText('My YouTube Channel')).toBeInTheDocument()
    )
    expect(screen.getByText('active')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /disconnect/i })).toBeInTheDocument()
  })

  it('shows "Connect YouTube" button when no platforms connected', async () => {
    vi.spyOn(apiModule.api, 'get').mockResolvedValue([])

    render(<PlatformsPage />)

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /connect youtube/i })).toBeInTheDocument()
    )
  })

  it('shows error Alert when connect fails', async () => {
    vi.spyOn(apiModule.api, 'get').mockImplementation((path: string) => {
      if (path === '/api/platforms') return Promise.resolve([])
      if (path.includes('auth/start')) return Promise.reject(new Error('OAuth failed'))
      return Promise.resolve([])
    })

    render(<PlatformsPage />)

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /connect youtube/i })).toBeInTheDocument()
    )

    fireEvent.click(screen.getByRole('button', { name: /connect youtube/i }))

    await waitFor(() =>
      expect(screen.getByText(/oauth failed/i)).toBeInTheDocument()
    )
  })
})
