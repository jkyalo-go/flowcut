import { useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/router'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { BrandLogo } from '@/components/BrandLogo'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { api, surfaceApi } from '@/lib/api'
import type { AICredentialSurface, AIProviderSurface, AIUsageSurface, AutonomySettings, PlatformSurface } from '@/types'

type IntegrationTab = 'platforms' | 'ai' | 'publishing'

interface ManualConnectState {
  fields: Record<string, string>
  instructions: string
  platform: string
  requiredFields: string[]
}

const DEFAULT_SETTINGS: AutonomySettings = {
  autonomy_mode: 'supervised',
  confidence_threshold: 0.8,
  allowed_platforms: [],
  quiet_hours: '',
  notification_preferences: '',
}

function activeTabFromQuery(value: string | string[] | undefined): IntegrationTab {
  return value === 'ai' || value === 'publishing' ? value : 'platforms'
}

export default function IntegrationsPage() {
  const router = useRouter()
  const activeTab = activeTabFromQuery(router.query.tab)
  const [platforms, setPlatforms] = useState<PlatformSurface[]>([])
  const [providers, setProviders] = useState<AIProviderSurface[]>([])
  const [credentials, setCredentials] = useState<AICredentialSurface[]>([])
  const [usage, setUsage] = useState<AIUsageSurface[]>([])
  const [settings, setSettings] = useState<AutonomySettings>(DEFAULT_SETTINGS)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [manualConnect, setManualConnect] = useState<ManualConnectState | null>(null)

  async function loadData() {
    const [platformData, providerData, credentialData, usageData, settingsData] = await Promise.all([
      surfaceApi.getPlatforms(),
      surfaceApi.getAIProviders().catch(() => []),
      surfaceApi.getAICredentials().catch(() => []),
      surfaceApi.getAIUsage().catch(() => []),
      surfaceApi.getReviewSettings().catch(() => DEFAULT_SETTINGS),
    ])
    setPlatforms(platformData)
    setProviders(providerData)
    setCredentials(credentialData)
    setUsage(usageData)
    setSettings(settingsData)
  }

  useEffect(() => {
    let mounted = true
    loadData()
      .catch((err) => {
        if (!mounted) return
        setError(err instanceof Error ? err.message : 'Failed to load integrations')
      })
      .finally(() => {
        if (mounted) setLoading(false)
      })
    return () => { mounted = false }
  }, [])

  async function connectPlatform(platform: string) {
    setError(null)
    try {
      const data = await api.get<{
        auth_url?: string
        instructions?: string
        mode?: string
        required_fields?: string[]
        url?: string
      }>(`/api/platforms/${platform}/auth/start`)
      if (data.mode === 'manual_token') {
        const requiredFields = data.required_fields ?? []
        setManualConnect({
          platform,
          instructions: data.instructions ?? 'Provide the required platform credentials to complete the connection.',
          requiredFields,
          fields: Object.fromEntries(requiredFields.map((field) => [field, ''])),
        })
        return
      }
      const authUrl = data.auth_url ?? data.url
      if (!authUrl) throw new Error('Missing platform authorization URL')
      window.open(authUrl, '_blank', 'width=640,height=800')
      window.setTimeout(() => {
        loadData().catch(() => {})
      }, 1500)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start platform auth')
    }
  }

  async function submitManualConnection() {
    if (!manualConnect) return
    setError(null)
    const accessToken = manualConnect.fields.access_token?.trim()
    if (!accessToken) {
      setError('Access token is required')
      return
    }
    const metadata = Object.fromEntries(
      Object.entries(manualConnect.fields)
        .filter(([field, value]) => field !== 'access_token' && field !== 'refresh_token' && field !== 'account_id' && field !== 'account_name' && value.trim())
        .map(([field, value]) => [field, value.trim()])
    )
    try {
      await api.post(`/api/platforms/${manualConnect.platform}`, {
        platform: manualConnect.platform,
        access_token: accessToken,
        refresh_token: manualConnect.fields.refresh_token?.trim() || null,
        account_id: manualConnect.fields.account_id?.trim() || null,
        account_name: manualConnect.fields.account_name?.trim() || null,
        metadata_json: JSON.stringify(metadata),
      })
      setManualConnect(null)
      await loadData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save platform credentials')
    }
  }

  async function disconnectPlatform(platform: string) {
    setError(null)
    try {
      await api.delete(`/api/platforms/${platform}`)
      await loadData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to disconnect platform')
    }
  }

  async function savePublishingDefaults() {
    setSaving(true)
    setError(null)
    try {
      const updated = await api.post<AutonomySettings>('/api/autonomy/settings', settings)
      setSettings(updated)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save defaults')
    } finally {
      setSaving(false)
    }
  }

  const connectedPlatforms = useMemo(
    () => platforms.filter((platform) => platform.connected),
    [platforms],
  )

  if (loading) {
    return (
      <div className="app-panel p-8">
        <p className="text-sm text-muted-foreground">Loading integrations…</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <section className="app-panel p-6 md:p-8">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="eyebrow">Integrations</p>
            <h2 className="mt-3 font-display text-4xl tracking-tight text-foreground">Manage platforms, provider access, and publishing defaults from one route.</h2>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-muted-foreground">
              Platform connections, AI capacity, credential inventory, and workspace-level publish defaults now live together instead of being scattered across placeholder pages.
            </p>
          </div>
          <Button variant="outline" onClick={() => loadData().catch(() => {})} className="rounded-xl">
            Refresh state
          </Button>
        </div>
      </section>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Tabs
        value={activeTab}
        onValueChange={(value) => {
          router.replace(`/integrations?tab=${value as IntegrationTab}`, undefined, { shallow: true })
        }}
      >
        <TabsList>
          <TabsTrigger value="platforms">Platforms</TabsTrigger>
          <TabsTrigger value="ai">AI</TabsTrigger>
          <TabsTrigger value="publishing">Publishing defaults</TabsTrigger>
        </TabsList>

        <TabsContent value="platforms" className="mt-4">
          <div className="grid gap-4 md:grid-cols-2">
            {platforms.map((platform) => (
              <Card key={platform.platform}>
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3">
                      <BrandLogo slug={platform.platform} label={platform.label} size={28} className="mt-0.5" />
                      <div>
                        <CardTitle className="text-base">{platform.label}</CardTitle>
                        <p className="mt-1 text-sm text-muted-foreground">
                          {platform.connected
                            ? platform.ready
                              ? `Connected as ${platform.connection?.account_name ?? platform.display_name}`
                              : `Missing ${platform.missing_fields.join(', ')}`
                            : 'No active connection'}
                        </p>
                      </div>
                    </div>
                    <Badge variant={platform.ready ? 'default' : platform.connected ? 'secondary' : 'outline'}>
                      {platform.status}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="rounded-2xl border border-border/70 bg-background/70 p-4">
                      <p className="eyebrow">Ratios</p>
                      <p className="mt-3 text-sm text-foreground">{platform.aspect_ratios.join(', ') || 'Default'}</p>
                    </div>
                    <div className="rounded-2xl border border-border/70 bg-background/70 p-4">
                      <p className="eyebrow">Scheduling</p>
                      <p className="mt-3 text-sm text-foreground">{platform.supports_scheduling ? 'Supported' : 'Not supported'}</p>
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    {platform.connected ? (
                      <Button variant="outline" onClick={() => disconnectPlatform(platform.platform)} className="rounded-xl">
                        Disconnect
                      </Button>
                    ) : (
                      <Button onClick={() => connectPlatform(platform.platform)} className="rounded-xl">
                        Connect
                      </Button>
                    )}
                    <Badge variant="outline" className="rounded-xl px-3 py-1">
                      Title limit {platform.title_limit || 'n/a'}
                    </Badge>
                      <Badge variant="outline" className="rounded-xl px-3 py-1">
                        Body limit {platform.body_limit || 'n/a'}
                      </Badge>
                  </div>

                  {manualConnect?.platform === platform.platform && (
                    <div className="space-y-3 rounded-2xl border border-border/70 bg-background/70 p-4">
                      <p className="text-sm text-muted-foreground">{manualConnect.instructions}</p>
                      <div className="grid gap-3 sm:grid-cols-2">
                        {manualConnect.requiredFields.map((field) => (
                          <div key={field} className="space-y-2">
                            <p className="eyebrow">{field.replace(/_/g, ' ')}</p>
                            <Input
                              type={field.toLowerCase().includes('token') ? 'password' : 'text'}
                              value={manualConnect.fields[field] ?? ''}
                              onChange={(event) => setManualConnect((current) => current && current.platform === platform.platform
                                ? {
                                    ...current,
                                    fields: { ...current.fields, [field]: event.target.value },
                                  }
                                : current)}
                            />
                          </div>
                        ))}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Button onClick={submitManualConnection} className="rounded-xl">
                          Save credentials
                        </Button>
                        <Button variant="outline" onClick={() => setManualConnect(null)} className="rounded-xl">
                          Cancel
                        </Button>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="ai" className="mt-4 space-y-4">
          <div className="grid gap-4 xl:grid-cols-[1fr_0.8fr]">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Model providers</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {providers.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No provider catalog available.</p>
                ) : providers.map((provider) => (
                  <div key={provider.id} className="rounded-2xl border border-border/70 bg-background/70 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-3">
                        <BrandLogo slug={provider.provider} label={provider.display_name} size={24} />
                        <div>
                          <p className="text-sm font-medium text-foreground">{provider.display_name}</p>
                          <p className="mt-1 text-xs text-muted-foreground">{provider.provider} • {provider.model_key}</p>
                        </div>
                      </div>
                      <Badge variant={provider.enabled ? 'default' : 'outline'}>
                        {provider.enabled ? 'Enabled' : 'Disabled'}
                      </Badge>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {provider.task_types.map((task) => (
                        <Badge key={task} variant="secondary">{task}</Badge>
                      ))}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>

            <div className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Credentials</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {credentials.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No credentials configured.</p>
                  ) : credentials.map((credential) => (
                    <div key={credential.id} className="rounded-2xl border border-border/70 bg-background/70 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-medium text-foreground">{credential.label ?? credential.provider}</p>
                        <Badge variant={credential.is_active ? 'default' : 'outline'}>
                          {credential.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                      </div>
                      <p className="mt-2 text-xs text-muted-foreground">
                        {credential.allowed_models.length > 0 ? credential.allowed_models.join(', ') : 'No model restrictions'}
                      </p>
                    </div>
                  ))}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Recent usage</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {usage.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No recent AI usage records.</p>
                  ) : usage.slice(0, 6).map((record) => (
                    <div key={record.id ?? `${record.provider}-${record.task_type}-${record.created_at ?? ''}`} className="rounded-2xl border border-border/70 bg-background/70 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-medium text-foreground">{record.task_type}</p>
                        <span className="text-xs text-muted-foreground">
                          {record.cost_estimate != null ? `$${record.cost_estimate.toFixed(4)}` : 'Pending'}
                        </span>
                      </div>
                      <p className="mt-2 text-xs text-muted-foreground">{record.provider}{record.model ? ` • ${record.model}` : ''}</p>
                    </div>
                  ))}
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="publishing" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Workspace publishing defaults</CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="grid gap-4 lg:grid-cols-2">
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
                        onClick={() => setSettings((current) => ({ ...current, autonomy_mode: mode }))}
                      >
                        {mode.replace(/_/g, ' ')}
                      </Button>
                    ))}
                  </div>
                </div>

                <div className="space-y-2">
                  <p className="eyebrow">Confidence threshold</p>
                  <Input
                    type="number"
                    min="0"
                    max="1"
                    step="0.05"
                    value={settings.confidence_threshold}
                    onChange={(e) => setSettings((current) => ({
                      ...current,
                      confidence_threshold: Number(e.target.value),
                    }))}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <p className="eyebrow">Allowed platforms</p>
                <div className="flex flex-wrap gap-2">
                  {connectedPlatforms.length === 0 ? (
                    <p className="text-sm text-muted-foreground">Connect platforms first to set workspace defaults.</p>
                  ) : connectedPlatforms.map((platform) => {
                    const selected = settings.allowed_platforms?.includes(platform.platform) ?? false
                    return (
                      <Button
                        key={platform.platform}
                        type="button"
                        variant={selected ? 'default' : 'outline'}
                        size="sm"
                        className="rounded-xl"
                        onClick={() => setSettings((current) => {
                          const currentList = current.allowed_platforms ?? []
                          return {
                            ...current,
                            allowed_platforms: currentList.includes(platform.platform)
                              ? currentList.filter((item) => item !== platform.platform)
                              : [...currentList, platform.platform],
                          }
                        })}
                      >
                        {platform.label}
                      </Button>
                    )
                  })}
                </div>
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <div className="space-y-2">
                  <p className="eyebrow">Quiet hours</p>
                  <Input
                    placeholder="22:00-07:00 Africa/Nairobi"
                    value={settings.quiet_hours ?? ''}
                    onChange={(e) => setSettings((current) => ({ ...current, quiet_hours: e.target.value }))}
                  />
                </div>

                <div className="space-y-2">
                  <p className="eyebrow">Notifications</p>
                  <Input
                    placeholder="email,slack"
                    value={settings.notification_preferences ?? ''}
                    onChange={(e) => setSettings((current) => ({ ...current, notification_preferences: e.target.value }))}
                  />
                </div>
              </div>

              <div className="flex justify-end">
                <Button onClick={savePublishingDefaults} disabled={saving} className="rounded-xl">
                  {saving ? 'Saving defaults…' : 'Save defaults'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
