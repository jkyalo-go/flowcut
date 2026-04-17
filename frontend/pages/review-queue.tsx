import { useEffect, useState, useRef } from 'react'
import { api } from '@/lib/api'
import { useTimelineStore } from '@/stores/timelineStore'
import type { ReviewQueueItem, AutonomySettings } from '@/types'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Separator } from '@/components/ui/separator'
import { Alert, AlertDescription } from '@/components/ui/alert'

interface AuditEntry {
  id: string
  action: string
  clip_id: string
  created_at: string
}

export default function ReviewQueuePage() {
  const [queue, setQueue] = useState<ReviewQueueItem[]>([])
  const [settings, setSettings] = useState<AutonomySettings>({
    autonomy_mode: 'supervised',
    autonomy_confidence_threshold: 0.8,
  })
  const [audit, setAudit] = useState<AuditEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [actionError, setActionError] = useState<string | null>(null)
  const [corrections, setCorrections] = useState<Record<string, string>>({})
  const [savingSettings, setSavingSettings] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const mounted = useRef(true)

  const reviewQueueDirty = useTimelineStore((s) => s.reviewQueueDirty)
  const setReviewQueueDirty = useTimelineStore((s) => s.setReviewQueueDirty)

  useEffect(() => {
    mounted.current = true
    Promise.all([
      api.get<AutonomySettings>('/api/autonomy/settings'),
      api.get<ReviewQueueItem[]>('/api/autonomy/review-queue'),
      api.get<AuditEntry[]>('/api/autonomy/audit-log').catch(() => [] as AuditEntry[]),
    ]).then(([s, q, a]) => {
      if (!mounted.current) return
      setSettings(s)
      setQueue(q)
      setAudit(a)
      setLoading(false)
    }).catch(() => {
      if (mounted.current) setLoading(false)
    })
    return () => {
      mounted.current = false
    }
  }, [])

  useEffect(() => {
    if (!reviewQueueDirty) return
    api.get<ReviewQueueItem[]>('/api/autonomy/review-queue')
      .then((q) => {
        if (!mounted.current) return
        setQueue(q)
        setReviewQueueDirty(false)
      })
      .catch(() => { if (mounted.current) setReviewQueueDirty(false) })
  }, [reviewQueueDirty, setReviewQueueDirty])

  function confidenceBadge(score: number): 'default' | 'secondary' | 'destructive' {
    if (score >= 0.8) return 'default'
    if (score >= 0.6) return 'secondary'
    return 'destructive'
  }

  function takeAction(clipId: string, action: 'approve' | 'reject') {
    const item = queue.find((i) => i.clip_id === clipId)
    if (!item) return

    // Optimistic removal
    setQueue((prev) => prev.filter((i) => i.clip_id !== clipId))
    setActionError(null)

    const correctionText = corrections[clipId]?.trim()
    const body: { corrections?: { instruction: string }[] } = {}
    if (correctionText) {
      body.corrections = [{ instruction: correctionText }]
    }

    api.post(`/api/autonomy/review-queue/${clipId}/${action}`, body).catch((err) => {
      // Restore item on error
      setQueue((prev) => [item, ...prev])
      setActionError(err instanceof Error ? err.message : 'Action failed')
    })
  }

  function saveSettings() {
    setSavingSettings(true)
    setSaveError(null)
    api.post<AutonomySettings>('/api/autonomy/settings', settings)
      .then((updated) => {
        setSettings(updated)
        setSavingSettings(false)
      })
      .catch((err) => {
        setSavingSettings(false)
        setSaveError(err instanceof Error ? err.message : 'Failed to save settings')
      })
  }

  function testNotification() {
    api.post('/api/autonomy/test-settings', {}).catch(() => {})
  }

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center">
        <p className="text-muted-foreground">Loading…</p>
      </div>
    )
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Autonomy &amp; Review</h1>

      {actionError && (
        <Alert variant="destructive">
          <AlertDescription>{actionError}</AlertDescription>
        </Alert>
      )}

      <Tabs defaultValue="queue">
        <TabsList>
          <TabsTrigger value="queue">Queue ({queue.length})</TabsTrigger>
          <TabsTrigger value="settings">Settings</TabsTrigger>
          <TabsTrigger value="audit">Audit Log</TabsTrigger>
        </TabsList>

        {/* Queue tab */}
        <TabsContent value="queue" className="space-y-4 mt-4">
          {queue.length === 0 ? (
            <p className="text-muted-foreground text-sm">No clips pending review.</p>
          ) : (
            queue.map((item) => (
              <Card key={item.id}>
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between gap-4">
                    <CardTitle className="text-base font-medium">
                      {item.title ?? item.clip_id}
                    </CardTitle>
                    <Badge variant={confidenceBadge(item.edit_confidence)}>
                      {Math.round(item.edit_confidence * 100)}% confidence
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  {item.thumbnail_urls && item.thumbnail_urls.length > 0 && (
                    <div className="flex gap-2 overflow-x-auto">
                      {item.thumbnail_urls.map((url, idx) => (
                        <img
                          key={idx}
                          src={url}
                          alt={`Thumbnail ${idx + 1}`}
                          className="h-20 w-32 object-cover rounded border"
                        />
                      ))}
                    </div>
                  )}

                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span>Status: {item.status}</span>
                    <span>·</span>
                    <span>{new Date(item.created_at).toLocaleDateString()}</span>
                  </div>

                  <div className="space-y-1">
                    <Label htmlFor={`correction-${item.clip_id}`} className="text-xs">
                      Rejection note (optional)
                    </Label>
                    <Input
                      id={`correction-${item.clip_id}`}
                      placeholder="Add correction instructions…"
                      value={corrections[item.clip_id] ?? ''}
                      onChange={(e) =>
                        setCorrections((prev) => ({
                          ...prev,
                          [item.clip_id]: e.target.value,
                        }))
                      }
                    />
                  </div>

                  <div className="flex gap-2 pt-1">
                    <Button
                      size="sm"
                      onClick={() => takeAction(item.clip_id, 'approve')}
                    >
                      Approve
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => takeAction(item.clip_id, 'reject')}
                    >
                      Reject
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </TabsContent>

        {/* Settings tab */}
        <TabsContent value="settings" className="mt-4">
          <Card>
            <CardContent className="pt-6 space-y-5">
              <div className="space-y-2">
                <Label htmlFor="autonomy-mode">Autonomy Mode</Label>
                <Select
                  value={settings.autonomy_mode}
                  onValueChange={(val) =>
                    setSettings((prev) => ({
                      ...prev,
                      autonomy_mode: val as AutonomySettings['autonomy_mode'],
                    }))
                  }
                >
                  <SelectTrigger id="autonomy-mode">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="supervised">Supervised</SelectItem>
                    <SelectItem value="review_then_publish">Review then Publish</SelectItem>
                    <SelectItem value="auto_publish">Auto Publish</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="confidence-threshold">Confidence Threshold</Label>
                <Input
                  id="confidence-threshold"
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  value={settings.autonomy_confidence_threshold}
                  onChange={(e) =>
                    setSettings((prev) => ({
                      ...prev,
                      autonomy_confidence_threshold: parseFloat(e.target.value),
                    }))
                  }
                />
              </div>

              {saveError && (
                <Alert variant="destructive">
                  <AlertDescription>{saveError}</AlertDescription>
                </Alert>
              )}

              <Separator />

              <div className="flex gap-2">
                <Button onClick={saveSettings} disabled={savingSettings}>
                  {savingSettings ? 'Saving…' : 'Save Settings'}
                </Button>
                <Button variant="outline" onClick={testNotification}>
                  Test Notification
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Audit tab */}
        <TabsContent value="audit" className="mt-4">
          {audit.length === 0 ? (
            <p className="text-muted-foreground text-sm">No audit entries found.</p>
          ) : (
            <div className="space-y-2">
              {audit.map((entry) => (
                <Card key={entry.id}>
                  <CardContent className="py-3 flex items-center justify-between text-sm">
                    <div className="space-x-2">
                      <Badge variant="secondary">{entry.action}</Badge>
                      <span className="text-muted-foreground">Clip: {entry.clip_id}</span>
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {new Date(entry.created_at).toLocaleString()}
                    </span>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
