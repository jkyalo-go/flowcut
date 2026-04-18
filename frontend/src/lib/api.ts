import type {
  AICredentialSurface,
  AIProviderSurface,
  AIUsageSurface,
  Asset,
  AutonomySettings,
  CalendarSlotSurface,
  Clip,
  GapSlot,
  InvitationPreview,
  OverviewData,
  PlatformSurface,
  Project,
  ProjectWorkspaceData,
  QuotaSurface,
  ReviewQueueSurface,
  StyleProfile,
  SubscriptionPlan,
  TimelineItem,
  WorkspaceMemberSurface,
  WorkspaceSubscription,
} from '@/types'

const TOKEN_KEY = 'flowcut_token'

export function getStoredToken(): string | null {
  return null
}

export function storeToken(token: string): void {
  void token
}

export function clearStoredToken(): void {
  void TOKEN_KEY
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

function newRequestId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `rid-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

function readCookie(name: string): string | null {
  if (typeof document === 'undefined') return null
  const match = document.cookie.match(new RegExp('(?:^|; )' + name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '=([^;]*)'))
  return match ? decodeURIComponent(match[1]) : null
}

let unauthorizedHandler: (() => void) | null = null

export function setUnauthorizedHandler(fn: (() => void) | null): void {
  unauthorizedHandler = fn
}

function parseJson<T>(value: unknown, fallback: T): T {
  if (value == null) return fallback
  if (Array.isArray(fallback)) {
    if (Array.isArray(value)) return value as T
  } else if (typeof fallback === 'object' && fallback !== null) {
    if (typeof value === 'object' && !Array.isArray(value)) return value as T
  }
  if (typeof value !== 'string') return fallback
  try {
    return JSON.parse(value) as T
  } catch {
    return fallback
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const contentTypeHeaders: HeadersInit = init.body instanceof FormData
    ? {}
    : { 'Content-Type': 'application/json' }
  const method = (init.method ?? 'GET').toUpperCase()
  const csrfHeaders: Record<string, string> = {}
  if (method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS') {
    const csrf = readCookie('flowcut_csrf')
    if (csrf) csrfHeaders['X-CSRF-Token'] = csrf
  }
  const res = await fetch(path, {
    ...init,
    credentials: 'include',
    headers: {
      ...contentTypeHeaders,
      'X-Request-ID': newRequestId(),
      ...csrfHeaders,
      ...(init.headers ?? {}),
    },
  })
  if (!res.ok) {
    let message = `HTTP ${res.status}`
    try {
      const data = await res.json()
      message = data.detail ?? data.message ?? message
    } catch {
      void 0
    }
    if (res.status === 401 && unauthorizedHandler) {
      try { unauthorizedHandler() } catch { void 0 }
    }
    throw new ApiError(res.status, message)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: 'GET' }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body !== undefined ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PUT', body: body !== undefined ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
  postForm: <T>(path: string, form: FormData) =>
    request<T>(path, { method: 'POST', body: form }),
}

function adaptProject(raw: Record<string, unknown>): Project {
  return {
    id: String(raw.id),
    name: String(raw.name ?? 'Untitled project'),
    workspace_id: String(raw.workspace_id ?? ''),
    created_at: typeof raw.created_at === 'string' ? raw.created_at : undefined,
    render_path: typeof raw.render_path === 'string' ? raw.render_path : null,
    autonomy_mode: typeof raw.autonomy_mode === 'string' ? raw.autonomy_mode : null,
    selected_title: typeof raw.selected_title === 'string' ? raw.selected_title : null,
    video_description: typeof raw.video_description === 'string' ? raw.video_description : null,
    video_tags: parseJson<string[]>(raw.video_tags, []),
    video_category: typeof raw.video_category === 'string' ? raw.video_category : '22',
    video_visibility: typeof raw.video_visibility === 'string' ? raw.video_visibility : 'private',
    selected_thumbnail_idx: typeof raw.selected_thumbnail_idx === 'number' ? raw.selected_thumbnail_idx : null,
    desc_system_prompt: typeof raw.desc_system_prompt === 'string' ? raw.desc_system_prompt : '',
    thumbnail_urls: parseJson<string[]>(raw.thumbnail_urls, []),
    locked_thumbnail_indices: parseJson<number[]>(raw.locked_thumbnail_indices, []),
    thumbnail_text: typeof raw.thumbnail_text === 'string' ? raw.thumbnail_text : '',
  }
}

function adaptClip(raw: Record<string, unknown>): Clip {
  return {
    id: String(raw.id),
    workspace_id: typeof raw.workspace_id === 'string' ? raw.workspace_id : undefined,
    project_id: typeof raw.project_id === 'string' ? raw.project_id : undefined,
    source_path: String(raw.source_path ?? ''),
    processed_path: typeof raw.processed_path === 'string' ? raw.processed_path : null,
    clip_type: (raw.clip_type as Clip['clip_type']) ?? null,
    status: (raw.status as Clip['status']) ?? 'pending',
    review_status: typeof raw.review_status === 'string' ? raw.review_status : null,
    confidence_score: typeof raw.confidence_score === 'number' ? raw.confidence_score : null,
    duration: typeof raw.duration === 'number' ? raw.duration : null,
    transcript: typeof raw.transcript === 'string' ? raw.transcript : null,
    error_message: typeof raw.error_message === 'string' ? raw.error_message : null,
    sub_clips: Array.isArray(raw.sub_clips)
      ? raw.sub_clips.map((sub) => ({
          id: String((sub as Record<string, unknown>).id),
          start_time: Number((sub as Record<string, unknown>).start_time ?? 0),
          end_time: Number((sub as Record<string, unknown>).end_time ?? 0),
          score: typeof (sub as Record<string, unknown>).score === 'number' ? Number((sub as Record<string, unknown>).score) : null,
          label: typeof (sub as Record<string, unknown>).label === 'string' ? String((sub as Record<string, unknown>).label) : null,
        }))
      : [],
    progress: typeof raw.progress === 'number' ? raw.progress : null,
    progressDetail: typeof raw.progressDetail === 'string' ? raw.progressDetail : null,
  }
}

function adaptTimelineItem(raw: Record<string, unknown>): TimelineItem {
  return {
    id: String(raw.id),
    clip_id: raw.clip_id == null ? null : String(raw.clip_id),
    sub_clip_id: raw.sub_clip_id == null ? null : String(raw.sub_clip_id),
    position: Number(raw.position ?? 0),
    video_url: String(raw.video_url ?? ''),
    duration: Number(raw.duration ?? 0),
    start_time: Number(raw.start_time ?? 0),
    end_time: Number(raw.end_time ?? 0),
    label: String(raw.label ?? ''),
    clip_type: typeof raw.clip_type === 'string' ? raw.clip_type : null,
  }
}

function adaptAsset(raw: Record<string, unknown>): Asset {
  return {
    id: String(raw.id),
    name: String(raw.name ?? ''),
    file_path: String(raw.file_path ?? ''),
    asset_type: (raw.asset_type as Asset['asset_type']) ?? 'music',
    duration: Number(raw.duration ?? 0),
  }
}

function adaptCalendarSlot(raw: Record<string, unknown>): CalendarSlotSurface {
  const metadata = parseJson<Record<string, unknown>>(raw.metadata ?? raw.metadata_json, {})
  const title = typeof metadata.title === 'string'
    ? metadata.title
    : (typeof raw.title === 'string' ? raw.title : undefined)
  return {
    id: String(raw.id),
    platform: String(raw.platform ?? ''),
    project_id: raw.project_id == null ? null : String(raw.project_id),
    clip_id: raw.clip_id == null ? null : String(raw.clip_id),
    render_variant: raw.render_variant == null ? null : String(raw.render_variant),
    scheduled_at: String(raw.scheduled_at ?? ''),
    status: String(raw.status ?? 'scheduled'),
    publish_url: typeof raw.publish_url === 'string' ? raw.publish_url : null,
    failure_reason: typeof raw.failure_reason === 'string' ? raw.failure_reason : null,
    retry_count: typeof raw.retry_count === 'number' ? raw.retry_count : 0,
    correlation_id: typeof raw.correlation_id === 'string' ? raw.correlation_id : null,
    metadata,
    title,
  }
}

function adaptPlatform(raw: Record<string, unknown>): PlatformSurface {
  return {
    id: typeof raw.id === 'string'
      ? raw.id
      : raw.connection && typeof raw.connection === 'object' && typeof (raw.connection as Record<string, unknown>).id === 'string'
        ? String((raw.connection as Record<string, unknown>).id)
        : undefined,
    platform: String(raw.platform ?? ''),
    label: String(raw.label ?? raw.platform ?? ''),
    connected: Boolean(raw.connected),
    ready: Boolean(raw.ready),
    status: String(raw.status ?? 'not_connected'),
    display_name: String(raw.display_name ?? raw.label ?? raw.platform ?? ''),
    scopes: Array.isArray(raw.scopes) ? raw.scopes.map(String) : [],
    auth_mode: String(raw.auth_mode ?? 'oauth'),
    supports_thumbnail: Boolean(raw.supports_thumbnail),
    supports_scheduling: Boolean(raw.supports_scheduling),
    aspect_ratios: Array.isArray(raw.aspect_ratios) ? raw.aspect_ratios.map(String) : [],
    duration_limit_seconds: Number(raw.duration_limit_seconds ?? 0),
    title_limit: Number(raw.title_limit ?? 0),
    body_limit: Number(raw.body_limit ?? 0),
    required_fields: Array.isArray(raw.required_fields) ? raw.required_fields.map(String) : [],
    missing_fields: Array.isArray(raw.missing_fields) ? raw.missing_fields.map(String) : [],
    connection: raw.connection && typeof raw.connection === 'object'
      ? {
          id: String((raw.connection as Record<string, unknown>).id ?? ''),
          platform: String((raw.connection as Record<string, unknown>).platform ?? raw.platform ?? ''),
          account_name: typeof (raw.connection as Record<string, unknown>).account_name === 'string' ? String((raw.connection as Record<string, unknown>).account_name) : null,
          account_id: typeof (raw.connection as Record<string, unknown>).account_id === 'string' ? String((raw.connection as Record<string, unknown>).account_id) : null,
          token_expiry: typeof (raw.connection as Record<string, unknown>).token_expiry === 'string' ? String((raw.connection as Record<string, unknown>).token_expiry) : null,
          metadata_json: typeof (raw.connection as Record<string, unknown>).metadata_json === 'string' ? String((raw.connection as Record<string, unknown>).metadata_json) : null,
        }
      : null,
  }
}

function adaptQuota(raw: Record<string, unknown> | null | undefined): QuotaSurface | null {
  if (!raw) return null
  const quota = raw.quota && typeof raw.quota === 'object' ? raw.quota as Record<string, unknown> : raw
  return {
    quota: {
      storage_quota_mb: Number(quota.storage_quota_mb ?? 0),
      ai_spend_cap_usd: Number(quota.ai_spend_cap_usd ?? 0),
      render_minutes_quota: Number(quota.render_minutes_quota ?? 0),
      connected_platforms_quota: Number(quota.connected_platforms_quota ?? 0),
      team_seats_quota: Number(quota.team_seats_quota ?? 0),
      retained_footage_days: Number(quota.retained_footage_days ?? 0),
      automation_max_mode: String(quota.automation_max_mode ?? 'supervised'),
    },
    usage: raw.usage && typeof raw.usage === 'object' ? Object.fromEntries(Object.entries(raw.usage as Record<string, unknown>).map(([key, value]) => [key, Number(value ?? 0)])) : {},
    exceeded: Array.isArray(raw.exceeded) ? raw.exceeded.map(String) : [],
  }
}

function adaptAutonomySettings(raw: Record<string, unknown>): AutonomySettings {
  return {
    autonomy_mode: (raw.autonomy_mode as AutonomySettings['autonomy_mode']) ?? 'supervised',
    confidence_threshold: Number(raw.confidence_threshold ?? raw.autonomy_confidence_threshold ?? 0.8),
    allowed_platforms: Array.isArray(raw.allowed_platforms) ? raw.allowed_platforms.map(String) : [],
    quiet_hours: typeof raw.quiet_hours === 'string' ? raw.quiet_hours : null,
    notification_preferences: typeof raw.notification_preferences === 'string' ? raw.notification_preferences : null,
  }
}

function adaptMember(raw: Record<string, unknown>): WorkspaceMemberSurface {
  if (raw.user && typeof raw.user === 'object') {
    const user = raw.user as Record<string, unknown>
    return {
      id: typeof raw.id === 'string' ? raw.id : undefined,
      user_id: String(user.id ?? raw.user_id ?? ''),
      email: String(user.email ?? raw.email ?? ''),
      name: String(user.name ?? raw.name ?? ''),
      role: String(raw.role ?? 'viewer') as WorkspaceMemberSurface['role'],
    }
  }
  return {
    id: typeof raw.id === 'string' ? raw.id : undefined,
    user_id: String(raw.user_id ?? ''),
    email: String(raw.email ?? ''),
    name: String(raw.name ?? ''),
    role: String(raw.role ?? 'viewer') as WorkspaceMemberSurface['role'],
  }
}

function adaptPlan(raw: Record<string, unknown>): SubscriptionPlan {
  return {
    id: String(raw.id ?? ''),
    key: String(raw.key ?? ''),
    name: String(raw.name ?? ''),
    monthly_price_usd: Number(raw.monthly_price_usd ?? 0),
    quotas: parseJson<Record<string, unknown>>(raw.quotas ?? raw.quotas_json, {}),
    features: parseJson<Record<string, unknown>>(raw.features ?? raw.features_json, {}),
  }
}

function adaptStyleProfile(raw: Record<string, unknown>): StyleProfile {
  return {
    id: String(raw.id ?? ''),
    name: String(raw.name ?? ''),
    genre: String(raw.genre ?? ''),
    style_doc: parseJson<Record<string, unknown>>(raw.style_doc, {}),
    confidence_scores: parseJson<Record<string, number>>(raw.confidence_scores, {}),
    dimension_locks: parseJson<Record<string, boolean>>(raw.dimension_locks, {}),
    version: Number(raw.version ?? 1),
  }
}

function adaptReviewItem(raw: Record<string, unknown>): ReviewQueueSurface {
  return {
    id: String(raw.id ?? raw.clip_id ?? ''),
    clip_id: String(raw.clip_id ?? raw.id ?? ''),
    project_id: String(raw.project_id ?? ''),
    title: typeof raw.title === 'string' ? raw.title : (typeof raw.source_path === 'string' ? raw.source_path.split('/').pop() : undefined),
    status: String(raw.status ?? raw.review_status ?? 'pending_review'),
    edit_confidence: Number(raw.edit_confidence ?? raw.confidence_score ?? 0),
    created_at: String(raw.created_at ?? new Date().toISOString()),
    thumbnail_urls: Array.isArray(raw.thumbnail_urls) ? raw.thumbnail_urls.map(String) : [],
  }
}

function adaptProvider(raw: Record<string, unknown>): AIProviderSurface {
  return {
    id: String(raw.id ?? ''),
    provider: String(raw.provider ?? ''),
    model_key: String(raw.model_key ?? ''),
    display_name: String(raw.display_name ?? raw.model_key ?? ''),
    task_types: parseJson<string[]>(raw.task_types, []),
    enabled: Boolean(raw.enabled),
    capabilities: parseJson<Record<string, unknown>>(raw.capabilities ?? raw.capabilities_json, {}),
    base_url: typeof raw.base_url === 'string' ? raw.base_url : null,
    config: parseJson<Record<string, unknown>>(raw.config ?? raw.config_json, {}),
  }
}

function adaptCredential(raw: Record<string, unknown>): AICredentialSurface {
  return {
    id: String(raw.id ?? ''),
    provider: String(raw.provider ?? ''),
    label: typeof raw.label === 'string' ? raw.label : null,
    allowed_models: parseJson<string[]>(raw.allowed_models, []),
    is_active: Boolean(raw.is_active),
    created_at: typeof raw.created_at === 'string' ? raw.created_at : undefined,
  }
}

function adaptUsage(raw: Record<string, unknown>): AIUsageSurface {
  return {
    id: raw.id == null ? undefined : String(raw.id),
    task_type: String(raw.task_type ?? ''),
    provider: String(raw.provider ?? ''),
    model: typeof raw.model === 'string' ? raw.model : undefined,
    total_cost: typeof raw.total_cost === 'number' ? raw.total_cost : undefined,
    cost_estimate: typeof raw.cost_estimate === 'number' ? raw.cost_estimate : null,
    count: typeof raw.count === 'number' ? raw.count : undefined,
    created_at: typeof raw.created_at === 'string' ? raw.created_at : null,
    status: typeof raw.status === 'string' ? raw.status : undefined,
  }
}

export const surfaceApi = {
  getOverview: async (): Promise<OverviewData> => api.get<OverviewData>('/api/overview'),
  listProjects: async (): Promise<Project[]> => {
    const data = await api.get<Array<Record<string, unknown>> | { projects: Array<Record<string, unknown>> }>('/api/projects')
    const projects = Array.isArray(data) ? data : data.projects
    return projects.map(adaptProject)
  },
  getProjectWorkspace: async (projectId: string): Promise<ProjectWorkspaceData> => {
    const raw = await api.get<Record<string, unknown>>(`/api/projects/${projectId}/workspace`)
    return {
      project: adaptProject(raw.project as Record<string, unknown>),
      clips: Array.isArray(raw.clips) ? raw.clips.map((clip) => adaptClip(clip as Record<string, unknown>)) : [],
      timeline: {
        items: Array.isArray((raw.timeline as Record<string, unknown> | undefined)?.items)
          ? ((raw.timeline as Record<string, unknown>).items as Array<Record<string, unknown>>).map(adaptTimelineItem)
          : [],
      },
      assets: Array.isArray(raw.assets) ? raw.assets.map((asset) => adaptAsset(asset as Record<string, unknown>)) : [],
      music: {
        items: Array.isArray((raw.music as Record<string, unknown> | undefined)?.items)
          ? ((raw.music as Record<string, unknown>).items as Array<Record<string, unknown>>).map((item) => ({
              id: String(item.id ?? ''),
              asset_id: String(item.asset_id ?? ''),
              asset_name: String(item.asset_name ?? ''),
              start_time: Number(item.start_time ?? 0),
              end_time: Number(item.end_time ?? 0),
              volume: Number(item.volume ?? 0),
            }))
          : [],
        volume_envelope: Array.isArray((raw.music as Record<string, unknown> | undefined)?.volume_envelope)
          ? ((raw.music as Record<string, unknown>).volume_envelope as Array<Record<string, unknown>>).map((point) => ({
              t: Number(point.t ?? 0),
              v: Number(point.v ?? 0),
            }))
          : [],
      },
      overlays: {
        titles: Array.isArray((raw.overlays as Record<string, unknown> | undefined)?.titles)
          ? ((raw.overlays as Record<string, unknown>).titles as Array<Record<string, unknown>>).map((item) => ({
              id: String(item.id ?? ''),
              text: String(item.text ?? ''),
              start_time: Number(item.start_time ?? 0),
              end_time: Number(item.end_time ?? 0),
            }))
          : [],
        captions: Array.isArray((raw.overlays as Record<string, unknown> | undefined)?.captions)
          ? ((raw.overlays as Record<string, unknown>).captions as Array<Record<string, unknown>>).map((item) => ({
              id: String(item.id ?? ''),
              text: String(item.text ?? ''),
              start_time: Number(item.start_time ?? 0),
              end_time: Number(item.end_time ?? 0),
            }))
          : [],
        timestamps: Array.isArray((raw.overlays as Record<string, unknown> | undefined)?.timestamps)
          ? ((raw.overlays as Record<string, unknown>).timestamps as Array<Record<string, unknown>>).map((item) => ({
              id: String(item.id ?? ''),
              text: String(item.text ?? ''),
              start_time: Number(item.start_time ?? 0),
              end_time: Number(item.end_time ?? 0),
            }))
          : [],
        trackers: Array.isArray((raw.overlays as Record<string, unknown> | undefined)?.trackers)
          ? ((raw.overlays as Record<string, unknown>).trackers as Array<Record<string, unknown>>).map((item) => ({
              id: String(item.id ?? ''),
              start_time: Number(item.start_time ?? 0),
              end_time: Number(item.end_time ?? 0),
              overlay_url: String(item.overlay_url ?? ''),
            }))
          : [],
        subscribes: Array.isArray((raw.overlays as Record<string, unknown> | undefined)?.subscribes)
          ? ((raw.overlays as Record<string, unknown>).subscribes as Array<Record<string, unknown>>).map((item) => ({
              id: String(item.id ?? ''),
              text: String(item.text ?? ''),
              start_time: Number(item.start_time ?? 0),
              end_time: Number(item.end_time ?? 0),
            }))
          : [],
      },
      render: {
        status: String((raw.render as Record<string, unknown> | undefined)?.status ?? 'idle'),
        has_render: Boolean((raw.render as Record<string, unknown> | undefined)?.has_render),
        render_path: typeof (raw.render as Record<string, unknown> | undefined)?.render_path === 'string'
          ? String((raw.render as Record<string, unknown>).render_path)
          : null,
      },
      publish: {
        platforms: Array.isArray((raw.publish as Record<string, unknown> | undefined)?.platforms)
          ? ((raw.publish as Record<string, unknown>).platforms as Array<Record<string, unknown>>).map(adaptPlatform)
          : [],
        recent_slots: Array.isArray((raw.publish as Record<string, unknown> | undefined)?.recent_slots)
          ? ((raw.publish as Record<string, unknown>).recent_slots as Array<Record<string, unknown>>).map(adaptCalendarSlot)
          : [],
        autonomy: adaptAutonomySettings(((raw.publish as Record<string, unknown> | undefined)?.autonomy ?? {}) as Record<string, unknown>),
      },
    }
  },
  getPlatforms: async (): Promise<PlatformSurface[]> => {
    const data = await api.get<{ platforms: Array<Record<string, unknown>> }>('/api/platforms')
    return data.platforms.map(adaptPlatform)
  },
  getCalendar: async (): Promise<CalendarSlotSurface[]> => {
    const data = await api.get<{ slots?: Array<Record<string, unknown>> } | Array<Record<string, unknown>>>('/api/platforms/calendar')
    const slots = Array.isArray(data) ? data : (data.slots ?? [])
    return slots.map(adaptCalendarSlot)
  },
  getCalendarGaps: async (platform: string): Promise<GapSlot[]> => {
    const data = await api.get<{ gaps?: GapSlot[] } | GapSlot[]>(`/api/calendar/gaps?platform=${encodeURIComponent(platform)}`)
    return Array.isArray(data) ? data : (data.gaps ?? [])
  },
  getReviewQueue: async (): Promise<ReviewQueueSurface[]> => {
    const data = await api.get<Array<Record<string, unknown>>>('/api/autonomy/review-queue')
    return data.map(adaptReviewItem)
  },
  getReviewSettings: async (projectId?: string): Promise<AutonomySettings> => {
    const path = projectId ? `/api/autonomy/settings?project_id=${encodeURIComponent(projectId)}` : '/api/autonomy/settings'
    const data = await api.get<Record<string, unknown>>(path)
    return adaptAutonomySettings(data)
  },
  getMembers: async (): Promise<WorkspaceMemberSurface[]> => {
    const data = await api.get<Array<Record<string, unknown>>>('/api/workspaces/current/members')
    return data.map(adaptMember)
  },
  getInvitation: async (token: string): Promise<InvitationPreview> => {
    const data = await api.get<Record<string, unknown>>(`/invitations/${token}`)
    return {
      id: String(data.id ?? ''),
      email: String(data.email ?? ''),
      role: String(data.role ?? 'viewer'),
      status: String(data.status ?? ''),
      expires_at: String(data.expires_at ?? ''),
      workspace_id: String(data.workspace_id ?? ''),
      workspace_name: String(data.workspace_name ?? 'Workspace'),
    }
  },
  listStyleProfiles: async (): Promise<StyleProfile[]> => {
    const data = await api.get<{ profiles?: Array<Record<string, unknown>> } | Array<Record<string, unknown>>>('/api/style-profiles')
    const profiles = Array.isArray(data) ? data : (data.profiles ?? [])
    return profiles.map(adaptStyleProfile)
  },
  getAIProviders: async (): Promise<AIProviderSurface[]> => {
    const data = await api.get<Array<Record<string, unknown>>>('/api/ai/admin/providers')
    return data.map(adaptProvider)
  },
  getAICredentials: async (): Promise<AICredentialSurface[]> => {
    const data = await api.get<Array<Record<string, unknown>>>('/api/ai/credentials')
    return data.map(adaptCredential)
  },
  getAIUsage: async (): Promise<AIUsageSurface[]> => {
    const data = await api.get<Array<Record<string, unknown>>>('/api/ai/usage')
    return data.map(adaptUsage)
  },
  getPlans: async (): Promise<SubscriptionPlan[]> => {
    const data = await api.get<Array<Record<string, unknown>>>('/api/enterprise/plans')
    return data.map(adaptPlan)
  },
  getSubscription: async (): Promise<WorkspaceSubscription | null> => {
    try {
      const data = await api.get<Record<string, unknown>>('/api/enterprise/subscription')
      return {
        id: String(data.id ?? ''),
        plan_id: String(data.plan_id ?? ''),
        status: String(data.status ?? ''),
        current_period_end: typeof data.current_period_end === 'string' ? data.current_period_end : null,
        billing_email: typeof data.billing_email === 'string' ? data.billing_email : null,
      }
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) return null
      throw error
    }
  },
  getQuota: async (): Promise<QuotaSurface | null> => {
    try {
      const data = await api.get<Record<string, unknown>>('/api/enterprise/quota')
      return adaptQuota(data)
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) return null
      throw error
    }
  },
}
