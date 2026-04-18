// frontend/pages/invitations/[token]/accept.tsx
import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/router'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { AuthScaffold } from '@/components/AuthScaffold'
import { api, ApiError, clearStoredToken } from '@/lib/api'
import { clearPendingInviteToken, rememberPendingInvite, completePendingInvite } from '@/lib/invitations'
import { surfaceApi } from '@/lib/api'
import { useAuthStore } from '@/stores/authStore'
import type { InvitationPreview } from '@/types'

export default function AcceptInvitePage() {
  const router = useRouter()
  const { token } = router.query
  const tok = typeof token === 'string' ? token : undefined
  const { user, clear, setToken, setUser, setWorkspace } = useAuthStore()

  const [accepting, setAccepting] = useState(false)
  const [done, setDone] = useState(false)
  const [invite, setInvite] = useState<InvitationPreview | null>(null)
  const [loading, setLoading] = useState(true)
  const [acceptError, setAcceptError] = useState('')
  const redirectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => () => { if (redirectTimerRef.current) clearTimeout(redirectTimerRef.current) }, [])

  useEffect(() => {
    if (!tok) return
    rememberPendingInvite(tok)
    surfaceApi.getInvitation(tok)
      .then((data) => {
        setInvite(data)
        setLoading(false)
      })
      .catch((err) => {
        setAcceptError(err instanceof Error ? err.message : 'Invitation not found')
        setLoading(false)
      })
  }, [tok])

  async function accept() {
    if (!tok) return
    setAccepting(true)
    setAcceptError('')
    try {
      const session = await completePendingInvite()
      if (session) {
        setToken(session.token)
        setUser(session.user)
        setWorkspace(session.workspace)
      }
      setDone(true)
      clearPendingInviteToken()
      redirectTimerRef.current = setTimeout(() => router.replace('/'), 2000)
    } catch (err) {
      setAcceptError(err instanceof ApiError ? err.message : 'Failed to accept invitation')
    } finally {
      setAccepting(false)
    }
  }

  function switchAccount() {
    void (async () => {
      try {
        await api.post('/api/auth/logout', {})
      } catch {
        void 0
      } finally {
        clearStoredToken()
        clearPendingInviteToken()
        if (tok) rememberPendingInvite(tok)
        clear()
        await router.replace(tok ? `/login?invite=${tok}` : '/login')
      }
    })()
  }

  if (done) {
    return (
      <AuthScaffold
        eyebrow="Invitation"
        title="You’re in."
        description="The workspace membership is active and the shell is ready. Redirecting to the overview now."
      >
        <div className="app-panel-muted p-5 text-sm text-muted-foreground">
          Redirecting to the overview...
        </div>
      </AuthScaffold>
    )
  }

  return (
    <AuthScaffold
      eyebrow="Workspace invitation"
      title="Review the invite, then enter the workspace with the right account."
      description="The invite is validated before acceptance. If you are not signed in, the token is preserved through login or registration and completed after authentication."
      footer={
        tok ? (
          <p className="text-sm text-muted-foreground">
            Need a different path?{' '}
            <Link href={`/register?invite=${tok}`} className="text-primary underline underline-offset-2">
              Create an account instead
            </Link>
          </p>
        ) : null
      }
    >
      <div className="space-y-2">
        <p className="eyebrow">Invitation</p>
        <h2 className="font-display text-3xl tracking-tight text-foreground">Join workspace</h2>
        <p className="text-sm leading-6 text-muted-foreground">
          {invite
            ? `You were invited to ${invite.workspace_name} as ${invite.role}.`
            : 'Checking invitation details.'}
        </p>
      </div>

      <div className="space-y-4">
          {acceptError && (
            <Alert variant="destructive">
              <AlertDescription>{acceptError}</AlertDescription>
            </Alert>
          )}

          <div className="app-panel-muted p-5">
            {loading ? (
              <p className="text-sm text-muted-foreground">Validating invitation…</p>
            ) : invite ? (
              <div className="space-y-4">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <p className="eyebrow">Workspace</p>
                    <p className="mt-2 text-sm font-medium text-foreground">{invite.workspace_name}</p>
                  </div>
                  <div>
                    <p className="eyebrow">Role</p>
                    <p className="mt-2 text-sm font-medium capitalize text-foreground">{invite.role}</p>
                  </div>
                  <div className="sm:col-span-2">
                    <p className="eyebrow">Invited email</p>
                    <p className="mt-2 text-sm font-medium text-foreground">{invite.email}</p>
                  </div>
                </div>

                {!user ? (
                  <div className="space-y-3">
                    <Alert>
                      <AlertDescription>
                        Sign in or create an account with the invited email to complete the handoff.
                      </AlertDescription>
                    </Alert>
                    <div className="flex flex-col gap-2 sm:flex-row">
                      <Button asChild className="flex-1">
                        <Link href={tok ? `/login?invite=${tok}` : '/login'}>Sign in</Link>
                      </Button>
                      <Button asChild variant="outline" className="flex-1">
                        <Link href={tok ? `/register?invite=${tok}` : '/register'}>Create account</Link>
                      </Button>
                    </div>
                  </div>
                ) : user.email.toLowerCase() !== invite.email.toLowerCase() ? (
                  <div className="space-y-3">
                    <Alert variant="destructive">
                      <AlertDescription>
                        You are signed in as {user.email}, but this invitation belongs to {invite.email}.
                      </AlertDescription>
                    </Alert>
                    <Button variant="outline" onClick={switchAccount} className="w-full">
                      Switch account
                    </Button>
                  </div>
                ) : (
                  <Button
                    onClick={accept}
                    disabled={accepting || !tok || !router.isReady}
                    className="w-full"
                  >
                    {accepting ? 'Accepting...' : 'Accept invitation'}
                  </Button>
                )}
              </div>
            ) : null}
          </div>
      </div>
    </AuthScaffold>
  )
}
