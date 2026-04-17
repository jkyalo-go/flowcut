import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { CalendarPage } from './CalendarPage'
import { vi, afterEach } from 'vitest'
import * as apiModule from '@/lib/api'

afterEach(() => vi.restoreAllMocks())

const mockSlots = [
  {
    id: 'slot-1',
    platform: 'youtube',
    scheduled_at: '2026-04-20T10:00:00Z',
    status: 'scheduled' as const,
    clip_id: 'clip-1',
    publish_url: null,
    failure_reason: null,
  },
  {
    id: 'slot-2',
    platform: 'tiktok',
    scheduled_at: '2026-04-15T09:00:00Z',
    status: 'failed' as const,
    clip_id: 'clip-2',
    publish_url: null,
    failure_reason: 'Upload quota exceeded',
  },
  {
    id: 'slot-3',
    platform: 'instagram_reels',
    scheduled_at: '2026-04-14T08:00:00Z',
    status: 'published' as const,
    clip_id: 'clip-3',
    publish_url: 'https://instagram.com/reel/abc123',
    failure_reason: null,
  },
]

const mockGaps = [
  { platform: 'youtube', suggested_at: '2026-04-21T14:00:00Z', score: 0.87 },
  { platform: 'tiktok', suggested_at: '2026-04-22T18:00:00Z', score: 0.72 },
]

describe('CalendarPage', () => {
  it('shows scheduled slots in Upcoming tab', async () => {
    vi.spyOn(apiModule.api, 'get').mockImplementation((path: string) => {
      if (path === '/api/platforms/calendar') return Promise.resolve(mockSlots)
      if (path === '/api/calendar/gaps') return Promise.resolve(mockGaps)
      return Promise.resolve([])
    })

    render(<CalendarPage />)

    await waitFor(() =>
      expect(screen.getByText('scheduled')).toBeInTheDocument()
    )

    // Upcoming tab should be active by default and show scheduled slot
    expect(screen.getAllByText('youtube').length).toBeGreaterThan(0)
    // Cancel button should be visible for scheduled slots
    expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument()
  })

  it('shows failed slot with Retry button in Past tab', async () => {
    vi.spyOn(apiModule.api, 'get').mockImplementation((path: string) => {
      if (path === '/api/platforms/calendar') return Promise.resolve(mockSlots)
      if (path === '/api/calendar/gaps') return Promise.resolve([])
      return Promise.resolve([])
    })

    render(<CalendarPage />)

    await waitFor(() =>
      expect(screen.getByRole('tab', { name: /past/i })).toBeInTheDocument()
    )

    await userEvent.click(screen.getByRole('tab', { name: /past/i }))

    await waitFor(() =>
      expect(screen.getByText('tiktok')).toBeInTheDocument()
    )

    expect(screen.getByText('Upload quota exceeded')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })

  it('cancel action updates slot status to cancelled in UI', async () => {
    // Use only a single scheduled slot to simplify the test
    const singleSlot = [mockSlots[0]]
    vi.spyOn(apiModule.api, 'get').mockImplementation((path: string) => {
      if (path === '/api/platforms/calendar') return Promise.resolve(singleSlot)
      if (path === '/api/calendar/gaps') return Promise.resolve([])
      return Promise.resolve([])
    })
    vi.spyOn(apiModule.api, 'post').mockResolvedValue(undefined)

    render(<CalendarPage />)

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument()
    )

    await userEvent.click(screen.getByRole('button', { name: /cancel/i }))

    // After cancel the slot moves to Past tab — switch to Past to verify
    await userEvent.click(screen.getByRole('tab', { name: /past/i }))

    await waitFor(() =>
      expect(screen.getByText('cancelled')).toBeInTheDocument()
    )
  })

  it('shows gap suggestions when gaps are present', async () => {
    vi.spyOn(apiModule.api, 'get').mockImplementation((path: string) => {
      if (path === '/api/platforms/calendar') return Promise.resolve([])
      if (path === '/api/calendar/gaps') return Promise.resolve(mockGaps)
      return Promise.resolve([])
    })

    render(<CalendarPage />)

    await waitFor(() =>
      expect(screen.getByText(/suggested posting times/i)).toBeInTheDocument()
    )

    expect(screen.getByText('87%')).toBeInTheDocument()
  })

  it('shows publish_url link for published slots in Past tab', async () => {
    vi.spyOn(apiModule.api, 'get').mockImplementation((path: string) => {
      if (path === '/api/platforms/calendar') return Promise.resolve(mockSlots)
      if (path === '/api/calendar/gaps') return Promise.resolve([])
      return Promise.resolve([])
    })

    render(<CalendarPage />)

    await waitFor(() =>
      expect(screen.getByRole('tab', { name: /past/i })).toBeInTheDocument()
    )

    await userEvent.click(screen.getByRole('tab', { name: /past/i }))

    await waitFor(() =>
      expect(screen.getByRole('link', { name: /view published/i })).toBeInTheDocument()
    )

    expect(screen.getByRole('link', { name: /view published/i })).toHaveAttribute(
      'href',
      'https://instagram.com/reel/abc123'
    )
  })
})
