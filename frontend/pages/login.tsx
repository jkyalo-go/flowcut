// frontend/pages/login.tsx
import { useState } from 'react'
import { useRouter } from 'next/router'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { api, ApiError, storeToken } from '@/lib/api'
import { useAuthStore } from '@/stores/authStore'
import type { User, Workspace } from '@/types'

export default function LoginPage() {
  const router = useRouter()
  const { setUser, setWorkspace, setToken } = useAuthStore()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleGoogleLogin() {
    setLoading(true)
    setError('')
    try {
      const data = await api.get<{ redirect_url: string; state: string }>('/api/auth/oauth/google/start')
      window.location.assign(data.redirect_url)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Failed to start login')
      setLoading(false)
    }
  }

  async function handleDevLogin() {
    setLoading(true)
    setError('')
    try {
      const data = await api.post<{ token: string; user: User; workspace: Workspace }>('/api/auth/dev-login', {
        email: 'demo@flowcut.local',
      })
      storeToken(data.token)
      setToken(data.token)
      setUser(data.user)
      setWorkspace(data.workspace)
      router.replace('/')
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Dev login failed')
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">FlowCut</CardTitle>
          <CardDescription>Sign in to your account</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <Button onClick={handleGoogleLogin} disabled={loading} className="w-full">
            {loading ? 'Redirecting...' : 'Sign in with Google'}
          </Button>
          {process.env.NODE_ENV === 'development' && (
            <Button variant="outline" onClick={handleDevLogin} disabled={loading} className="w-full">
              Dev login (demo@flowcut.local)
            </Button>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
