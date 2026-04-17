// frontend/pages/workspace.tsx
import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { api, ApiError } from '@/lib/api'
import { useAuthStore } from '@/stores/authStore'
import type { Membership } from '@/types'

export default function WorkspacePage() {
  const { workspace } = useAuthStore()

  const [members, setMembers] = useState<Membership[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [email, setEmail] = useState('')
  const [role, setRole] = useState<'editor' | 'viewer' | 'admin'>('editor')
  const [inviting, setInviting] = useState(false)
  const [inviteError, setInviteError] = useState('')
  const [inviteSent, setInviteSent] = useState(false)
  const [lastSentEmail, setLastSentEmail] = useState('')

  useEffect(() => {
    let mounted = true
    api.get<Membership[]>('/api/workspaces/current/members')
      .then((data) => {
        if (mounted) {
          setMembers(data)
          setLoading(false)
        }
      })
      .catch((err) => {
        if (mounted) {
          setError(err instanceof ApiError ? err.message : 'Failed to load members')
          setLoading(false)
        }
      })
    return () => { mounted = false }
  }, [])

  async function sendInvite() {
    if (!email.trim()) return
    setInviting(true)
    setInviteError('')
    setInviteSent(false)
    try {
      await api.post('/invitations', { email: email.trim(), role })
      setLastSentEmail(email.trim())
      setEmail('')
      setInviteSent(true)
    } catch (err) {
      setInviteError(err instanceof ApiError ? err.message : 'Failed to send invitation')
    } finally {
      setInviting(false)
    }
  }

  function roleBadgeVariant(r: string): 'default' | 'secondary' | 'outline' {
    if (r === 'owner') return 'default'
    if (r === 'admin') return 'secondary'
    return 'outline'
  }

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{workspace?.name ?? 'Workspace'}</h1>
        {workspace?.plan_tier && (
          <p className="text-sm text-muted-foreground capitalize">{workspace.plan_tier} plan</p>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Members</CardTitle>
        </CardHeader>
        <CardContent>
          {loading && <p className="text-sm text-muted-foreground">Loading members...</p>}
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          {!loading && !error && members.length === 0 && (
            <p className="text-sm text-muted-foreground">No members found.</p>
          )}
          {!loading && members.length > 0 && (
            <div className="divide-y">
              {members.map((member) => (
                <div key={member.user_id} className="flex items-center justify-between py-3">
                  <div>
                    <p className="text-sm font-medium">{member.name}</p>
                    <p className="text-sm text-muted-foreground">{member.email}</p>
                  </div>
                  <Badge variant={roleBadgeVariant(member.role)}>{member.role}</Badge>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Invite a teammate</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="invite-email">Email address</Label>
              <Input
                id="invite-email"
                type="email"
                placeholder="colleague@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="invite-role">Role</Label>
              <Select value={role} onValueChange={(v) => setRole(v as typeof role)}>
                <SelectTrigger id="invite-role">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="admin">Admin</SelectItem>
                  <SelectItem value="editor">Editor</SelectItem>
                  <SelectItem value="viewer">Viewer</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <Button onClick={sendInvite} disabled={inviting || !email.trim()}>
              {inviting ? 'Sending...' : 'Send invite'}
            </Button>

            {inviteSent && (
              <Alert>
                <AlertDescription>Invitation sent to {lastSentEmail}.</AlertDescription>
              </Alert>
            )}

            {inviteError && (
              <Alert variant="destructive">
                <AlertDescription>{inviteError}</AlertDescription>
              </Alert>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
