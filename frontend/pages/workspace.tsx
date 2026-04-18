import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/router'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { api, surfaceApi } from '@/lib/api'
import { useAuthStore } from '@/stores/authStore'
import type { QuotaSurface, StyleProfile, SubscriptionPlan, WorkspaceMemberSurface, WorkspaceSubscription } from '@/types'

type WorkspaceTab = 'team' | 'plan' | 'brand' | 'admin'

interface AdminSummary {
  workspaces: number
  users: number
  active_subscriptions: number
  queued_jobs: number
  failed_jobs: number
  pending_exports: number
  ai_spend_usd: number
}

function tabFromQuery(value: string | string[] | undefined, isAdmin: boolean): WorkspaceTab {
  if (value === 'plan' || value === 'brand') return value
  if (value === 'admin' && isAdmin) return 'admin'
  return 'team'
}

function fmtMb(mb: number) {
  return mb >= 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${mb.toFixed(0)} MB`
}

async function fetchWorkspaceState(isAdmin: boolean) {
  const [memberData, planData, subscriptionData, quotaData, profileData, summaryData] = await Promise.all([
    surfaceApi.getMembers(),
    surfaceApi.getPlans(),
    surfaceApi.getSubscription(),
    surfaceApi.getQuota(),
    surfaceApi.listStyleProfiles().catch(() => []),
    isAdmin ? api.get<AdminSummary>('/api/enterprise/admin/summary').catch(() => null) : Promise.resolve(null),
  ])
  return { memberData, planData, profileData, quotaData, subscriptionData, summaryData }
}

export default function WorkspacePage() {
  const router = useRouter()
  const { workspace, user } = useAuthStore()
  const isAdmin = user?.user_type === 'admin'
  const activeTab = tabFromQuery(router.query?.tab, isAdmin)

  const [members, setMembers] = useState<WorkspaceMemberSurface[]>([])
  const [plans, setPlans] = useState<SubscriptionPlan[]>([])
  const [subscription, setSubscription] = useState<WorkspaceSubscription | null>(null)
  const [quota, setQuota] = useState<QuotaSurface | null>(null)
  const [profiles, setProfiles] = useState<StyleProfile[]>([])
  const [adminSummary, setAdminSummary] = useState<AdminSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [inviting, setInviting] = useState(false)
  const [checkingOut, setCheckingOut] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [inviteSent, setInviteSent] = useState<{ email: string; inviteUrl: string; emailSent: boolean } | null>(null)

  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState<'admin' | 'editor' | 'viewer'>('editor')

  useEffect(() => {
    let mounted = true
    void (async () => {
      try {
        const {
          memberData,
          planData,
          profileData,
          quotaData,
          subscriptionData,
          summaryData,
        } = await fetchWorkspaceState(isAdmin)
        if (!mounted) return
        setMembers(memberData)
        setPlans(planData)
        setSubscription(subscriptionData)
        setQuota(quotaData)
        setProfiles(profileData)
        setAdminSummary(summaryData)
      } catch (err) {
        if (!mounted) return
        setError(err instanceof Error ? err.message : 'Failed to load workspace')
      } finally {
        if (mounted) setLoading(false)
      }
    })()
    return () => { mounted = false }
  }, [isAdmin])

  const currentPlan = useMemo(
    () => plans.find((plan) => plan.id === subscription?.plan_id) ?? null,
    [plans, subscription],
  )

  async function sendInvite() {
    if (!inviteEmail.trim()) return
    setInviting(true)
    setError(null)
    setInviteSent(null)
    try {
      const data = await api.post<{ invite_url: string; email: string; email_sent: boolean }>('/invitations', {
        email: inviteEmail.trim().toLowerCase(),
        role: inviteRole,
      })
      setInviteSent({
        email: data.email,
        inviteUrl: data.invite_url,
        emailSent: data.email_sent,
      })
      setInviteEmail('')
      const {
        memberData,
        planData,
        profileData,
        quotaData,
        subscriptionData,
        summaryData,
      } = await fetchWorkspaceState(isAdmin)
      setMembers(memberData)
      setPlans(planData)
      setSubscription(subscriptionData)
      setQuota(quotaData)
      setProfiles(profileData)
      setAdminSummary(summaryData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send invite')
    } finally {
      setInviting(false)
    }
  }

  async function checkout(planKey: string) {
    setCheckingOut(planKey)
    setError(null)
    try {
      const data = await api.post<{ url?: string; checkout_url?: string }>('/billing/checkout', {
        plan_tier: planKey,
      })
      const redirectUrl = data.url ?? data.checkout_url
      if (!redirectUrl) throw new Error('Missing checkout redirect URL')
      window.location.assign(redirectUrl)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start checkout')
      setCheckingOut(null)
    }
  }

  if (loading) {
    return (
      <div className="app-panel p-8">
        <p className="text-sm text-muted-foreground">Loading workspace…</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <section className="app-panel p-6 md:p-8">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="eyebrow">Workspace</p>
            <h2 className="mt-3 font-display text-4xl tracking-tight text-foreground">{workspace?.name ?? 'Workspace settings'}</h2>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-muted-foreground">
              Team operations, plan and usage, brand defaults, and admin-only controls are grouped here instead of being split across disconnected settings routes.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            {workspace?.plan_tier && (
              <Badge variant="secondary" className="rounded-xl px-3 py-1 capitalize">
                {workspace.plan_tier}
              </Badge>
            )}
            <Button asChild variant="outline" className="rounded-xl">
              <Link href="/integrations">Open integrations</Link>
            </Button>
          </div>
        </div>
      </section>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {inviteSent && (
        <Alert>
          <AlertDescription className="space-y-2">
            <span className="block">
              {inviteSent.emailSent
                ? `Invitation emailed to ${inviteSent.email}.`
                : `Invitation created for ${inviteSent.email}. Copy and send the link manually.`}
            </span>
            <span className="block break-all text-xs text-muted-foreground">{inviteSent.inviteUrl}</span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="mt-2 rounded-xl"
              onClick={() => navigator.clipboard.writeText(inviteSent.inviteUrl).catch(() => {})}
            >
              Copy invite link
            </Button>
          </AlertDescription>
        </Alert>
      )}

      <Tabs
        value={activeTab}
        onValueChange={(value) => {
          router.replace(`/workspace?tab=${value as WorkspaceTab}`, undefined, { shallow: true })
        }}
      >
        <TabsList>
          <TabsTrigger value="team">Team</TabsTrigger>
          <TabsTrigger value="plan">Plan &amp; usage</TabsTrigger>
          <TabsTrigger value="brand">Brand &amp; defaults</TabsTrigger>
          {isAdmin && <TabsTrigger value="admin">Admin</TabsTrigger>}
        </TabsList>

        <TabsContent value="team" className="mt-4 space-y-4">
          <div className="grid gap-4 xl:grid-cols-[1fr_22rem]">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Members</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {members.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No members found.</p>
                ) : members.map((member) => (
                  <div key={member.user_id} className="rounded-2xl border border-border/70 bg-background/70 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-medium text-foreground">{member.name}</p>
                        <p className="mt-1 text-xs text-muted-foreground">{member.email}</p>
                      </div>
                      <Badge variant={member.role === 'owner' ? 'default' : member.role === 'admin' ? 'secondary' : 'outline'}>
                        {member.role}
                      </Badge>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Invite teammate</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <p className="eyebrow">Email</p>
                  <Input
                    type="email"
                    placeholder="colleague@example.com"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                  />
                </div>

                <div className="space-y-2">
                  <p className="eyebrow">Role</p>
                  <Select value={inviteRole} onValueChange={(value) => setInviteRole(value as typeof inviteRole)}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {isAdmin && <SelectItem value="admin">Admin</SelectItem>}
                      <SelectItem value="editor">Editor</SelectItem>
                      <SelectItem value="viewer">Viewer</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <Button onClick={sendInvite} disabled={inviting || !inviteEmail.trim()} className="w-full rounded-xl">
                  {inviting ? 'Sending invite…' : 'Send invite'}
                </Button>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="plan" className="mt-4 space-y-4">
          <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Current plan</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="rounded-2xl border border-border/70 bg-background/70 p-5">
                  <p className="eyebrow">Subscription</p>
                  <p className="mt-3 font-display text-3xl tracking-tight text-foreground">{currentPlan?.name ?? 'Starter'}</p>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {subscription ? `Status: ${subscription.status}` : 'No subscription record yet'}
                  </p>
                </div>

                {quota && (
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="rounded-2xl border border-border/70 bg-background/70 p-4">
                      <p className="eyebrow">Storage</p>
                      <p className="mt-3 text-sm font-medium text-foreground">{fmtMb(quota.quota.storage_quota_mb)}</p>
                      <p className="mt-1 text-xs text-muted-foreground">Used {fmtMb(quota.usage.storage_mb ?? 0)}</p>
                    </div>
                    <div className="rounded-2xl border border-border/70 bg-background/70 p-4">
                      <p className="eyebrow">AI spend</p>
                      <p className="mt-3 text-sm font-medium text-foreground">${quota.quota.ai_spend_cap_usd.toFixed(2)}</p>
                      <p className="mt-1 text-xs text-muted-foreground">Used ${(quota.usage.ai_spend_usd ?? 0).toFixed(2)}</p>
                    </div>
                    <div className="rounded-2xl border border-border/70 bg-background/70 p-4">
                      <p className="eyebrow">Render minutes</p>
                      <p className="mt-3 text-sm font-medium text-foreground">{quota.quota.render_minutes_quota}</p>
                    </div>
                    <div className="rounded-2xl border border-border/70 bg-background/70 p-4">
                      <p className="eyebrow">Team seats</p>
                      <p className="mt-3 text-sm font-medium text-foreground">{quota.quota.team_seats_quota}</p>
                      <p className="mt-1 text-xs text-muted-foreground">{members.length} active members</p>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Available plans</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {plans.map((plan) => {
                  const isCurrent = plan.id === subscription?.plan_id
                  const quotas = plan.quotas
                  return (
                    <div key={plan.id} className="rounded-2xl border border-border/70 bg-background/70 p-5">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-medium text-foreground">{plan.name}</p>
                          <p className="mt-1 text-xs text-muted-foreground">
                            {plan.monthly_price_usd === 0 ? 'Free' : `$${plan.monthly_price_usd}/mo`}
                          </p>
                        </div>
                        {isCurrent && <Badge>Current</Badge>}
                      </div>
                      <div className="mt-4 grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
                        <span>Storage {typeof quotas.storage_quota_mb === 'number' ? fmtMb(quotas.storage_quota_mb) : 'n/a'}</span>
                        <span>AI cap {typeof quotas.ai_spend_cap_usd === 'number' ? `$${quotas.ai_spend_cap_usd}` : 'n/a'}</span>
                        <span>Seats {typeof quotas.team_seats_quota === 'number' ? quotas.team_seats_quota : 'n/a'}</span>
                        <span>Platforms {typeof quotas.connected_platforms_quota === 'number' ? quotas.connected_platforms_quota : 'n/a'}</span>
                      </div>
                      {!isCurrent && plan.monthly_price_usd > 0 && (
                        <Button
                          className="mt-4 w-full rounded-xl"
                          disabled={checkingOut !== null}
                          onClick={() => checkout(plan.key)}
                        >
                          {checkingOut === plan.key ? 'Redirecting…' : 'Upgrade'}
                        </Button>
                      )}
                    </div>
                  )
                })}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="brand" className="mt-4 space-y-4">
          <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Workspace defaults</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="rounded-2xl border border-border/70 bg-background/70 p-4">
                  <p className="eyebrow">Slug</p>
                  <p className="mt-3 text-sm font-medium text-foreground">{workspace?.slug ?? 'workspace'}</p>
                </div>
                <div className="rounded-2xl border border-border/70 bg-background/70 p-4">
                  <p className="eyebrow">Lifecycle</p>
                  <p className="mt-3 text-sm font-medium capitalize text-foreground">{workspace?.lifecycle_status ?? 'active'}</p>
                </div>
                <div className="rounded-2xl border border-border/70 bg-background/70 p-4">
                  <p className="eyebrow">Style profiles</p>
                  <p className="mt-3 text-sm font-medium text-foreground">{profiles.length} available</p>
                </div>
                <Button asChild variant="outline" className="w-full rounded-xl">
                  <Link href="/style-profiles">Manage style profiles</Link>
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Profiles</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {profiles.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No style profiles created yet.</p>
                ) : profiles.map((profile) => (
                  <div key={profile.id} className="rounded-2xl border border-border/70 bg-background/70 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-medium text-foreground">{profile.name}</p>
                        <p className="mt-1 text-xs text-muted-foreground">{profile.genre}</p>
                      </div>
                      <Badge variant="outline">v{profile.version}</Badge>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {isAdmin && (
          <TabsContent value="admin" className="mt-4">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {adminSummary ? (
                <>
                  <div className="app-panel p-5">
                    <p className="eyebrow">Workspaces</p>
                    <p className="metric-value mt-4">{adminSummary.workspaces}</p>
                  </div>
                  <div className="app-panel p-5">
                    <p className="eyebrow">Users</p>
                    <p className="metric-value mt-4">{adminSummary.users}</p>
                  </div>
                  <div className="app-panel p-5">
                    <p className="eyebrow">Active subscriptions</p>
                    <p className="metric-value mt-4">{adminSummary.active_subscriptions}</p>
                  </div>
                  <div className="app-panel p-5">
                    <p className="eyebrow">Queued jobs</p>
                    <p className="metric-value mt-4">{adminSummary.queued_jobs}</p>
                  </div>
                  <div className="app-panel p-5">
                    <p className="eyebrow">Failed jobs</p>
                    <p className="metric-value mt-4">{adminSummary.failed_jobs}</p>
                  </div>
                  <div className="app-panel p-5">
                    <p className="eyebrow">AI spend</p>
                    <p className="metric-value mt-4">${adminSummary.ai_spend_usd.toFixed(2)}</p>
                  </div>
                </>
              ) : (
                <div className="app-panel p-8">
                  <p className="text-sm text-muted-foreground">Admin summary unavailable.</p>
                </div>
              )}
            </div>
          </TabsContent>
        )}
      </Tabs>
    </div>
  )
}
