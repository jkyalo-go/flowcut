// frontend/pages/invitations/[token]/accept.tsx
import { useState } from 'react'
import { useRouter } from 'next/router'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { api, ApiError } from '@/lib/api'

export default function AcceptInvitePage() {
  const router = useRouter()
  const { token } = router.query
  const tok = typeof token === 'string' ? token : undefined

  const [accepting, setAccepting] = useState(false)
  const [done, setDone] = useState(false)
  const [acceptError, setAcceptError] = useState('')

  async function accept() {
    if (!tok) return
    setAccepting(true)
    setAcceptError('')
    try {
      await api.post(`/invitations/${tok}/accept`)
      setDone(true)
      setTimeout(() => router.replace('/'), 2000)
    } catch (err) {
      setAcceptError(err instanceof ApiError ? err.message : 'Failed to accept invitation')
    } finally {
      setAccepting(false)
    }
  }

  if (done) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Welcome to the team!</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">Redirecting to the editor...</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Join workspace</CardTitle>
          <CardDescription>You've been invited to collaborate on FlowCut.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {acceptError && (
            <p className="text-sm text-destructive">{acceptError}</p>
          )}
          <Button
            onClick={accept}
            disabled={accepting || !tok || !router.isReady}
            className="w-full"
          >
            {accepting ? 'Accepting...' : 'Accept invitation'}
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
