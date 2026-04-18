import { useEffect, useMemo, useState } from 'react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { DateTimePickerField } from '@/components/DateTimePickerField'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { api, surfaceApi } from '@/lib/api'
import type { CalendarSlotSurface, GapSlot, PlatformSurface } from '@/types'

function statusVariant(status: string): 'default' | 'secondary' | 'destructive' | 'outline' {
  if (status === 'published') return 'default'
  if (status === 'failed') return 'destructive'
  if (status === 'scheduled') return 'secondary'
  return 'outline'
}

function localDraftToIsoString(value: string): string {
  return new Date(value).toISOString()
}

export default function CalendarPage() {
  const [slots, setSlots] = useState<CalendarSlotSurface[]>([])
  const [platforms, setPlatforms] = useState<PlatformSurface[]>([])
  const [gaps, setGaps] = useState<GapSlot[]>([])
  const [selectedPlatform, setSelectedPlatform] = useState<string>('all')
  const [rescheduleDrafts, setRescheduleDrafts] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const localTimeZone = useMemo(() => Intl.DateTimeFormat().resolvedOptions().timeZone, [])

  async function loadCalendarState() {
    const [slotData, platformData] = await Promise.all([
      surfaceApi.getCalendar(),
      surfaceApi.getPlatforms(),
    ])
    return { platformData, slotData }
  }

  useEffect(() => {
    let mounted = true
    void (async () => {
      try {
        const { platformData, slotData } = await loadCalendarState()
        if (!mounted) return
        setSlots(slotData)
        setPlatforms(platformData)
      } catch (err) {
        if (!mounted) return
        setError(err instanceof Error ? err.message : 'Failed to load calendar')
      } finally {
        if (mounted) setLoading(false)
      }
    })()
    return () => { mounted = false }
  }, [])

  const gapPlatform = useMemo(() => {
    if (selectedPlatform !== 'all') return selectedPlatform
    return platforms.find((platform) => platform.connected)?.platform ?? ''
  }, [platforms, selectedPlatform])

  useEffect(() => {
    let mounted = true
    void (async () => {
      if (!gapPlatform) {
        if (mounted) setGaps([])
        return
      }
      try {
        const nextGaps = await surfaceApi.getCalendarGaps(gapPlatform)
        if (mounted) setGaps(nextGaps)
      } catch {
        if (mounted) setGaps([])
      }
    })()
    return () => { mounted = false }
  }, [gapPlatform])

  const visibleSlots = selectedPlatform === 'all'
    ? slots
    : slots.filter((slot) => slot.platform === selectedPlatform)

  async function runSlotAction(path: string) {
    setError(null)
    try {
      await api.post(path, {})
      const { platformData, slotData } = await loadCalendarState()
      setSlots(slotData)
      setPlatforms(platformData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Calendar action failed')
    }
  }

  async function reschedule(slotId: string) {
    const draft = rescheduleDrafts[slotId]
    if (!draft) return
    setError(null)
    try {
      await api.post(`/api/platforms/calendar/${slotId}/reschedule?scheduled_at=${encodeURIComponent(localDraftToIsoString(draft))}`, {})
      const { platformData, slotData } = await loadCalendarState()
      setSlots(slotData)
      setPlatforms(platformData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reschedule slot')
    }
  }

  if (loading) {
    return (
      <div className="app-panel p-8">
        <p className="text-sm text-muted-foreground">Loading schedule…</p>
      </div>
    )
  }

  const scheduledCount = slots.filter((slot) => slot.status === 'scheduled').length
  const failedCount = slots.filter((slot) => slot.status === 'failed').length
  const publishedCount = slots.filter((slot) => slot.status === 'published').length

  return (
    <div className="space-y-6">
      <section className="app-panel p-6 md:p-8">
        <div className="grid gap-6 xl:grid-cols-[1fr_23rem]">
          <div>
            <p className="eyebrow">Schedule</p>
            <h2 className="mt-3 font-display text-4xl tracking-tight text-foreground">Operate publication timing, retries, and recovery from one calendar route.</h2>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-muted-foreground">
              The live schedule now consumes the real platform calendar endpoints and requires platform-aware gap analysis instead of guessing at missing parameters.
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
            <div className="app-panel-muted p-4">
              <p className="eyebrow">Scheduled</p>
              <p className="metric-value mt-3">{scheduledCount}</p>
            </div>
            <div className="app-panel-muted p-4">
              <p className="eyebrow">Failed</p>
              <p className="metric-value mt-3">{failedCount}</p>
            </div>
            <div className="app-panel-muted p-4">
              <p className="eyebrow">Published</p>
              <p className="metric-value mt-3">{publishedCount}</p>
            </div>
          </div>
        </div>
      </section>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="grid gap-6 xl:grid-cols-[1fr_20rem]">
        <section className="space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Platform filter</CardTitle>
            </CardHeader>
            <CardContent>
              <Select value={selectedPlatform} onValueChange={setSelectedPlatform}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All platforms</SelectItem>
                  {platforms.map((platform) => (
                    <SelectItem key={platform.platform} value={platform.platform}>
                      {platform.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </CardContent>
          </Card>

          {visibleSlots.length === 0 ? (
            <div className="app-panel p-8">
              <p className="text-sm text-muted-foreground">No publish jobs for this filter yet.</p>
            </div>
          ) : visibleSlots.map((slot) => (
            <Card key={slot.id}>
              <CardHeader className="pb-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <CardTitle className="text-base">{slot.title ?? slot.platform}</CardTitle>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {slot.scheduled_at ? new Date(slot.scheduled_at).toLocaleString() : 'No schedule time'}
                    </p>
                  </div>
                  <Badge variant={statusVariant(slot.status)}>{slot.status}</Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                  <span>{slot.platform}</span>
                  {slot.publish_url && (
                    <>
                      <span>•</span>
                      <a href={slot.publish_url} target="_blank" rel="noreferrer" className="text-primary underline underline-offset-2">
                        View publish URL
                      </a>
                    </>
                  )}
                  {slot.failure_reason && (
                    <>
                      <span>•</span>
                      <span>{slot.failure_reason}</span>
                    </>
                  )}
                </div>

                <div className="flex flex-wrap gap-2">
                  {(slot.status === 'scheduled' || slot.status === 'processing') && (
                    <Button size="sm" variant="outline" className="rounded-xl" onClick={() => runSlotAction(`/api/platforms/calendar/${slot.id}/execute`)}>
                      Execute now
                    </Button>
                  )}
                  {slot.status === 'failed' && (
                    <Button size="sm" className="rounded-xl" onClick={() => runSlotAction(`/api/platforms/calendar/${slot.id}/retry`)}>
                      Retry
                    </Button>
                  )}
                  {slot.status !== 'cancelled' && slot.status !== 'published' && (
                    <Button size="sm" variant="outline" className="rounded-xl" onClick={() => runSlotAction(`/api/platforms/calendar/${slot.id}/cancel`)}>
                      Cancel
                    </Button>
                  )}
                </div>

                {slot.status !== 'published' && (
                  <div className="grid gap-2 md:grid-cols-[1fr_auto]">
                    <div className="space-y-2">
                      <DateTimePickerField
                        value={rescheduleDrafts[slot.id] ?? ''}
                        onChange={(value) => setRescheduleDrafts((current) => ({ ...current, [slot.id]: value }))}
                        placeholder="Pick a publish date"
                      />
                      <p className="text-xs text-muted-foreground">
                        Reschedules in {localTimeZone}. The saved publish time is converted to UTC.
                      </p>
                    </div>
                    <Button variant="outline" className="rounded-xl" onClick={() => reschedule(slot.id)}>
                      Reschedule
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </section>

        <aside className="space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Gap suggestions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {!gapPlatform ? (
                <p className="text-sm text-muted-foreground">Connect a platform to generate publish gap suggestions.</p>
              ) : gaps.length === 0 ? (
                <p className="text-sm text-muted-foreground">No suggested slots returned for {gapPlatform}.</p>
              ) : gaps.map((gap) => (
                <div key={`${gap.platform}-${gap.suggested_at}`} className="rounded-2xl border border-border/70 bg-background/70 p-4">
                  <p className="text-sm font-medium text-foreground">{new Date(gap.suggested_at).toLocaleString()}</p>
                  <p className="mt-2 text-xs text-muted-foreground">Score {gap.score.toFixed(2)} on {gap.platform}</p>
                </div>
              ))}
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  )
}
