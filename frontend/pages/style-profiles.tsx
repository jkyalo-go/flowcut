import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { api, ApiError } from '@/lib/api'
import type { StyleProfile } from '@/types'

const DIMENSIONS = ['pacing', 'cut_density', 'music_energy', 'text_density', 'transition_style']

function parseLocks(p: StyleProfile): Record<string, boolean> {
  if (typeof p.dimension_locks === 'string') {
    try {
      return JSON.parse(p.dimension_locks)
    } catch {
      return {}
    }
  } else if (p.dimension_locks && typeof p.dimension_locks === 'object') {
    return p.dimension_locks
  }
  return {}
}

function parseScores(p: StyleProfile): Record<string, number> {
  if (typeof p.confidence_scores === 'string') {
    try {
      return JSON.parse(p.confidence_scores)
    } catch {
      return {}
    }
  } else if (p.confidence_scores && typeof p.confidence_scores === 'object') {
    return p.confidence_scores
  }
  return {}
}

export default function StyleProfilesPage() {
  const [genres, setGenres] = useState<string[]>([])
  const [profiles, setProfiles] = useState<StyleProfile[]>([])
  const [selected, setSelected] = useState<StyleProfile | null>(null)
  const [newName, setNewName] = useState('')
  const [newGenre, setNewGenre] = useState('')
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lockSaved, setLockSaved] = useState(false)
  const lockSavedTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => () => { if (lockSavedTimerRef.current) clearTimeout(lockSavedTimerRef.current) }, [])

  useEffect(() => {
    let mounted = true
    Promise.all([
      api.get<{ genres: string[] } | string[]>('/api/style-profiles/genres'),
      api.get<{ profiles: StyleProfile[] } | StyleProfile[]>('/api/style-profiles'),
    ])
      .then(([g, p]) => {
        if (!mounted) return
        setGenres(Array.isArray(g) ? g : (g as { genres: string[] }).genres ?? [])
        setProfiles(Array.isArray(p) ? p : (p as { profiles: StyleProfile[] }).profiles ?? [])
      })
      .catch((err: unknown) => {
        if (!mounted) return
        setError(err instanceof ApiError ? err.message : 'Failed to load')
      })
    return () => { mounted = false }
  }, [])

  async function createProfile() {
    if (!newName.trim() || !newGenre) return
    setCreating(true)
    setError(null)
    try {
      const created = await api.post<StyleProfile>('/api/style-profiles', {
        name: newName.trim(),
        genre: newGenre,
      })
      setProfiles(prev => [...prev, created])
      setNewName('')
      setNewGenre('')
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : 'Failed to create profile')
    } finally {
      setCreating(false)
    }
  }

  async function openProfile(id: string) {
    try {
      const profile = await api.get<StyleProfile>(`/api/style-profiles/${id}`)
      setSelected(profile)
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : 'Failed to load profile')
    }
  }

  async function toggleLock(dim: string) {
    if (!selected) return
    const currentLocks = parseLocks(selected)
    const updatedLocks = { ...currentLocks, [dim]: !currentLocks[dim] }
    try {
      const updated = await api.put<StyleProfile>(`/api/style-profiles/${selected.id}/locks`, {
        locks: updatedLocks,
      })
      setSelected(updated)
      setProfiles(prev => prev.map(p => p.id === updated.id ? updated : p))
      if (lockSavedTimerRef.current) clearTimeout(lockSavedTimerRef.current)
      setLockSaved(true)
      lockSavedTimerRef.current = setTimeout(() => setLockSaved(false), 2000)
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : 'Failed to update locks')
    }
  }

  async function rollback() {
    if (!selected || selected.version <= 1) return
    try {
      const updated = await api.post<StyleProfile>(`/api/style-profiles/${selected.id}/rollback`, {
        target_version: selected.version - 1,
      })
      setSelected(updated)
      setProfiles(prev => prev.map(p => p.id === updated.id ? updated : p))
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : 'Failed to rollback')
    }
  }

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <h1 className="text-3xl font-bold">Style Profiles</h1>

      <Card>
        <CardHeader>
          <CardTitle>New profile</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <div className="flex gap-3 items-end flex-wrap">
            <div className="flex-1 min-w-48 space-y-1">
              <Label htmlFor="profile-name">Name</Label>
              <Input
                id="profile-name"
                placeholder="Profile name"
                value={newName}
                onChange={e => setNewName(e.target.value)}
              />
            </div>
            <div className="flex-1 min-w-40 space-y-1">
              <Label htmlFor="profile-genre">Genre</Label>
              <Select value={newGenre} onValueChange={setNewGenre}>
                <SelectTrigger id="profile-genre">
                  <SelectValue placeholder="Select genre" />
                </SelectTrigger>
                <SelectContent>
                  {genres.map(g => (
                    <SelectItem key={g} value={g}>{g}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button
              onClick={createProfile}
              disabled={creating || !newName.trim() || !newGenre}
            >
              {creating ? 'Creating...' : 'Create'}
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="space-y-3">
          {profiles.map(profile => (
            <Card key={profile.id} className="hover:shadow-md transition-shadow">
              <CardContent className="pt-4 pb-4">
                <button
                  type="button"
                  className="flex w-full items-center justify-between text-left"
                  onClick={() => openProfile(profile.id)}
                >
                  <div>
                    <p className="font-semibold">{profile.name}</p>
                    <p className="text-sm text-muted-foreground">
                      {profile.genre} · v{profile.version}
                    </p>
                  </div>
                  <Badge variant="secondary">{profile.genre}</Badge>
                </button>
              </CardContent>
            </Card>
          ))}
          {profiles.length === 0 && (
            <p className="text-muted-foreground text-sm">No profiles yet. Create one above.</p>
          )}
        </div>

        <div>
          {selected ? (
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle>{selected.name}</CardTitle>
                <div className="flex items-center gap-2">
                  {lockSaved && (
                    <span className="text-xs text-green-600">Saved</span>
                  )}
                  {selected.version > 1 && (
                    <Button variant="outline" size="sm" onClick={rollback}>
                      Rollback to v{selected.version - 1}
                    </Button>
                  )}
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                {DIMENSIONS.map(dim => {
                  const locks = parseLocks(selected)
                  const scores = parseScores(selected)
                  const isLocked = !!locks[dim]
                  const score = scores[dim] ?? 0
                  const badgeVariant = score > 0.7 ? 'default' : 'secondary'
                  return (
                    <div key={dim} className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => toggleLock(dim)}
                          className="text-lg hover:opacity-70 transition-opacity"
                          aria-label={isLocked ? `Unlock ${dim}` : `Lock ${dim}`}
                        >
                          {isLocked ? '🔒' : '🔓'}
                        </button>
                        <span className="text-sm capitalize">{dim.replace(/_/g, ' ')}</span>
                      </div>
                      <Badge variant={badgeVariant}>
                        {Math.round(score * 100)}%
                      </Badge>
                    </div>
                  )
                })}
              </CardContent>
            </Card>
          ) : (
            <div className="flex items-center justify-center h-40 text-muted-foreground text-sm border rounded-lg">
              Select a profile to view details
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
