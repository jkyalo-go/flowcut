import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { api } from '@/lib/api'
import type { PlatformConnection } from '@/types'

const SUPPORTED_PLATFORMS = ['youtube', 'tiktok', 'instagram_reels', 'linkedin', 'x']

const PLATFORM_LABELS: Record<string, string> = {
  youtube: 'YouTube',
  tiktok: 'TikTok',
  instagram_reels: 'Instagram Reels',
  linkedin: 'LinkedIn',
  x: 'X (Twitter)',
}

export function PlatformsPage() {
  const [connections, setConnections] = useState<PlatformConnection[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [redirecting, setRedirecting] = useState<string | null>(null)
  const [disconnecting, setDisconnecting] = useState<string | null>(null)

  useEffect(() => {
    let mounted = true
    api.get<PlatformConnection[]>('/api/platforms')
      .then((data) => {
        if (mounted) {
          setConnections(data)
          setLoading(false)
        }
      })
      .catch((err) => {
        if (mounted) {
          setError(err instanceof Error ? err.message : 'Failed to load platforms')
          setLoading(false)
        }
      })
    return () => { mounted = false }
  }, [])

  async function handleConnect(platform: string) {
    setError('')
    setRedirecting(platform)
    try {
      const data = await api.get<{ url: string }>(`/api/platforms/${platform}/auth/start`)
      if (!data?.url) {
        setError('OAuth start returned no redirect URL')
        setRedirecting(null)
        return
      }
      window.location.assign(data.url)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start OAuth')
      setRedirecting(null)
    }
  }

  async function handleDisconnect(platform: string) {
    setError('')
    setDisconnecting(platform)
    try {
      await api.delete(`/api/platforms/${platform}`)
      setConnections((prev) => prev.filter((c) => c.platform !== platform))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to disconnect platform')
    } finally {
      setDisconnecting(null)
    }
  }

  const connectedPlatforms = new Set(connections.map((c) => c.platform))

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Platforms</h1>
        <p className="text-sm text-muted-foreground">Manage your connected publishing platforms.</p>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Connected platforms</CardTitle>
        </CardHeader>
        <CardContent>
          {loading && (
            <p className="text-sm text-muted-foreground">Loading platforms...</p>
          )}
          {!loading && connections.length === 0 && (
            <p className="text-sm text-muted-foreground">No platforms connected yet.</p>
          )}
          {!loading && connections.length > 0 && (
            <div className="divide-y">
              {connections.map((conn) => (
                <div key={conn.id} className="flex items-center justify-between py-3">
                  <div>
                    <p className="text-sm font-medium">
                      {PLATFORM_LABELS[conn.platform] ?? conn.platform}
                    </p>
                    <p className="text-sm text-muted-foreground">{conn.display_name}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge variant={conn.status === 'active' ? 'default' : 'secondary'}>
                      {conn.status}
                    </Badge>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleDisconnect(conn.platform)}
                      disabled={disconnecting === conn.platform}
                    >
                      {disconnecting === conn.platform ? 'Disconnecting...' : 'Disconnect'}
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Add platform</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {SUPPORTED_PLATFORMS.map((platform) => {
              const isConnected = connectedPlatforms.has(platform)
              const isRedirecting = redirecting === platform
              return (
                <div key={platform} className="flex items-center justify-between">
                  <span className="text-sm font-medium">
                    {PLATFORM_LABELS[platform] ?? platform}
                  </span>
                  <Button
                    size="sm"
                    onClick={() => handleConnect(platform)}
                    disabled={isConnected || isRedirecting || loading}
                  >
                    {isRedirecting
                      ? 'Redirecting...'
                      : `Connect ${PLATFORM_LABELS[platform] ?? platform}`}
                  </Button>
                </div>
              )
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
