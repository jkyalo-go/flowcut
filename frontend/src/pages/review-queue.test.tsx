import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import ReviewQueuePage from '@pages/review-queue'
import { vi, beforeEach, afterEach } from 'vitest'
import * as apiModule from '@/lib/api'

vi.mock('next/router', () => ({
  useRouter: () => ({ pathname: '/review-queue', replace: vi.fn() }),
}))

vi.mock('@/stores/timelineStore', () => ({
  useTimelineStore: vi.fn((selector) => {
    const store = { reviewQueueDirty: false, setReviewQueueDirty: vi.fn() }
    return selector(store)
  }),
}))

describe('ReviewQueuePage', () => {
  afterEach(() => vi.restoreAllMocks())

  beforeEach(() => {
    vi.spyOn(apiModule.api, 'get').mockImplementation((path: string) => {
      if (path.includes('settings')) return Promise.resolve({ autonomy_mode: 'supervised', autonomy_confidence_threshold: 0.8 })
      if (path.includes('review-queue')) return Promise.resolve([
        { id: 'q1', clip_id: 'c1', project_id: 'p1', title: 'Cool clip', status: 'pending_review', edit_confidence: 0.72, created_at: '2026-01-01' },
      ])
      if (path.includes('notifications')) return Promise.resolve([])
      if (path.includes('audit')) return Promise.resolve([])
      return Promise.resolve([])
    })
  })

  it('shows queued clips', async () => {
    render(<ReviewQueuePage />)
    await waitFor(() => expect(screen.getByText('Cool clip')).toBeInTheDocument())
  })

  it('renders approve and reject buttons', async () => {
    render(<ReviewQueuePage />)
    await waitFor(() => screen.getByText('Cool clip'))
    expect(screen.getByRole('button', { name: /approve/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /reject/i })).toBeInTheDocument()
  })

  it('restores item if approve action fails', async () => {
    vi.spyOn(apiModule.api, 'post').mockRejectedValue(new Error('Network error'))
    render(<ReviewQueuePage />)
    await waitFor(() => screen.getByText('Cool clip'))
    fireEvent.click(screen.getByRole('button', { name: /approve/i }))
    await waitFor(() => expect(screen.getByText('Cool clip')).toBeInTheDocument())
    expect(screen.getByText(/network error/i)).toBeInTheDocument()
  })
})
