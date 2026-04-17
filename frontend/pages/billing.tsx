import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { api } from '@/lib/api'
import type { SubscriptionPlan, WorkspaceSubscription, QuotaPolicy, UsageRecord } from '@/types'

function fmtMb(mb: number) {
  return mb >= 1024 ? `${(mb / 1024).toFixed(0)} GB` : `${mb} MB`
}

export default function BillingPage() {
  const [plans, setPlans] = useState<SubscriptionPlan[]>([])
  const [sub, setSub] = useState<WorkspaceSubscription | null>(null)
  const [quota, setQuota] = useState<QuotaPolicy | null>(null)
  const [, setUsage] = useState<UsageRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [checkingOut, setCheckingOut] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let mounted = true

    Promise.all([
      api.get<SubscriptionPlan[]>('/api/enterprise/plans'),
      api.get<WorkspaceSubscription>('/api/enterprise/subscription').catch(() => null),
      api.get<QuotaPolicy>('/api/enterprise/quota').catch(() => null),
      api.get<UsageRecord[]>('/api/enterprise/usage').catch((): UsageRecord[] => []),
    ])
      .then(([plansData, subData, quotaData, usageData]) => {
        if (!mounted) return
        setPlans(plansData)
        setSub(subData)
        setQuota(quotaData)
        setUsage(usageData)
      })
      .catch((err: unknown) => {
        if (!mounted) return
        setError(err instanceof Error ? err.message : 'Failed to load billing data')
      })
      .finally(() => {
        if (mounted) setLoading(false)
      })

    return () => {
      mounted = false
    }
  }, [])

  async function checkout(planKey: string) {
    setCheckingOut(planKey)
    try {
      const data = await api.post<{ url: string }>('/billing/checkout', { plan_key: planKey })
      window.location.assign(data.url)
    } catch (err: unknown) {
      setCheckingOut(null)
      setError(err instanceof Error ? err.message : 'Checkout failed')
    }
  }

  const currentPlan = sub ? plans.find((p) => p.id === sub.plan_id) : null

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-8">
      {/* Header */}
      <div className="flex items-center gap-3">
        <h1 className="text-3xl font-bold">Billing</h1>
        {sub && (
          <Badge variant="secondary" className="capitalize">
            {sub.status}
          </Badge>
        )}
        {currentPlan && (
          <Badge variant="outline">Plan: {currentPlan.name}</Badge>
        )}
      </div>

      {/* Error alert */}
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Current quota card */}
      {quota && (
        <Card>
          <CardHeader>
            <CardTitle>Current quota</CardTitle>
            <CardDescription>Your workspace resource limits</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <div>
                <p className="text-sm text-muted-foreground">Storage</p>
                <p className="text-lg font-semibold">{fmtMb(quota.storage_quota_mb)}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">AI spend cap</p>
                <p className="text-lg font-semibold">${quota.ai_spend_cap_usd}/mo</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Render minutes</p>
                <p className="text-lg font-semibold">{quota.render_minutes_quota} min</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Connected platforms</p>
                <p className="text-lg font-semibold">{quota.connected_platforms_quota}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Team seats</p>
                <p className="text-lg font-semibold">{quota.team_seats_quota}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Footage retention</p>
                <p className="text-lg font-semibold">{quota.retained_footage_days} days</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Plans grid */}
      {!loading && plans.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {plans.map((plan) => {
            const isCurrent = currentPlan?.id === plan.id
            let quotas: Record<string, unknown> = {}
            try {
              quotas = JSON.parse(plan.quotas_json)
            } catch {}

            const storageMb = typeof quotas.storage_quota_mb === 'number' ? quotas.storage_quota_mb : null
            const aiCap = typeof quotas.ai_spend_cap_usd === 'number' ? quotas.ai_spend_cap_usd : null
            const seats = typeof quotas.team_seats_quota === 'number' ? quotas.team_seats_quota : null

            return (
              <Card
                key={plan.id}
                className={isCurrent ? 'border-primary border-2' : undefined}
              >
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle>{plan.name}</CardTitle>
                    {isCurrent && <Badge>Current</Badge>}
                  </div>
                  <CardDescription>
                    {plan.monthly_price_usd === 0
                      ? 'Free'
                      : `$${plan.monthly_price_usd}/mo`}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {storageMb !== null && (
                    <p className="text-sm text-muted-foreground">
                      Storage: <span className="text-foreground font-medium">{fmtMb(storageMb)}</span>
                    </p>
                  )}
                  {aiCap !== null && (
                    <p className="text-sm text-muted-foreground">
                      AI cap: <span className="text-foreground font-medium">${aiCap}/mo</span>
                    </p>
                  )}
                  {seats !== null && (
                    <p className="text-sm text-muted-foreground">
                      Team seats: <span className="text-foreground font-medium">{seats}</span>
                    </p>
                  )}
                  {!isCurrent && plan.monthly_price_usd > 0 && (
                    <Button
                      className="w-full mt-2"
                      disabled={checkingOut !== null}
                      onClick={() => checkout(plan.key)}
                    >
                      {checkingOut === plan.key ? 'Redirecting…' : 'Upgrade'}
                    </Button>
                  )}
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}

      {loading && (
        <p className="text-muted-foreground text-sm">Loading billing information…</p>
      )}
    </div>
  )
}
