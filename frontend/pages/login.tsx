import { useEffect, useState } from 'react'
import { useRouter } from 'next/router'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { api, ApiError } from '@/lib/api'
import { AuthScaffold } from '@/components/AuthScaffold'
import { completePendingInvite, getPendingInviteToken, rememberPendingInvite } from '@/lib/invitations'
import { useAuthStore } from '@/stores/authStore'
import type { User, Workspace } from '@/types'

export default function LoginPage() {
  const router = useRouter()
  const { setUser, setWorkspace, setToken } = useAuthStore()
  const allowDevLogin = process.env.NEXT_PUBLIC_ENABLE_DEV_LOGIN === 'true'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const inviteToken = typeof router.query?.invite === 'string' ? router.query.invite : null

  useEffect(() => {
    if (inviteToken) rememberPendingInvite(inviteToken)
  }, [inviteToken])

  async function finishSession(data: { token: string; user: User; workspace: Workspace }) {
    setToken(data.token)
    setUser(data.user)
    setWorkspace(data.workspace)

    const pendingInvite = getPendingInviteToken()
    if (pendingInvite) {
      try {
        const inviteSession = await completePendingInvite()
        if (inviteSession) {
          setToken(inviteSession.token)
          setUser(inviteSession.user)
          setWorkspace(inviteSession.workspace)
        }
        await router.replace('/')
        return
      } catch {
        await router.replace(`/invitations/${pendingInvite}/accept`)
        return
      }
    }

    await router.replace('/')
  }

  async function handleEmailLogin(e: React.FormEvent) {
    e.preventDefault()
    if (!email.trim() || !password) return
    setLoading(true)
    setError('')
    try {
      const data = await api.post<{ token: string; user: User; workspace: Workspace }>('/api/auth/login', {
        email: email.trim().toLowerCase(),
        password,
      })
      await finishSession(data)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Sign in failed')
      setLoading(false)
    }
  }

  async function handleGoogleLogin() {
    setLoading(true)
    setError('')
    try {
      const data = await api.get<{ redirect_url: string; state: string }>('/api/auth/oauth/google/start')
      window.location.assign(data.redirect_url)
      setTimeout(() => setLoading(false), 500)
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
        email: 'dev@flowcut.local',
        name: 'Dev User',
        workspace_name: 'FlowCut Dev Workspace',
      })
      await finishSession(data)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Dev login failed')
      setLoading(false)
    }
  }

  return (
    <AuthScaffold
      eyebrow={inviteToken ? 'Invitation' : 'Sign in'}
      title={inviteToken ? 'Accept the invite, then step straight into the workspace.' : 'Operate the full production flow from one place.'}
      description={inviteToken
        ? 'Your invitation is preserved through sign in. Once your session is created, the workspace handoff completes automatically.'
        : 'Use email or Google to get into the workspace shell, queue, schedule, and editor without bouncing between disconnected screens.'}
      footer={
        <p className="text-sm text-muted-foreground">
          Don&apos;t have an account?{' '}
          <Link href={inviteToken ? `/register?invite=${inviteToken}` : '/register'} className="text-primary underline underline-offset-2">
            Create one
          </Link>
        </p>
      }
    >
      <div className="space-y-2">
        <p className="eyebrow">{inviteToken ? 'Join Workspace' : 'Welcome Back'}</p>
        <h2 className="font-display text-3xl tracking-tight text-foreground">Sign in</h2>
        <p className="text-sm leading-6 text-muted-foreground">
          {inviteToken
            ? 'Use the invited email address to complete the handoff.'
            : 'Pick up where the team left off.'}
        </p>
      </div>

      <div className="flex flex-col gap-4">
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <form onSubmit={handleEmailLogin} className="flex flex-col gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                placeholder="At least 8 characters"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
              />
            </div>
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? 'Signing in...' : 'Sign in'}
            </Button>
          </form>
          <div className="flex items-center gap-2">
            <Separator className="flex-1" />
            <span className="text-xs text-muted-foreground">or</span>
            <Separator className="flex-1" />
          </div>
          <Button variant="outline" onClick={handleGoogleLogin} disabled={loading} className="w-full">
            Sign in with Google
          </Button>
          {allowDevLogin && (
            <Button variant="ghost" onClick={handleDevLogin} disabled={loading} className="w-full">
              Dev Login
            </Button>
          )}
      </div>
    </AuthScaffold>
  )
}
