import { describe, it, expect, vi, beforeEach } from 'vitest'
import { api } from './api'

describe('api helper', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  it('GET request hits the correct path', async () => {
    const mockFetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ id: '1' }) })
    vi.stubGlobal('fetch', mockFetch)
    await api.get('/api/auth/me')
    expect(mockFetch).toHaveBeenCalledWith('/api/auth/me', expect.objectContaining({ method: 'GET' }))
  })

  it('POST request sends JSON body', async () => {
    const mockFetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) })
    vi.stubGlobal('fetch', mockFetch)
    await api.post('/api/auth/dev-login', { email: 'demo@flowcut.local' })
    expect(mockFetch).toHaveBeenCalledWith('/api/auth/dev-login', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ email: 'demo@flowcut.local' }),
    }))
  })

  it('throws ApiError on non-ok response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Unauthorized' }),
    }))
    await expect(api.get('/api/auth/me')).rejects.toThrow('Unauthorized')
  })

  it('postForm does not set Content-Type to application/json', async () => {
    const mockFetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) })
    vi.stubGlobal('fetch', mockFetch)
    const form = new FormData()
    form.append('file', new Blob(['data'], { type: 'video/mp4' }), 'test.mp4')
    await api.postForm('/api/uploads/sessions/abc/part', form)
    const [, init] = mockFetch.mock.calls[0]
    expect((init.headers as Record<string, string>)['Content-Type']).toBeUndefined()
    expect(init.body).toBeInstanceOf(FormData)
  })

  it('includes credentials: include on all requests', async () => {
    const mockFetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) })
    vi.stubGlobal('fetch', mockFetch)
    await api.get('/api/auth/me')
    expect(mockFetch).toHaveBeenCalledWith('/api/auth/me', expect.objectContaining({ credentials: 'include' }))
  })
})
