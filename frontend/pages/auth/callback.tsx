// frontend/pages/auth/callback.tsx
import { useEffect, useState } from 'react'
import { useRouter } from 'next/router'
import { api, ApiError, storeToken } from '@/lib/api'
import { useAuthStore } from '@/stores/authStore'
import type { User, Workspace } from '@/types'

export default function AuthCallbackPage() {
  const router = useRouter()
  const { setUser, setWorkspace, setToken, setLoading } = useAuthStore()
  const [error, setError] = useState('')

  useEffect(() => {
    // router.query is populated after hydration
    if (!router.isReady) return
    const { code, state } = router.query
    if (!code || !state) {
      setError('Missing OAuth parameters')
      return
    }
    if (typeof code !== 'string' || typeof state !== 'string') {
      setError('Malformed OAuth parameters')
      return
    }

    async function handleCallback() {
      try {
        const data = await api.post<{ token: string; user: User; workspace: Workspace }>(
          '/api/auth/oauth/google/callback',
          { code, state }
        )
        storeToken(data.token)
        setToken(data.token)
        setUser(data.user)
        setWorkspace(data.workspace)
        setLoading(false)
        router.replace('/')
      } catch (e) {
        setError(e instanceof ApiError ? e.message : 'OAuth callback failed')
      }
    }
    handleCallback()
  }, [router.isReady, router.query]) // eslint-disable-line react-hooks/exhaustive-deps

  if (error) {
    return (
      <div className="flex h-screen items-center justify-center">
        <p className="text-sm text-destructive">{error}</p>
      </div>
    )
  }

  return (
    <div className="flex h-screen items-center justify-center text-sm text-muted-foreground">
      Completing sign in...
    </div>
  )
}
