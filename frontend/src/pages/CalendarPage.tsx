import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { api } from '@/lib/api'
import type { CalendarSlot, GapSlot } from '@/types'

const STATUS_VARIANT: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  scheduled: 'default',
  processing: 'secondary',
  published: 'secondary',
  failed: 'destructive',
  cancelled: 'outline',
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

export function CalendarPage() {
  const [slots, setSlots] = useState<CalendarSlot[]>([])
  const [gaps, setGaps] = useState<GapSlot[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let mounted = true

    Promise.all([
      api.get<CalendarSlot[]>('/api/platforms/calendar').catch(() => [] as CalendarSlot[]),
      api.get<GapSlot[]>('/api/calendar/gaps').catch(() => [] as GapSlot[]),
    ]).then(([slotsData, gapsData]) => {
      if (mounted) {
        setSlots(slotsData)
        setGaps(gapsData)
        setLoading(false)
      }
    }).catch((err) => {
      if (mounted) {
        setError(err instanceof Error ? err.message : 'Failed to load calendar')
        setLoading(false)
      }
    })

    return () => { mounted = false }
  }, [])

  async function handleCancel(slotId: string) {
    try {
      await api.post(`/api/platforms/calendar/${slotId}/cancel`, {})
      setSlots((prev) =>
        prev.map((s) => s.id === slotId ? { ...s, status: 'cancelled' as const } : s)
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to cancel slot')
    }
  }

  async function handleRetry(slotId: string) {
    try {
      await api.post(`/api/platforms/calendar/${slotId}/retry`, {})
      setSlots((prev) =>
        prev.map((s) => s.id === slotId ? { ...s, status: 'scheduled' as const } : s)
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to retry slot')
    }
  }

  const upcomingSlots = slots.filter((s) => s.status === 'scheduled' || s.status === 'processing')
  const pastSlots = slots.filter((s) =>
    s.status === 'published' || s.status === 'failed' || s.status === 'cancelled'
  )

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Publishing Calendar</h1>
        <p className="text-sm text-muted-foreground">Manage your scheduled and past publishing slots.</p>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {loading && (
        <p className="text-sm text-muted-foreground">Loading calendar...</p>
      )}

      {!loading && (
        <>
          <Tabs defaultValue="upcoming">
            <TabsList>
              <TabsTrigger value="upcoming">Upcoming</TabsTrigger>
              <TabsTrigger value="past">Past</TabsTrigger>
            </TabsList>

            <TabsContent value="upcoming">
              <Card>
                <CardHeader>
                  <CardTitle>Upcoming slots</CardTitle>
                </CardHeader>
                <CardContent>
                  {upcomingSlots.length === 0 && (
                    <p className="text-sm text-muted-foreground">No upcoming scheduled slots.</p>
                  )}
                  {upcomingSlots.length > 0 && (
                    <div className="divide-y">
                      {upcomingSlots.map((slot) => (
                        <div key={slot.id} className="flex items-center justify-between py-3">
                          <div>
                            <p className="text-sm font-medium">{slot.platform}</p>
                            <p className="text-sm text-muted-foreground">{formatDate(slot.scheduled_at)}</p>
                          </div>
                          <div className="flex items-center gap-3">
                            <Badge variant={STATUS_VARIANT[slot.status] ?? 'outline'}>
                              {slot.status}
                            </Badge>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleCancel(slot.id)}
                            >
                              Cancel
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="past">
              <Card>
                <CardHeader>
                  <CardTitle>Past slots</CardTitle>
                </CardHeader>
                <CardContent>
                  {pastSlots.length === 0 && (
                    <p className="text-sm text-muted-foreground">No past slots.</p>
                  )}
                  {pastSlots.length > 0 && (
                    <div className="divide-y">
                      {pastSlots.map((slot) => (
                        <div key={slot.id} className="py-3 space-y-1">
                          <div className="flex items-center justify-between">
                            <div>
                              <p className="text-sm font-medium">{slot.platform}</p>
                              <p className="text-sm text-muted-foreground">{formatDate(slot.scheduled_at)}</p>
                            </div>
                            <div className="flex items-center gap-3">
                              <Badge variant={STATUS_VARIANT[slot.status] ?? 'outline'}>
                                {slot.status}
                              </Badge>
                              {slot.status === 'failed' && (
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => handleRetry(slot.id)}
                                >
                                  Retry
                                </Button>
                              )}
                            </div>
                          </div>
                          {slot.status === 'failed' && slot.failure_reason && (
                            <p className="text-sm text-destructive">{slot.failure_reason}</p>
                          )}
                          {slot.status === 'published' && slot.publish_url && (
                            <a
                              href={slot.publish_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-sm text-primary underline"
                            >
                              View published
                            </a>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>

          {gaps.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Suggested posting times</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="divide-y">
                  {gaps.slice(0, 5).map((gap) => (
                    <div key={`${gap.platform}-${gap.suggested_at}`} className="flex items-center justify-between py-3">
                      <div>
                        <p className="text-sm font-medium">{gap.platform}</p>
                        <p className="text-sm text-muted-foreground">{formatDate(gap.suggested_at)}</p>
                      </div>
                      <Badge variant="outline">{Math.round(gap.score * 100)}%</Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  )
}
