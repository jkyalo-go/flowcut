import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { api, surfaceApi } from '@/lib/api'
import { useTimelineStore } from '@/stores/timelineStore'
import type { AutonomySettings, Project, ReviewQueueSurface } from '@/types'

interface AuditEntry {
  id: string
  action: string
  actor: string
  target_type: string
  target_id?: string | null
  created_at?: string | null
}

const DEFAULT_SETTINGS: AutonomySettings = {
  autonomy_mode: 'supervised',
  confidence_threshold: 0.8,
  allowed_platforms: [],
  quiet_hours: '',
  notification_preferences: '',
}

function confidenceVariant(score: number): 'default' | 'secondary' | 'destructive' {
  if (score >= 0.8) return 'default'
  if (score >= 0.6) return 'secondary'
  return 'destructive'
}

export default function ReviewQueuePage() {
  const mounted = useRef(true)
  const reviewQueueDirty = useTimelineStore((state) => state.reviewQueueDirty)
  const setReviewQueueDirty = useTimelineStore((state) => state.setReviewQueueDirty)

  const [queue, setQueue] = useState<ReviewQueueSurface[]>([])
  const [projects, setProjects] = useState<Project[]>([])
  const [settings, setSettings] = useState<AutonomySettings>(DEFAULT_SETTINGS)
  const [audit, setAudit] = useState<AuditEntry[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState<string>('workspace')
  const [corrections, setCorrections] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [loadingSettings, setLoadingSettings] = useState(false)
  const [savingSettings, setSavingSettings] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function loadQueueState() {
    const [queueData, projectData, settingsData, auditData] = await Promise.all([
      surfaceApi.getReviewQueue(),
      surfaceApi.listProjects(),
      surfaceApi.getReviewSettings(),
      api.get<AuditEntry[]>('/api/autonomy/audit').catch(() => []),
    ])
    setQueue(queueData)
    setProjects(projectData)
    setSettings(settingsData)
    setAudit(auditData)
  }

  useEffect(() => {
    mounted.current = true
    loadQueueState()
      .catch((err) => {
        if (!mounted.current) return
        setError(err instanceof Error ? err.message : 'Failed to load review queue')
      })
      .finally(() => {
        if (mounted.current) setLoading(false)
      })
    return () => { mounted.current = false }
  }, [])

  useEffect(() => {
    if (!reviewQueueDirty) return
    surfaceApi.getReviewQueue()
      .then((items) => {
        if (!mounted.current) return
        setQueue(items)
        setReviewQueueDirty(false)
      })
      .catch(() => {
        if (mounted.current) setReviewQueueDirty(false)
      })
  }, [reviewQueueDirty, setReviewQueueDirty])

  useEffect(() => {
    if (loading) return
    setLoadingSettings(true)
    surfaceApi.getReviewSettings(selectedProjectId === 'workspace' ? undefined : selectedProjectId)
      .then((data) => {
        if (!mounted.current) return
        setSettings(data)
      })
      .catch(() => {})
      .finally(() => {
        if (mounted.current) setLoadingSettings(false)
      })
  }, [loading, selectedProjectId])

  async function takeAction(item: ReviewQueueSurface, action: 'approve' | 'reject') {
    const existing = queue
    setQueue((current) => current.filter((entry) => entry.id !== item.id))
    setError(null)

    const correctionText = corrections[item.clip_id]?.trim()
    const body: {
      action: 'approve' | 'reject'
      reason?: string
      corrections?: Array<{ instruction: string }>
    } = { action }

    if (correctionText) {
      body.reason = correctionText
      body.corrections = [{ instruction: correctionText }]
    }

    try {
      await api.post(`/api/autonomy/review-queue/${item.clip_id}`, body)
      const auditData = await api.get<AuditEntry[]>('/api/autonomy/audit').catch(() => [])
      setAudit(auditData)
    } catch (err) {
      setQueue(existing)
      setError(err instanceof Error ? err.message : 'Failed to apply review action')
    }
  }

  async function saveSettings() {
    setSavingSettings(true)
    setError(null)
    try {
      const updated = await api.post<AutonomySettings>('/api/autonomy/settings', {
        ...settings,
        ...(selectedProjectId !== 'workspace' ? { project_id: selectedProjectId } : {}),
      })
      setSettings(updated)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save review settings')
    } finally {
      setSavingSettings(false)
    }
  }

  async function sendTestNotification() {
    try {
      await api.post('/api/autonomy/notifications/test', {})
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send test notification')
    }
  }

  if (loading) {
    return (
      <div className="app-panel p-8">
        <p className="text-sm text-muted-foreground">Loading queue…</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <section className="app-panel p-6 md:p-8">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="eyebrow">Queue</p>
            <h2 className="mt-3 font-display text-4xl tracking-tight text-foreground">Approve, reject, and tune automation without leaving the live queue.</h2>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-muted-foreground">
              The route now uses the normalized review action contract and pulls workspace or project-level settings from the same backend shape the rest of the shell consumes.
            </p>
          </div>
          <Button asChild variant="outline" className="rounded-xl">
            <Link href="/projects">Open projects</Link>
          </Button>
        </div>
      </section>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Tabs defaultValue="queue">
        <TabsList>
          <TabsTrigger value="queue">Queue ({queue.length})</TabsTrigger>
          <TabsTrigger value="settings">Automation</TabsTrigger>
          <TabsTrigger value="audit">Audit</TabsTrigger>
        </TabsList>

        <TabsContent value="queue" className="mt-4 space-y-4">
          {queue.length === 0 ? (
            <div className="app-panel p-8">
              <p className="text-sm text-muted-foreground">Nothing is waiting for review.</p>
            </div>
          ) : queue.map((item) => (
            <Card key={item.id}>
              <CardHeader className="pb-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <CardTitle className="text-base">{item.title ?? item.clip_id}</CardTitle>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Created {new Date(item.created_at).toLocaleString()}
                    </p>
                  </div>
                  <Badge variant={confidenceVariant(item.edit_confidence)}>
                    {Math.round(item.edit_confidence * 100)}% confidence
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {item.thumbnail_urls && item.thumbnail_urls.length > 0 && (
                  <div className="flex gap-2 overflow-x-auto">
                    {item.thumbnail_urls.map((url, index) => (
                      <img
                        key={`${item.id}-${index}`}
                        src={url}
                        alt={`Thumbnail ${index + 1}`}
                        className="h-20 w-32 rounded-xl border border-border object-cover"
                      />
                    ))}
                  </div>
                )}

                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span>Status: {item.status}</span>
                  {item.project_id && (
                    <>
                      <span>•</span>
                      <Link href={`/projects/${item.project_id}`} className="text-primary underline underline-offset-2">
                        Open project
                      </Link>
                    </>
                  )}
                </div>

                <div className="space-y-2">
                  <p className="eyebrow">Rejection note</p>
                  <Input
                    placeholder="Add correction instructions for a reject action"
                    value={corrections[item.clip_id] ?? ''}
                    onChange={(e) => setCorrections((current) => ({ ...current, [item.clip_id]: e.target.value }))}
                  />
                </div>

                <div className="flex flex-wrap gap-2">
                  <Button size="sm" className="rounded-xl" onClick={() => takeAction(item, 'approve')}>
                    Approve
                  </Button>
                  <Button size="sm" variant="destructive" className="rounded-xl" onClick={() => takeAction(item, 'reject')}>
                    Reject
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </TabsContent>

        <TabsContent value="settings" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Automation scope</CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="grid gap-4 lg:grid-cols-2">
                <div className="space-y-2">
                  <p className="eyebrow">Apply settings to</p>
                  <Select value={selectedProjectId} onValueChange={setSelectedProjectId}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="workspace">Workspace default</SelectItem>
                      {projects.map((project) => (
                        <SelectItem key={project.id} value={project.id}>
                          {project.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <p className="eyebrow">Confidence threshold</p>
                  <Input
                    type="number"
                    min="0"
                    max="1"
                    step="0.05"
                    value={settings.confidence_threshold}
                    onChange={(e) => setSettings((current) => ({ ...current, confidence_threshold: Number(e.target.value) }))}
                    disabled={loadingSettings}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <p className="eyebrow">Automation mode</p>
                <div className="flex flex-wrap gap-2">
                  {(['supervised', 'review_then_publish', 'auto_publish'] as const).map((mode) => (
                    <Button
                      key={mode}
                      type="button"
                      variant={settings.autonomy_mode === mode ? 'default' : 'outline'}
                      size="sm"
                      className="rounded-xl"
                      disabled={loadingSettings}
                      onClick={() => setSettings((current) => ({ ...current, autonomy_mode: mode }))}
                    >
                      {mode.replace(/_/g, ' ')}
                    </Button>
                  ))}
                </div>
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <div className="space-y-2">
                  <p className="eyebrow">Quiet hours</p>
                  <Input
                    placeholder="22:00-07:00 Africa/Nairobi"
                    value={settings.quiet_hours ?? ''}
                    onChange={(e) => setSettings((current) => ({ ...current, quiet_hours: e.target.value }))}
                    disabled={loadingSettings}
                  />
                </div>
                <div className="space-y-2">
                  <p className="eyebrow">Notifications</p>
                  <Input
                    placeholder="email,slack"
                    value={settings.notification_preferences ?? ''}
                    onChange={(e) => setSettings((current) => ({ ...current, notification_preferences: e.target.value }))}
                    disabled={loadingSettings}
                  />
                </div>
              </div>

              <div className="flex flex-wrap justify-end gap-2">
                <Button variant="outline" onClick={sendTestNotification} className="rounded-xl">
                  Test notification
                </Button>
                <Button onClick={saveSettings} disabled={savingSettings || loadingSettings} className="rounded-xl">
                  {savingSettings ? 'Saving…' : 'Save settings'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="audit" className="mt-4 space-y-4">
          {audit.length === 0 ? (
            <div className="app-panel p-8">
              <p className="text-sm text-muted-foreground">No audit entries yet.</p>
            </div>
          ) : audit.slice(0, 20).map((entry) => (
            <div key={entry.id} className="app-panel p-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-foreground">{entry.action}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {entry.actor} • {entry.target_type}{entry.target_id ? ` #${entry.target_id}` : ''}
                  </p>
                </div>
                <span className="text-xs text-muted-foreground">
                  {entry.created_at ? new Date(entry.created_at).toLocaleString() : 'Pending'}
                </span>
              </div>
            </div>
          ))}
        </TabsContent>
      </Tabs>
    </div>
  )
}
