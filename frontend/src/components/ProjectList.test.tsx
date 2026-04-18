import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import * as apiModule from '@/lib/api'

vi.mock('@/stores/authStore', () => ({
  useAuthStore: () => ({
    workspace: { id: 'ws1', name: 'Default', slug: 'default', plan_tier: 'starter', lifecycle_status: 'trial' },
  }),
}))

vi.mock('@/stores/timelineStore', () => ({
  useTimelineStore: () => ({
    setProject: vi.fn(),
    setClips: vi.fn(),
    setTimelineItems: vi.fn(),
    uploadProgress: null,
  }),
}))

describe('ProjectList', () => {
  beforeEach(() => {
    vi.spyOn(apiModule.api, 'get').mockResolvedValue([])
  })

  it('does not render watch_directory input', async () => {
    const { ProjectList } = await import('./ProjectList')
    render(<ProjectList />)
    await waitFor(() => expect(screen.queryByText(/loading projects/i)).not.toBeInTheDocument())
    expect(screen.queryByPlaceholderText(/watch/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/folder/i)).not.toBeInTheDocument()
  })

  it('renders an upload or browse button', async () => {
    const { ProjectList } = await import('./ProjectList')
    render(<ProjectList />)
    await waitFor(() => expect(screen.queryByText(/loading projects/i)).not.toBeInTheDocument())
    const btn = screen.queryByRole('button', { name: /upload|browse/i })
    expect(btn).toBeInTheDocument()
  })
})
