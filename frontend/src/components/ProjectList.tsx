// frontend/src/components/ProjectList.tsx
import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { api, ApiError } from '@/lib/api'
import { useAuthStore } from '@/stores/authStore'
import { useTimelineStore } from '@/stores/timelineStore'
import type { Project, Clip, TimelineItem } from '@/types'

export function ProjectList() {
  const { workspace } = useAuthStore()
  const { setProject, setClips, setTimelineItems, uploadProgress } = useTimelineStore()
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [error, setError] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadPct, setUploadPct] = useState(0)
  const [dragging, setDragging] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    let mounted = true
    api.get<Project[]>('/api/projects')
      .then(data => { if (mounted) setProjects(data) })
      .catch(() => { if (mounted) setError('Failed to load projects') })
      .finally(() => { if (mounted) setLoading(false) })
    return () => { mounted = false }
  }, [])

  async function createProject() {
    if (!name.trim() || !workspace) return
    setCreating(true)
    setError('')
    try {
      const proj = await api.post<Project>('/api/projects', {
        name: name.trim(),
        workspace_id: workspace.id,
      })
      setProjects(prev => [proj, ...prev])
      setName('')
      setShowForm(false)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Failed to create project')
    } finally {
      setCreating(false)
    }
  }

  async function deleteProject(e: React.MouseEvent, id: string, pName: string) {
    e.stopPropagation()
    if (!confirm(`Delete "${pName}"?`)) return
    try {
      await api.delete(`/api/projects/${id}`)
      setProjects(prev => prev.filter(p => p.id !== id))
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Failed to delete project')
    }
  }

  async function openProject(id: string) {
    setError('')
    try {
      const [proj, clips, timeline] = await Promise.all([
        api.get<Project>(`/api/projects/${id}`),
        api.get<Clip[]>(`/api/clips?project_id=${id}`),
        api.get<{ items?: TimelineItem[] }>(`/api/timeline/${id}`),
      ])
      setProject(proj)
      setClips(clips)
      setTimelineItems(timeline?.items ?? [])
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Failed to open project')
    }
  }

  async function handleUpload(file: File) {
    if (!workspace) return
    setUploading(true)
    setUploadPct(0)
    setError('')
    try {
      const session = await api.post<{ id: string; storage_path: string }>(
        '/api/uploads/sessions',
        { workspace_id: workspace.id, filename: file.name, total_size: file.size, media_type: file.type }
      )
      await fetch(`/api/uploads/sessions/${session.id}`, {
        method: 'PUT',
        credentials: 'include',
        body: file,
      })
      setUploadPct(80)
      await api.post(`/api/uploads/sessions/${session.id}/complete`, {})
      setUploadPct(100)
      const updated = await api.get<Project[]>('/api/projects')
      setProjects(updated)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Upload failed')
    } finally {
      setUploading(false)
      setUploadPct(0)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  if (loading) {
    return <div className="flex h-full items-center justify-center text-sm text-muted-foreground">Loading projects...</div>
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold">Projects</h1>
        <Button onClick={() => setShowForm(v => !v)}>New project</Button>
      </div>

      {error && (
        <Alert variant="destructive" className="mb-4">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* WebSocket upload progress from timelineStore */}
      {uploadProgress && Object.entries(uploadProgress).map(([sessionId, { stage, pct }]) => (
        <div key={sessionId} className="flex items-center gap-3 py-2 px-3 bg-muted rounded text-sm mb-4">
          <div className="flex-1">
            <div className="flex justify-between mb-1">
              <span className="text-xs text-muted-foreground">{stage}</span>
              <span className="text-xs">{Math.round(pct)}%</span>
            </div>
            <div className="h-1.5 bg-muted-foreground/20 rounded overflow-hidden">
              <div className="h-full bg-primary transition-all" style={{ width: `${pct}%` }} />
            </div>
          </div>
        </div>
      ))}

      {showForm && (
        <Card className="mb-6">
          <CardContent className="pt-4 flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <Label htmlFor="proj-name">Project name</Label>
              <Input
                id="proj-name"
                value={name}
                onChange={e => setName(e.target.value)}
                placeholder="My awesome video"
                onKeyDown={e => e.key === 'Enter' && createProject()}
              />
            </div>
            <div className="flex gap-2">
              <Button onClick={createProject} disabled={creating || !name.trim()}>
                {creating ? 'Creating...' : 'Create'}
              </Button>
              <Button variant="ghost" onClick={() => setShowForm(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Drag and drop upload zone */}
      <div
        className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors mb-6 ${
          dragging ? 'border-primary bg-primary/5' : 'border-muted-foreground/25'
        }`}
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDragEnd={() => setDragging(false)}
        onDrop={e => {
          e.preventDefault()
          setDragging(false)
          const file = e.dataTransfer.files[0]
          if (file) handleUpload(file)
        }}
      >
        {uploading ? (
          <div className="text-sm text-muted-foreground">
            <p className="mb-2">Uploading... {uploadPct}%</p>
            <div className="h-1.5 bg-muted-foreground/20 rounded overflow-hidden max-w-xs mx-auto">
              <div className="h-full bg-primary transition-all" style={{ width: `${uploadPct}%` }} />
            </div>
          </div>
        ) : (
          <>
            <p className="text-sm text-muted-foreground mb-2">Drag & drop a video here, or</p>
            <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()} disabled={uploading}>
              Browse files
            </Button>
          </>
        )}
        <input
          ref={fileRef}
          type="file"
          accept="video/*"
          className="hidden"
          onChange={e => { if (e.target.files?.[0]) handleUpload(e.target.files[0]) }}
        />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {projects.map(p => (
          <Card
            key={p.id}
            className="cursor-pointer hover:border-primary transition-colors"
            onClick={() => openProject(p.id)}
          >
            <CardHeader className="pb-2">
              <div className="flex items-start justify-between gap-2">
                <CardTitle className="text-base truncate">{p.name}</CardTitle>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 w-6 p-0 shrink-0 text-muted-foreground hover:text-destructive"
                  onClick={e => deleteProject(e, p.id, p.name)}
                >
                  ×
                </Button>
              </div>
            </CardHeader>
            <CardContent className="pt-0">
              {p.status && <Badge variant="outline" className="text-xs">{p.status}</Badge>}
            </CardContent>
          </Card>
        ))}

        {projects.length === 0 && !showForm && (
          <div className="col-span-full text-center py-12 text-muted-foreground text-sm">
            No projects yet. Upload a video or create a new project.
          </div>
        )}
      </div>
    </div>
  )
}
