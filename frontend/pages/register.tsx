import { useEffect, useState } from 'react'
import { useRouter } from 'next/router'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api, ApiError } from '@/lib/api'
import { AuthScaffold } from '@/components/AuthScaffold'
import { completePendingInvite, getPendingInviteToken, rememberPendingInvite } from '@/lib/invitations'
import { useAuthStore } from '@/stores/authStore'
import type { User, Workspace } from '@/types'

export default function RegisterPage() {
  const router = useRouter()
  const { setUser, setWorkspace, setToken } = useAuthStore()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
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

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!email.trim() || !password) return
    if (password !== confirm) {
      setError('Passwords do not match')
      return
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }
    setLoading(true)
    setError('')
    try {
      const data = await api.post<{ token: string; user: User; workspace: Workspace }>('/api/auth/register', {
        email: email.trim().toLowerCase(),
        password,
        name: name.trim() || undefined,
      })
      await finishSession(data)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Registration failed')
      setLoading(false)
    }
  }

  return (
    <AuthScaffold
      eyebrow={inviteToken ? 'Invitation' : 'Create account'}
      title={inviteToken ? 'Create your account and join the team without losing the invite.' : 'Set up the workspace once and keep the whole publishing system aligned.'}
      description={inviteToken
        ? 'The invite token stays attached to this session. After registration, the workspace membership is completed automatically.'
        : 'Registration provisions the workspace, plan, onboarding state, and the core product shell so you can move directly into projects.'}
      footer={
        <p className="text-sm text-muted-foreground">
          Already have an account?{' '}
          <Link href={inviteToken ? `/login?invite=${inviteToken}` : '/login'} className="text-primary underline underline-offset-2">
            Sign in
          </Link>
        </p>
      }
    >
      <div className="space-y-2">
        <p className="eyebrow">{inviteToken ? 'Join Workspace' : 'Start Here'}</p>
        <h2 className="font-display text-3xl tracking-tight text-foreground">Create account</h2>
        <p className="text-sm leading-6 text-muted-foreground">
          {inviteToken
            ? 'Use the invited email so the workspace membership can be completed immediately.'
            : 'Create the account once, then work from the shell, queue, calendar, and project workspace.'}
        </p>
      </div>

      <div>
          {error && (
            <Alert variant="destructive" className="mb-4">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="name">Name (optional)</Label>
              <Input
                id="name"
                type="text"
                placeholder="Your name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoComplete="name"
              />
            </div>
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
                autoComplete="new-password"
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="confirm">Confirm password</Label>
              <Input
                id="confirm"
                type="password"
                placeholder="••••••••"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                autoComplete="new-password"
                required
              />
            </div>
            <Button type="submit" className="w-full mt-1" disabled={loading}>
              {loading ? 'Creating account...' : 'Create account'}
            </Button>
          </form>
      </div>
    </AuthScaffold>
  )
}
