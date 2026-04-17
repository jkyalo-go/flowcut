import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { api } from '@/lib/api'
import type { AIProviderConfig, AICredential } from '@/types'

interface UsageRow {
  task_type: string
  provider: string
  total_cost: number
  count: number
}

const BYOK_PROVIDERS = ['anthropic', 'openai', 'vertex', 'deepgram', 'dashscope']

export function AISettingsPage() {
  const [providers, setProviders] = useState<AIProviderConfig[]>([])
  const [credentials, setCredentials] = useState<AICredential[]>([])
  const [usage, setUsage] = useState<UsageRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // BYOK form state
  const [newProvider, setNewProvider] = useState('anthropic')
  const [newApiKey, setNewApiKey] = useState('')
  const [addingKey, setAddingKey] = useState(false)
  const [byokError, setByokError] = useState('')

  useEffect(() => {
    let mounted = true
    Promise.all([
      api.get<AIProviderConfig[]>('/api/ai/admin/providers').catch(() => [] as AIProviderConfig[]),
      api.get<AICredential[]>('/api/ai/credentials').catch(() => [] as AICredential[]),
      api.get<UsageRow[]>('/api/ai/usage').catch(() => [] as UsageRow[]),
    ]).then(([providerData, credData, usageData]) => {
      if (mounted) {
        setProviders(providerData)
        setCredentials(credData)
        setUsage(usageData)
        setLoading(false)
      }
    })
    return () => { mounted = false }
  }, [])

  async function toggleConfig(config: AIProviderConfig) {
    setError('')
    try {
      const updated = await api.put<AIProviderConfig>(
        `/api/ai/admin/providers/${config.id}`,
        { ...config, enabled: !config.enabled }
      )
      setProviders((prev) =>
        prev.map((p) => (p.id === config.id ? updated : p))
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update provider config')
    }
  }

  async function addCredential() {
    setByokError('')
    if (!newApiKey.trim()) {
      setByokError('API key is required')
      return
    }
    setAddingKey(true)
    try {
      const cred = await api.post<AICredential>('/api/ai/credentials', {
        provider: newProvider,
        api_key: newApiKey,
        allowed_models: [],
      })
      setCredentials((prev) => [...prev, cred])
      setNewApiKey('')
    } catch (err) {
      setByokError(err instanceof Error ? err.message : 'Failed to add credential')
    } finally {
      setAddingKey(false)
    }
  }

  async function removeCredential(id: string) {
    try {
      await api.delete(`/api/ai/credentials/${id}`)
      setCredentials((prev) => prev.filter((c) => c.id !== id))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to remove credential')
    }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">AI Settings</h1>
        <p className="text-sm text-muted-foreground">
          Manage AI providers, API keys, and usage.
        </p>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading...</p>
      ) : (
        <Tabs defaultValue="providers">
          <TabsList>
            <TabsTrigger value="providers">Providers</TabsTrigger>
            <TabsTrigger value="byok">Your API keys</TabsTrigger>
            <TabsTrigger value="usage">Usage</TabsTrigger>
          </TabsList>

          {/* Providers Tab */}
          <TabsContent value="providers">
            <Card>
              <CardHeader>
                <CardTitle>Provider configurations</CardTitle>
              </CardHeader>
              <CardContent>
                {providers.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No providers configured.</p>
                ) : (
                  <div className="divide-y">
                    {providers.map((config) => (
                      <div key={config.id} className="flex items-start justify-between py-4">
                        <div className="space-y-1">
                          <p className="text-sm font-medium">{config.display_name}</p>
                          <p className="text-xs text-muted-foreground">
                            {config.provider} / {config.model_key}
                          </p>
                          <div className="flex flex-wrap gap-1 mt-1">
                            {config.task_types.map((t) => (
                              <Badge key={t} variant="secondary" className="text-xs">
                                {t}
                              </Badge>
                            ))}
                          </div>
                        </div>
                        <div className="flex items-center gap-3 ml-4">
                          <Badge variant={config.enabled ? 'default' : 'outline'}>
                            {config.enabled ? 'Enabled' : 'Disabled'}
                          </Badge>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => toggleConfig(config)}
                          >
                            {config.enabled ? 'Disable' : 'Enable'}
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* BYOK Tab */}
          <TabsContent value="byok">
            <div className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Add API key</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {byokError && (
                    <Alert variant="destructive">
                      <AlertDescription>{byokError}</AlertDescription>
                    </Alert>
                  )}
                  <div className="space-y-2">
                    <Label htmlFor="provider-select">Provider</Label>
                    <Select value={newProvider} onValueChange={setNewProvider}>
                      <SelectTrigger id="provider-select">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {BYOK_PROVIDERS.map((p) => (
                          <SelectItem key={p} value={p}>
                            {p}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="api-key-input">API key</Label>
                    <Input
                      id="api-key-input"
                      type="password"
                      placeholder="Paste API key here"
                      value={newApiKey}
                      onChange={(e) => setNewApiKey(e.target.value)}
                    />
                  </div>
                  <Button onClick={addCredential} disabled={addingKey}>
                    {addingKey ? 'Adding...' : 'Add key'}
                  </Button>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Stored keys</CardTitle>
                </CardHeader>
                <CardContent>
                  {credentials.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No API keys stored.</p>
                  ) : (
                    <div className="divide-y">
                      {credentials.map((cred) => (
                        <div key={cred.id} className="flex items-center justify-between py-3">
                          <div className="space-y-0.5">
                            <p className="text-sm font-medium">{cred.provider}</p>
                            {cred.created_at && (
                              <p className="text-xs text-muted-foreground">
                                Added {new Date(cred.created_at).toLocaleDateString()}
                              </p>
                            )}
                          </div>
                          <div className="flex items-center gap-3">
                            <Badge variant={cred.is_active ? 'default' : 'secondary'}>
                              {cred.is_active ? 'Active' : 'Inactive'}
                            </Badge>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => removeCredential(cred.id)}
                            >
                              Remove
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Usage Tab */}
          <TabsContent value="usage">
            <Card>
              <CardHeader>
                <CardTitle>AI usage</CardTitle>
              </CardHeader>
              <CardContent>
                {usage.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No usage data available.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b text-left">
                          <th className="pb-2 font-medium">Task type</th>
                          <th className="pb-2 font-medium">Provider</th>
                          <th className="pb-2 font-medium text-right">Count</th>
                          <th className="pb-2 font-medium text-right">Total cost</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {usage.map((row) => (
                          <tr key={`${row.task_type}-${row.provider}`}>
                            <td className="py-2">{row.task_type}</td>
                            <td className="py-2 text-muted-foreground">{row.provider}</td>
                            <td className="py-2 text-right">{row.count}</td>
                            <td className="py-2 text-right font-mono">
                              ${row.total_cost.toFixed(3)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      )}
    </div>
  )
}
