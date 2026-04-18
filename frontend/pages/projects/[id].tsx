import { useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/router'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { DateTimePickerField } from '@/components/DateTimePickerField'
import { api, surfaceApi } from '@/lib/api'
import { uploadFileToProject } from '@/lib/uploads'
import { useAuthStore } from '@/stores/authStore'
import { useAutoSaveMetadata } from '@/hooks/useAutoSaveMetadata'
import { useWebSocket } from '@/hooks/useWebSocket'
import { AssetLibrary } from '@/components/AssetLibrary'
import { ClipList } from '@/components/ClipList'
import { RenderControls } from '@/components/RenderControls'
import { ThumbnailGenerator } from '@/components/ThumbnailGenerator'
import { Timeline } from '@/components/Timeline'
import { TitleSuggestions } from '@/components/TitleSuggestions'
import { VideoMetadata } from '@/components/VideoMetadata'
import { VideoPlayer } from '@/components/VideoPlayer'
import { useTimelineStore } from '@/stores/timelineStore'
import type { PlatformSurface, ProjectWorkspaceData } from '@/types'

function formatSlotDate(value?: string | null) {
  if (!value) return 'Pending'
  return new Date(value).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function saveLabel(status: 'idle' | 'saving' | 'saved' | 'error') {
  if (status === 'saving') return 'Saving metadata…'
  if (status === 'saved') return 'Metadata saved'
  if (status === 'error') return 'Save failed — changes not persisted'
  return 'Autosave idle'
}

export default function ProjectWorkspacePage() {
  const router = useRouter()
  const projectId = typeof router.query.id === 'string' ? router.query.id : null
  const uploadInputRef = useRef<HTMLInputElement | null>(null)
  const { workspace } = useAuthStore()

  const {
    setProject,
    setClips,
    setTimelineItems,
    setAssets,
    setMusicItems,
    setVolumeEnvelope,
    setTitleItems,
    setCaptionItems,
    setTimestampItems,
    setTrackerItems,
    setSubscribeItems,
    setSelectedTitle,
    setVideoDescription,
    setVideoTags,
    setVideoCategory,
    setVideoVisibility,
    setSelectedThumbnailIndices,
    setDescSystemPrompt,
    setThumbnailUrls,
    setThumbnailText,
    saveStatus,
    selectedTitle,
    videoDescription,
    videoTags,
    videoVisibility,
    selectedThumbnailIndices,
  } = useTimelineStore()

  const [workspaceData, setWorkspaceData] = useState<ProjectWorkspaceData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [publishPlatforms, setPublishPlatforms] = useState<string[]>([])
  const [scheduledAt, setScheduledAt] = useState('')
  const [publishing, setPublishing] = useState(false)
  const [publishError, setPublishError] = useState<string | null>(null)
  const [publishMessage, setPublishMessage] = useState<string | null>(null)

  useAutoSaveMetadata()
  useWebSocket(projectId)

  useEffect(() => {
    if (!projectId) return
    let mounted = true
    void (async () => {
      try {
        const data = await surfaceApi.getProjectWorkspace(projectId)
        if (!mounted) return
        setWorkspaceData(data)
        setLoading(false)
      } catch (err) {
        if (!mounted) return
        setError(err instanceof Error ? err.message : 'Failed to load project workspace')
        setLoading(false)
      }
    })()
    return () => { mounted = false }
  }, [projectId])

  async function refreshWorkspace() {
    if (!projectId) return
    const data = await surfaceApi.getProjectWorkspace(projectId)
    setWorkspaceData(data)
  }

  useEffect(() => {
    if (!workspaceData) return

    setProject(workspaceData.project)
    setClips(workspaceData.clips)
    setTimelineItems(workspaceData.timeline.items)
    setAssets(workspaceData.assets)
    setMusicItems(workspaceData.music.items)
    setVolumeEnvelope(workspaceData.music.volume_envelope)
    setTitleItems(workspaceData.overlays.titles)
    setCaptionItems(workspaceData.overlays.captions)
    setTimestampItems(workspaceData.overlays.timestamps)
    setTrackerItems(workspaceData.overlays.trackers)
    setSubscribeItems(workspaceData.overlays.subscribes)
    setSelectedTitle(workspaceData.project.selected_title ?? null)
    setVideoDescription(workspaceData.project.video_description ?? '')
    setVideoTags(Array.isArray(workspaceData.project.video_tags) ? workspaceData.project.video_tags : [])
    setVideoCategory(workspaceData.project.video_category ?? '22')
    setVideoVisibility(workspaceData.project.video_visibility ?? 'private')
    setSelectedThumbnailIndices(
      Array.isArray(workspaceData.project.locked_thumbnail_indices) && workspaceData.project.locked_thumbnail_indices.length > 0
        ? workspaceData.project.locked_thumbnail_indices
        : workspaceData.project.selected_thumbnail_idx != null
          ? [workspaceData.project.selected_thumbnail_idx]
          : [],
    )
    setDescSystemPrompt(workspaceData.project.desc_system_prompt ?? '')
    setThumbnailUrls(Array.isArray(workspaceData.project.thumbnail_urls) ? workspaceData.project.thumbnail_urls : [])
    setThumbnailText(workspaceData.project.thumbnail_text ?? '')
    setPublishPlatforms((current) => {
      const ready = workspaceData.publish.platforms.filter((platform) => platform.ready).map((platform) => platform.platform)
      return current.length > 0 ? current.filter((platform) => ready.includes(platform)) : ready.slice(0, 1)
    })
  }, [
    workspaceData,
    setAssets,
    setCaptionItems,
    setClips,
    setDescSystemPrompt,
    setMusicItems,
    setProject,
    setSelectedThumbnailIndices,
    setSelectedTitle,
    setSubscribeItems,
    setThumbnailText,
    setThumbnailUrls,
    setTimelineItems,
    setTimestampItems,
    setTitleItems,
    setTrackerItems,
    setVideoCategory,
    setVideoDescription,
    setVideoTags,
    setVideoVisibility,
    setVolumeEnvelope,
  ])

  async function handleUpload(files: FileList | null) {
    if (!files || !workspace || !projectId) return
    setUploading(true)
    setError(null)
    try {
      for (const file of Array.from(files)) {
        await uploadFileToProject({
          workspaceId: workspace.id,
          projectId,
          file,
        })
      }
      await refreshWorkspace()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to upload footage')
    } finally {
      setUploading(false)
      if (uploadInputRef.current) uploadInputRef.current.value = ''
    }
  }

  async function publishProject() {
    if (!projectId || publishPlatforms.length === 0) {
      setPublishError('Select at least one ready platform')
      return
    }
    setPublishing(true)
    setPublishError(null)
    setPublishMessage(null)
    try {
      const response = await api.post<{ scheduled_slots: number }>('/api/platforms/projects/' + projectId + '/publish', {
        title: selectedTitle ?? workspaceData?.project.name ?? 'Untitled project',
        description: videoDescription,
        tags: videoTags,
        privacy_status: videoVisibility,
        thumbnail_index: selectedThumbnailIndices[0] ?? null,
        platforms: publishPlatforms,
        render_variants: ['default'],
        scheduled_at: scheduledAt ? new Date(scheduledAt).toISOString() : undefined,
      })
      setPublishMessage(`${response.scheduled_slots} publish slot${response.scheduled_slots === 1 ? '' : 's'} created`)
      await refreshWorkspace()
    } catch (err) {
      setPublishError(err instanceof Error ? err.message : 'Failed to schedule publish')
    } finally {
      setPublishing(false)
    }
  }

  const readyPlatforms = useMemo(
    () => workspaceData?.publish.platforms.filter((platform) => platform.connected) ?? [],
    [workspaceData],
  )

  if (loading) {
    return (
      <div className="app-panel p-8">
        <p className="text-sm text-muted-foreground">Loading project workspace…</p>
      </div>
    )
  }

  if (!workspaceData) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{error ?? 'Project workspace unavailable'}</AlertDescription>
      </Alert>
    )
  }

  return (
    <div className="space-y-6">
      <section className="app-panel p-6 md:p-8">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="eyebrow">Project workspace</p>
            <h2 className="mt-3 font-display text-4xl tracking-tight text-foreground">{workspaceData.project.name}</h2>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-muted-foreground">
              This route is now the canonical workspace for editing, metadata, export, and publishing. The old query-string editor path is treated as a compatibility redirect only.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Button variant="outline" onClick={() => uploadInputRef.current?.click()} disabled={uploading} className="rounded-xl">
              {uploading ? 'Uploading footage…' : 'Upload footage'}
            </Button>
            <Button asChild variant="outline" className="rounded-xl">
              <Link href="/projects">All projects</Link>
            </Button>
          </div>
          <input
            ref={uploadInputRef}
            type="file"
            accept="video/*"
            multiple
            className="hidden"
            onChange={(e) => handleUpload(e.target.files)}
          />
        </div>
      </section>

      {(error || publishError || publishMessage) && (
        <div className="space-y-3">
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          {publishError && (
            <Alert variant="destructive">
              <AlertDescription>{publishError}</AlertDescription>
            </Alert>
          )}
          {publishMessage && (
            <Alert>
              <AlertDescription>{publishMessage}</AlertDescription>
            </Alert>
          )}
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[18rem_minmax(0,1fr)_22rem]">
        <aside className="space-y-5">
          <div className="app-panel p-5">
            <p className="eyebrow">Intake</p>
            <h3 className="mt-3 text-2xl text-foreground">Clip rail</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Add source footage here. Processing updates stream back into the workspace over the authenticated websocket connection.
            </p>
          </div>

          <div className="app-panel p-4 legacy-editor-surface">
            <ClipList />
          </div>

          <div className="legacy-editor-surface">
            <AssetLibrary />
          </div>
        </aside>

        <section className="space-y-5">
          <div className="legacy-editor-surface">
            <VideoPlayer />
          </div>
          <div className="app-panel p-4 legacy-editor-surface">
            <Timeline />
          </div>
        </section>

        <aside className="space-y-5">
          <div className="app-panel p-5">
            <div className="legacy-editor-surface">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="eyebrow">Inspector</p>
                  <h3 className="mt-3 text-2xl text-foreground">Metadata and creative variants</h3>
                </div>
                <span className={`save-indicator ${saveStatus}`}>
                  {saveLabel(saveStatus)}
                </span>
              </div>
              <TitleSuggestions />
              <ThumbnailGenerator />
              <VideoMetadata />
            </div>
          </div>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Publish planner</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Ready platforms</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {readyPlatforms.length === 0 ? (
                    <p className="text-sm text-muted-foreground">Connect a platform in integrations before scheduling publish.</p>
                  ) : readyPlatforms.map((platform: PlatformSurface) => {
                    const selected = publishPlatforms.includes(platform.platform)
                    return (
                      <Button
                        key={platform.platform}
                        type="button"
                        variant={selected ? 'default' : 'outline'}
                        size="sm"
                        className="rounded-xl"
                        onClick={() => setPublishPlatforms((current) =>
                          current.includes(platform.platform)
                            ? current.filter((item) => item !== platform.platform)
                            : [...current, platform.platform]
                        )}
                      >
                        {platform.label}
                      </Button>
                    )
                  })}
                </div>
              </div>

              <div className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Schedule time</p>
                <DateTimePickerField
                  value={scheduledAt}
                  onChange={setScheduledAt}
                  placeholder="Pick a publish date"
                />
                <p className="text-xs text-muted-foreground">Leave blank to execute immediately and enqueue publish jobs now.</p>
              </div>

              <Button onClick={publishProject} disabled={publishing || readyPlatforms.length === 0} className="w-full rounded-xl">
                {publishing ? 'Scheduling publish…' : scheduledAt ? 'Schedule publish' : 'Publish now'}
              </Button>

              <div className="space-y-3">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Recent slots</p>
                {workspaceData.publish.recent_slots.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No publish jobs created for this project yet.</p>
                ) : workspaceData.publish.recent_slots.slice(0, 4).map((slot) => (
                  <div key={slot.id} className="rounded-2xl border border-border/70 bg-background/70 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-medium text-foreground">{slot.title ?? slot.platform}</p>
                      <Badge variant={slot.status === 'published' ? 'default' : slot.status === 'failed' ? 'destructive' : 'secondary'}>
                        {slot.status}
                      </Badge>
                    </div>
                    <p className="mt-2 text-xs text-muted-foreground">{formatSlotDate(slot.scheduled_at)}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <RenderControls />
        </aside>
      </div>
    </div>
  )
}
