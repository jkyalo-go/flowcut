import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/router'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api, ApiError, surfaceApi } from '@/lib/api'
import { uploadFileToProject } from '@/lib/uploads'
import { useAuthStore } from '@/stores/authStore'
import type { Project } from '@/types'

function projectTimestamp(value?: string) {
  if (!value) return 'No recent activity'
  return new Date(value).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

export default function ProjectsPage() {
  const router = useRouter()
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const { workspace } = useAuthStore()
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [creating, setCreating] = useState(false)
  const [uploading, setUploading] = useState(false)

  async function loadProjects() {
    const data = await surfaceApi.listProjects()
    setProjects(data)
  }

  useEffect(() => {
    let mounted = true
    loadProjects()
      .catch((err) => {
        if (!mounted) return
        setError(err instanceof Error ? err.message : 'Failed to load projects')
      })
      .finally(() => {
        if (mounted) setLoading(false)
      })
    return () => { mounted = false }
  }, [])

  async function createProject() {
    if (!workspace || !name.trim()) return
    setCreating(true)
    setError(null)
    try {
      const created = await api.post<{ id: string }>('/api/projects', {
        name: name.trim(),
        workspace_id: workspace.id,
      })
      setName('')
      await loadProjects()
      await router.push(`/projects/${created.id}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to create project')
    } finally {
      setCreating(false)
    }
  }

  async function createProjectFromUpload(file: File) {
    if (!workspace) return
    setUploading(true)
    setError(null)
    try {
      const baseName = file.name.replace(/\.[^.]+$/, '').replace(/[-_]+/g, ' ').trim() || 'Untitled project'
      const created = await api.post<{ id: string }>('/api/projects', {
        name: baseName,
        workspace_id: workspace.id,
      })
      await uploadFileToProject({
        workspaceId: workspace.id,
        projectId: created.id,
        file,
      })
      await loadProjects()
      await router.push(`/projects/${created.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to upload footage')
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  return (
    <div className="space-y-6">
      <section className="app-panel p-6 md:p-8">
        <div className="grid gap-6 xl:grid-cols-[1fr_23rem]">
          <div>
            <p className="eyebrow">Projects</p>
            <h2 className="mt-3 font-display text-4xl tracking-tight text-foreground">Create, upload, and reopen work without jumping into a dead-end editor route.</h2>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-muted-foreground md:text-base">
              The project index now opens the promoted workspace path directly. New uploads can create a project and start processing in one move.
            </p>
          </div>

          <div className="app-panel-muted p-5">
            <p className="eyebrow">Quick start</p>
            <div className="mt-4 space-y-3">
              <Input
                placeholder="Project name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && createProject()}
              />
              <Button onClick={createProject} disabled={creating || !name.trim()} className="w-full rounded-xl">
                {creating ? 'Creating…' : 'Create project'}
              </Button>
              <Button variant="outline" onClick={() => fileInputRef.current?.click()} disabled={uploading} className="w-full rounded-xl">
                {uploading ? 'Uploading footage…' : 'Upload footage to new project'}
              </Button>
              <input
                ref={fileInputRef}
                type="file"
                accept="video/*"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0]
                  if (file) createProjectFromUpload(file)
                }}
              />
            </div>
          </div>
        </div>
      </section>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {loading ? (
        <div className="app-panel p-8">
          <p className="text-sm text-muted-foreground">Loading projects…</p>
        </div>
      ) : projects.length === 0 ? (
        <div className="app-panel p-8 text-center">
          <p className="font-display text-2xl tracking-tight text-foreground">No projects yet</p>
          <p className="mt-2 text-sm text-muted-foreground">
            Create a project or upload footage to start processing.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
          {projects.map((project) => (
            <button
              key={project.id}
              type="button"
              onClick={() => router.push(`/projects/${project.id}`)}
              className="app-panel text-left transition hover:-translate-y-0.5 hover:border-primary/30"
            >
              <div className="flex h-full flex-col gap-5 p-6">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="eyebrow">Project</p>
                    <h3 className="mt-3 font-display text-2xl tracking-tight text-foreground">{project.name}</h3>
                  </div>
                  <Badge variant={project.render_path ? 'default' : 'outline'}>
                    {project.render_path ? 'Rendered' : 'Active'}
                  </Badge>
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-2xl border border-border/70 bg-background/70 p-4">
                    <p className="eyebrow">Last activity</p>
                    <p className="mt-3 text-sm font-medium text-foreground">{projectTimestamp(project.created_at)}</p>
                  </div>
                  <div className="rounded-2xl border border-border/70 bg-background/70 p-4">
                    <p className="eyebrow">Automation</p>
                    <p className="mt-3 text-sm font-medium capitalize text-foreground">
                      {(project.autonomy_mode ?? 'supervised').replace(/_/g, ' ')}
                    </p>
                  </div>
                </div>

                <div className="mt-auto flex items-center justify-between text-sm text-muted-foreground">
                  <span>Open workspace</span>
                  <span aria-hidden="true">→</span>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
