import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AdminPage } from './AdminPage'
import { vi, afterEach } from 'vitest'
import * as apiModule from '@/lib/api'

afterEach(() => vi.restoreAllMocks())

const mockSummary = { total_workspaces: 3, active_jobs: 2 }

const mockJobs = [
  { id: 'job-1', job_type: 'video_export', status: 'running', created_at: '2026-04-17T10:00:00Z' },
  { id: 'job-2', job_type: 'transcription', status: 'failed', created_at: '2026-04-17T09:00:00Z' },
]

const mockActions = [
  { id: 'act-1', action: 'user_login', actor: 'alice@example.com', created_at: '2026-04-17T08:00:00Z' },
]

const mockExports = [
  { id: 'exp-1', status: 'complete', created_at: '2026-04-16T12:00:00Z', download_url: 'https://example.com/export.json' },
]

const mockOnboarding = {
  workspace_id: 'ws-1',
  checklist_json: JSON.stringify([
    { label: 'Connect platform', completed: true },
    { label: 'Upload first video', completed: false },
  ]),
}

function mockAllEndpoints(overrides: Record<string, unknown> = {}) {
  vi.spyOn(apiModule.api, 'get').mockImplementation((path: string) => {
    if (path === '/api/enterprise/admin/summary') {
      return Promise.resolve((overrides.summary !== undefined ? overrides.summary : mockSummary) as unknown)
    }
    if (path === '/api/enterprise/admin/jobs') {
      return Promise.resolve((overrides.jobs ?? mockJobs) as unknown)
    }
    if (path === '/api/enterprise/admin/actions') {
      return Promise.resolve((overrides.actions ?? mockActions) as unknown)
    }
    if (path === '/api/enterprise/compliance-exports') {
      return Promise.resolve((overrides.exports ?? mockExports) as unknown)
    }
    if (path === '/api/enterprise/onboarding') {
      return Promise.resolve((overrides.onboarding !== undefined ? overrides.onboarding : mockOnboarding) as unknown)
    }
    return Promise.resolve(null)
  })
}

describe('AdminPage', () => {
  it('shows summary stats with total_workspaces visible as "3"', async () => {
    mockAllEndpoints()

    render(<AdminPage />)

    await waitFor(() =>
      expect(screen.getByText('3')).toBeInTheDocument()
    )
    expect(screen.getByText('Total workspaces')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
    expect(screen.getByText('Active jobs')).toBeInTheDocument()
  })

  it('shows jobs in Background jobs tab', async () => {
    mockAllEndpoints()

    render(<AdminPage />)

    // Background jobs tab should be visible (it's the default)
    await waitFor(() =>
      expect(screen.getByText('video_export')).toBeInTheDocument()
    )
    expect(screen.getByText('transcription')).toBeInTheDocument()

    // Check status badges
    expect(screen.getByText('running')).toBeInTheDocument()
    expect(screen.getByText('failed')).toBeInTheDocument()
  })

  it('shows action log entries in Action log tab', async () => {
    mockAllEndpoints()

    render(<AdminPage />)

    await waitFor(() =>
      expect(screen.getByRole('tab', { name: /action log/i })).toBeInTheDocument()
    )
    await userEvent.click(screen.getByRole('tab', { name: /action log/i }))

    await waitFor(() =>
      expect(screen.getByText('user_login')).toBeInTheDocument()
    )
    expect(screen.getByText('alice@example.com')).toBeInTheDocument()
  })

  it('creates a compliance export and new export appears in list', async () => {
    mockAllEndpoints()

    const newExport = {
      id: 'exp-new',
      status: 'pending',
      created_at: '2026-04-17T11:00:00Z',
    }
    vi.spyOn(apiModule.api, 'post').mockResolvedValue(newExport)

    render(<AdminPage />)

    // Switch to Compliance exports tab
    await waitFor(() =>
      expect(screen.getByRole('tab', { name: /compliance exports/i })).toBeInTheDocument()
    )
    await userEvent.click(screen.getByRole('tab', { name: /compliance exports/i }))

    // Existing export should be visible
    await waitFor(() =>
      expect(screen.getByText('complete')).toBeInTheDocument()
    )

    // Click new export button
    await userEvent.click(screen.getByRole('button', { name: /new compliance export/i }))

    // New export should appear prepended
    await waitFor(() =>
      expect(screen.getByText('pending')).toBeInTheDocument()
    )
    expect(apiModule.api.post).toHaveBeenCalledWith('/api/enterprise/compliance-exports', { format: 'json' })
  })

  it('shows onboarding checklist with completed and incomplete steps', async () => {
    mockAllEndpoints()

    render(<AdminPage />)

    await waitFor(() =>
      expect(screen.getByText('Connect platform')).toBeInTheDocument()
    )
    expect(screen.getByText('Upload first video')).toBeInTheDocument()
  })

  it('shows error alert when compliance export POST fails', async () => {
    mockAllEndpoints()
    vi.spyOn(apiModule.api, 'post').mockRejectedValue(new Error('Export failed'))

    render(<AdminPage />)

    await waitFor(() =>
      expect(screen.getByRole('tab', { name: /compliance exports/i })).toBeInTheDocument()
    )
    await userEvent.click(screen.getByRole('tab', { name: /compliance exports/i }))

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /new compliance export/i })).toBeInTheDocument()
    )
    await userEvent.click(screen.getByRole('button', { name: /new compliance export/i }))

    await waitFor(() =>
      expect(screen.getByText(/export failed/i)).toBeInTheDocument()
    )
  })
})
