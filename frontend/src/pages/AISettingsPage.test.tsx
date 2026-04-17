import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AISettingsPage } from './AISettingsPage'
import { vi, afterEach } from 'vitest'
import * as apiModule from '@/lib/api'

afterEach(() => vi.restoreAllMocks())

const mockProviders = [
  {
    id: 'cfg-1',
    provider: 'anthropic',
    model_key: 'claude-3-5-sonnet',
    display_name: 'Claude 3.5 Sonnet',
    task_types: ['transcription', 'summarization'],
    enabled: true,
  },
]

const mockCredentials = [
  {
    id: 'cred-1',
    provider: 'openai',
    allowed_models: [],
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
  },
]

const mockUsage = [
  { task_type: 'transcription', provider: 'anthropic', total_cost: 0.0123, count: 5 },
]

function mockAllEndpoints(overrides: Record<string, unknown> = {}) {
  vi.spyOn(apiModule.api, 'get').mockImplementation((path: string) => {
    if (path === '/api/ai/admin/providers') {
      return Promise.resolve((overrides.providers ?? mockProviders) as unknown)
    }
    if (path === '/api/ai/credentials') {
      return Promise.resolve((overrides.credentials ?? mockCredentials) as unknown)
    }
    if (path === '/api/ai/usage') {
      return Promise.resolve((overrides.usage ?? mockUsage) as unknown)
    }
    return Promise.resolve([])
  })
}

describe('AISettingsPage', () => {
  it('shows provider config in Providers tab', async () => {
    mockAllEndpoints()

    render(<AISettingsPage />)

    await waitFor(() =>
      expect(screen.getByText('Claude 3.5 Sonnet')).toBeInTheDocument()
    )
    expect(screen.getByText(/anthropic.*claude-3-5-sonnet/i)).toBeInTheDocument()
    expect(screen.getByText('transcription')).toBeInTheDocument()
    expect(screen.getByText('summarization')).toBeInTheDocument()
  })

  it('can add a credential and it appears in the list', async () => {
    mockAllEndpoints({ credentials: [] })
    const newCred = {
      id: 'cred-new',
      provider: 'anthropic',
      allowed_models: [],
      is_active: true,
    }
    vi.spyOn(apiModule.api, 'post').mockResolvedValue(newCred)

    render(<AISettingsPage />)

    // Switch to BYOK tab
    await waitFor(() =>
      expect(screen.getByRole('tab', { name: /your api keys/i })).toBeInTheDocument()
    )
    await userEvent.click(screen.getByRole('tab', { name: /your api keys/i }))

    // Fill in the API key field
    const keyInput = screen.getByPlaceholderText(/paste api key/i)
    await userEvent.type(keyInput, 'sk-test-key-123')

    // Submit
    await userEvent.click(screen.getByRole('button', { name: /add key/i }))

    await waitFor(() =>
      expect(screen.getAllByText('anthropic').length).toBeGreaterThanOrEqual(1)
    )
    expect(apiModule.api.post).toHaveBeenCalledWith('/api/ai/credentials', {
      provider: 'anthropic',
      api_key: 'sk-test-key-123',
      allowed_models: [],
    })
  })

  it('can remove a credential and it disappears from the list', async () => {
    mockAllEndpoints()
    vi.spyOn(apiModule.api, 'delete').mockResolvedValue(undefined)

    render(<AISettingsPage />)

    // Switch to BYOK tab
    await waitFor(() =>
      expect(screen.getByRole('tab', { name: /your api keys/i })).toBeInTheDocument()
    )
    await userEvent.click(screen.getByRole('tab', { name: /your api keys/i }))

    await waitFor(() =>
      expect(screen.getByText('openai')).toBeInTheDocument()
    )

    await userEvent.click(screen.getByRole('button', { name: /remove/i }))

    await waitFor(() =>
      expect(screen.queryByText('openai')).not.toBeInTheDocument()
    )
    expect(apiModule.api.delete).toHaveBeenCalledWith('/api/ai/credentials/cred-1')
  })

  it('shows usage rows in Usage tab', async () => {
    mockAllEndpoints()

    render(<AISettingsPage />)

    await waitFor(() =>
      expect(screen.getByRole('tab', { name: /usage/i })).toBeInTheDocument()
    )
    await userEvent.click(screen.getByRole('tab', { name: /usage/i }))

    await waitFor(() =>
      expect(screen.getByText('transcription')).toBeInTheDocument()
    )
    expect(screen.getByText('$0.012')).toBeInTheDocument()
  })

  it('shows error alert when toggle provider config fails', async () => {
    mockAllEndpoints()
    vi.spyOn(apiModule.api, 'put').mockRejectedValue(new Error('Toggle failed'))

    render(<AISettingsPage />)

    await waitFor(() =>
      expect(screen.getByText('Claude 3.5 Sonnet')).toBeInTheDocument()
    )

    await userEvent.click(screen.getByRole('button', { name: /disable/i }))

    await waitFor(() =>
      expect(screen.getByText(/toggle failed/i)).toBeInTheDocument()
    )
  })
})
