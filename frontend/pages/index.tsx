import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { surfaceApi } from '@/lib/api'
import type { OverviewData } from '@/types'

function formatDate(value?: string | null) {
  if (!value) return 'Pending'
  return new Date(value).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function ratio(used: number, total: number) {
  if (!total) return 0
  return Math.min(100, Math.round((used / total) * 100))
}

export default function OverviewPage() {
  const [overview, setOverview] = useState<OverviewData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let mounted = true
    surfaceApi.getOverview()
      .then((data) => {
        if (!mounted) return
        setOverview(data)
        setLoading(false)
      })
      .catch((err) => {
        if (!mounted) return
        setError(err instanceof Error ? err.message : 'Failed to load overview')
        setLoading(false)
      })
    return () => { mounted = false }
  }, [])

  if (loading) {
    return (
      <div className="app-panel p-8">
        <p className="text-sm text-muted-foreground">Loading overview…</p>
      </div>
    )
  }

  if (!overview) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{error ?? 'Overview unavailable'}</AlertDescription>
      </Alert>
    )
  }

  const storageUsed = overview.quota.usage.storage_mb ?? 0
  const storageLimit = overview.quota.quota.storage_quota_mb
  const aiUsed = overview.quota.usage.ai_spend_usd ?? 0
  const aiLimit = overview.quota.quota.ai_spend_cap_usd

  return (
    <div className="space-y-6">
      <section className="app-panel overflow-hidden p-6 md:p-8">
        <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
          <div>
            <p className="eyebrow">Control room</p>
            <h2 className="mt-3 font-display text-4xl leading-tight tracking-tight text-foreground md:text-5xl">
              Keep intake, review, scheduling, and platform readiness in one operating view.
            </h2>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-muted-foreground md:text-base">
              The shell now reflects the real production state: backlog pressure, publishing health,
              quota burn, and onboarding blockers all have direct actions instead of dead-end counters.
            </p>

            <div className="mt-6 flex flex-wrap gap-3">
              <Button asChild className="rounded-xl">
                <Link href="/projects">Open projects</Link>
              </Button>
              <Button asChild variant="outline" className="rounded-xl">
                <Link href="/review-queue">Clear queue</Link>
              </Button>
              <Button asChild variant="outline" className="rounded-xl">
                <Link href="/integrations">Check integrations</Link>
              </Button>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-3 xl:grid-cols-1">
            <div className="app-panel-muted p-5">
              <p className="eyebrow">Pending review</p>
              <p className="metric-value mt-4">{overview.review.pending}</p>
              <p className="mt-2 text-sm text-muted-foreground">Clips waiting for operator approval.</p>
            </div>
            <div className="app-panel-muted p-5">
              <p className="eyebrow">Upcoming schedule</p>
              <p className="metric-value mt-4">{overview.schedule.scheduled_count}</p>
              <p className="mt-2 text-sm text-muted-foreground">Scheduled publication jobs across the workspace.</p>
            </div>
            <div className="app-panel-muted p-5">
              <p className="eyebrow">Platform readiness</p>
              <p className="metric-value mt-4">{overview.platforms.ready}<span className="text-xl text-muted-foreground"> / {overview.platforms.total}</span></p>
              <p className="mt-2 text-sm text-muted-foreground">Connected platforms ready to publish without intervention.</p>
            </div>
          </div>
        </div>
      </section>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="grid gap-6 xl:grid-cols-12">
        <section className="app-panel p-6 xl:col-span-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="eyebrow">Review backlog</p>
              <h3 className="mt-3 text-2xl text-foreground">Prioritize the queue</h3>
            </div>
            <Button asChild variant="ghost" className="rounded-xl">
              <Link href="/review-queue">Open queue</Link>
            </Button>
          </div>
          <div className="mt-5 space-y-3">
            {overview.review.items.length === 0 ? (
              <p className="text-sm text-muted-foreground">Nothing is waiting for review.</p>
            ) : overview.review.items.slice(0, 4).map((item) => (
              <div key={item.id} className="rounded-2xl border border-border/70 bg-background/75 p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="truncate text-sm font-medium text-foreground">{item.title ?? item.clip_id}</p>
                  <Badge variant={item.edit_confidence >= 0.8 ? 'default' : item.edit_confidence >= 0.6 ? 'secondary' : 'destructive'}>
                    {Math.round(item.edit_confidence * 100)}%
                  </Badge>
                </div>
                <p className="mt-2 text-xs text-muted-foreground">{formatDate(item.created_at)}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="app-panel p-6 xl:col-span-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="eyebrow">Schedule</p>
              <h3 className="mt-3 text-2xl text-foreground">Watch what ships next</h3>
            </div>
            <Button asChild variant="ghost" className="rounded-xl">
              <Link href="/calendar">Open schedule</Link>
            </Button>
          </div>
          <div className="mt-5 space-y-3">
            {overview.schedule.upcoming.length === 0 ? (
              <p className="text-sm text-muted-foreground">No upcoming publish slots yet.</p>
            ) : overview.schedule.upcoming.slice(0, 4).map((slot) => (
              <div key={slot.id} className="rounded-2xl border border-border/70 bg-background/75 p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-medium text-foreground">{slot.title ?? slot.platform}</p>
                  <Badge variant={slot.status === 'failed' ? 'destructive' : slot.status === 'published' ? 'default' : 'secondary'}>
                    {slot.status}
                  </Badge>
                </div>
                <p className="mt-2 text-xs text-muted-foreground">{formatDate(slot.scheduled_at)}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="app-panel p-6 xl:col-span-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="eyebrow">Platform readiness</p>
              <h3 className="mt-3 text-2xl text-foreground">Fix blockers before publish</h3>
            </div>
            <Button asChild variant="ghost" className="rounded-xl">
              <Link href="/integrations">Manage</Link>
            </Button>
          </div>
          <div className="mt-5 space-y-3">
            {overview.platforms.items.map((platform) => (
              <div key={platform.platform} className="rounded-2xl border border-border/70 bg-background/75 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-foreground">{platform.label}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {platform.connected ? (platform.ready ? 'Ready to publish' : `Needs ${platform.missing_fields.join(', ')}`) : 'Not connected'}
                    </p>
                  </div>
                  <Badge variant={platform.ready ? 'default' : platform.connected ? 'secondary' : 'outline'}>
                    {platform.status}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="app-panel p-6 xl:col-span-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="eyebrow">Usage</p>
              <h3 className="mt-3 text-2xl text-foreground">Track quota burn before it becomes a blocker</h3>
            </div>
            <Button asChild variant="ghost" className="rounded-xl">
              <Link href="/workspace?tab=plan">Plan &amp; usage</Link>
            </Button>
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <div className="rounded-2xl border border-border/70 bg-background/75 p-4">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-medium text-foreground">Storage</p>
                <span className="text-xs text-muted-foreground">{storageUsed.toFixed(0)} / {storageLimit} MB</span>
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
                <div className="h-full rounded-full bg-primary" style={{ width: `${ratio(storageUsed, storageLimit)}%` }} />
              </div>
            </div>
            <div className="rounded-2xl border border-border/70 bg-background/75 p-4">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-medium text-foreground">AI spend</p>
                <span className="text-xs text-muted-foreground">${aiUsed.toFixed(2)} / ${aiLimit.toFixed(2)}</span>
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
                <div className="h-full rounded-full bg-[hsl(var(--accent-foreground))]" style={{ width: `${ratio(aiUsed, aiLimit)}%` }} />
              </div>
            </div>
          </div>

          {overview.quota.exceeded.length > 0 && (
            <Alert className="mt-4">
              <AlertDescription>
                Exceeded: {overview.quota.exceeded.join(', ')}
              </AlertDescription>
            </Alert>
          )}
        </section>

        <section className="app-panel p-6 xl:col-span-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="eyebrow">Onboarding</p>
              <h3 className="mt-3 text-2xl text-foreground">Remove setup blockers</h3>
            </div>
            <Button asChild variant="ghost" className="rounded-xl">
              <Link href="/workspace?tab=brand">Open workspace</Link>
            </Button>
          </div>

          <div className="mt-5 grid gap-3 md:grid-cols-2">
            {overview.onboarding.items.map((item) => (
              <div key={item.key} className="rounded-2xl border border-border/70 bg-background/75 p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-medium text-foreground">{item.label}</p>
                  <Badge variant={item.completed ? 'default' : 'outline'}>
                    {item.completed ? 'Done' : 'Pending'}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="app-panel p-6 xl:col-span-12">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="eyebrow">Recent activity</p>
              <h3 className="mt-3 text-2xl text-foreground">What changed across the workspace</h3>
            </div>
            <div className="flex gap-2">
              <Button asChild variant="outline" className="rounded-xl">
                <Link href="/projects">Open project list</Link>
              </Button>
              <Button asChild variant="outline" className="rounded-xl">
                <Link href="/workspace">Manage workspace</Link>
              </Button>
            </div>
          </div>

          <div className="mt-5 grid gap-4 xl:grid-cols-[1fr_0.8fr]">
            <div className="space-y-3">
              {overview.activity.length === 0 ? (
                <p className="text-sm text-muted-foreground">No recent audit activity.</p>
              ) : overview.activity.slice(0, 6).map((entry) => (
                <div key={entry.id} className="rounded-2xl border border-border/70 bg-background/75 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-medium text-foreground">{entry.action}</p>
                    <span className="text-xs text-muted-foreground">{formatDate(entry.created_at)}</span>
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">
                    {entry.actor} • {entry.target_type}{entry.target_id ? ` #${entry.target_id}` : ''}
                  </p>
                </div>
              ))}
            </div>

            <div className="space-y-3">
              <div className="rounded-2xl border border-border/70 bg-background/75 p-5">
                <p className="eyebrow">Projects</p>
                <p className="metric-value mt-4">{overview.projects.total}</p>
                <p className="mt-2 text-sm text-muted-foreground">Projects in the active workspace.</p>
              </div>
              {overview.projects.recent.slice(0, 3).map((project) => (
                <Link key={project.id} href={`/projects/${project.id}`} className="block rounded-2xl border border-border/70 bg-background/75 p-4 transition hover:border-primary/30">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-medium text-foreground">{project.name}</p>
                    <Badge variant={project.render_path ? 'default' : 'outline'}>
                      {project.render_path ? 'Rendered' : `${project.clip_count} clips`}
                    </Badge>
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">{formatDate(project.created_at)}</p>
                </Link>
              ))}
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
