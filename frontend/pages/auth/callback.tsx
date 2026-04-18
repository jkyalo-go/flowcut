// frontend/pages/auth/callback.tsx
import { useEffect, useState } from 'react'
import { useRouter } from 'next/router'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { api, ApiError } from '@/lib/api'
import { AuthScaffold } from '@/components/AuthScaffold'
import { completePendingInvite, getPendingInviteToken } from '@/lib/invitations'
import { useAuthStore } from '@/stores/authStore'
import type { User, Workspace } from '@/types'

export default function AuthCallbackPage() {
  const router = useRouter()
  const { setUser, setWorkspace, setToken, setLoading } = useAuthStore()
  const [error, setError] = useState('')
  const { code, state } = router.query
  const callbackParamError = !router.isReady
    ? ''
    : !code || !state
      ? 'Missing OAuth parameters'
      : typeof code !== 'string' || typeof state !== 'string'
        ? 'Malformed OAuth parameters'
        : ''

  useEffect(() => {
    // router.query is populated after hydration
    if (!router.isReady || callbackParamError) return
    if (typeof code !== 'string' || typeof state !== 'string') {
      return
    }

    async function handleCallback() {
      try {
        const data = await api.post<{ token: string; user: User; workspace: Workspace }>(
          '/api/auth/oauth/google/callback',
          { code, state }
        )
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
          } catch {
            await router.replace(`/invitations/${pendingInvite}/accept`)
            return
          }
        }
        setLoading(false)
        await router.replace('/')
      } catch (e) {
        setLoading(false)
        setError(e instanceof ApiError ? e.message : 'OAuth callback failed')
      }
    }
    void handleCallback()
  }, [callbackParamError, code, router.isReady, setLoading, setToken, setUser, setWorkspace, state]) // eslint-disable-line react-hooks/exhaustive-deps

  if (error || callbackParamError) {
    return (
      <AuthScaffold
        eyebrow="OAuth"
        title="The sign-in callback did not complete."
        description="The Google handoff reached the app, but the session could not be finalized. Review the message and retry the sign-in flow."
      >
        <Alert variant="destructive">
          <AlertDescription>{error || callbackParamError}</AlertDescription>
        </Alert>
      </AuthScaffold>
    )
  }

  return (
    <AuthScaffold
      eyebrow="OAuth"
      title="Completing sign in"
      description="Finalizing your session, workspace selection, and any pending invitation handoff."
    >
      <div className="app-panel-muted p-5 text-sm text-muted-foreground">
        Completing sign in...
      </div>
    </AuthScaffold>
  )
}
