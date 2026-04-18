export type EntityId = string | number

export interface Project {
  id: string
  name: string
  workspace_id: string
  created_at?: string
  status?: string | null
  render_path?: string | null
  autonomy_mode?: string | null
  selected_title?: string | null
  video_description?: string | null
  video_tags?: string[] | string | null
  video_category?: string | null
  video_visibility?: string | null
  selected_thumbnail_idx?: number | null
  desc_system_prompt?: string | null
  thumbnail_urls?: string[] | string | null
  locked_thumbnail_indices?: number[] | string | null
  thumbnail_text?: string | null
  clips?: Clip[]
}

export interface SubClip {
  id: EntityId
  start_time: number
  end_time: number
  score: number | null
  label: string | null
}

export interface Clip {
  id: EntityId
  workspace_id?: string
  project_id?: string
  source_path: string
  processed_path: string | null
  clip_type: 'talking' | 'broll' | 'remix' | null
  status: 'pending' | 'transcribing' | 'classifying' | 'processing' | 'done' | 'error'
  review_status?: string | null
  confidence_score?: number | null
  duration: number | null
  transcript: string | null
  error_message: string | null
  sub_clips: SubClip[]
  progress?: number | null
  progressDetail?: string | null
}

export interface TimelineItem {
  id: EntityId
  clip_id: EntityId | null
  sub_clip_id: EntityId | null
  position: number
  video_url: string
  duration: number
  start_time: number
  end_time: number
  label: string
  clip_type: string | null
}

export interface Asset {
  id: EntityId
  name: string
  file_path: string
  asset_type: 'music' | 'sfx'
  duration: number
}

export interface MusicItem {
  id: EntityId
  asset_id: EntityId
  asset_name: string
  file_path?: string
  start_time: number
  end_time: number
  volume: number
}

export interface TitleItem {
  id: EntityId
  text: string
  start_time: number
  end_time: number
}

export interface CaptionItem {
  id: EntityId
  text: string
  start_time: number
  end_time: number
}

export interface TimestampItem {
  id: EntityId
  text: string
  start_time: number
  end_time: number
}

export interface TrackerItem {
  id: EntityId
  start_time: number
  end_time: number
  overlay_url: string
}

export interface SubscribeItem {
  id: EntityId
  text: string
  start_time: number
  end_time: number
}

export interface VolumeKeypoint {
  t: number
  v: number
}

export interface WsMessage {
  event: string
  data: Record<string, unknown>
}

export interface TitleSuggestionsResponse {
  titles: string[]
}

export interface User {
  id: string
  email: string
  name: string
  user_type: 'admin' | 'user'
  avatar_url?: string
}

export interface Workspace {
  id: string
  name: string
  slug: string
  plan_tier: string
  lifecycle_status: string
  autonomy_mode?: string
}

export interface WorkspaceMemberSurface {
  id?: string
  user_id: string
  email: string
  name: string
  role: 'owner' | 'admin' | 'editor' | 'viewer'
}

export interface InvitationPreview {
  id: string
  email: string
  role: string
  status: string
  expires_at: string
  workspace_id: string
  workspace_name: string
}

export interface StyleProfile {
  id: string
  name: string
  genre: string
  style_doc: Record<string, unknown>
  confidence_scores: Record<string, number>
  dimension_locks: Record<string, boolean>
  version: number
}

export interface SubscriptionPlan {
  id: string
  key: string
  name: string
  monthly_price_usd: number
  quotas: Record<string, unknown>
  features: Record<string, unknown>
  quotas_json?: string
  features_json?: string
}

export interface WorkspaceSubscription {
  id: string
  plan_id: string
  status: string
  current_period_end?: string | null
  billing_email?: string | null
}

export interface QuotaPolicy {
  storage_quota_mb: number
  ai_spend_cap_usd: number
  render_minutes_quota: number
  connected_platforms_quota: number
  team_seats_quota: number
  retained_footage_days: number
  automation_max_mode: string
}

export interface QuotaSurface {
  quota: QuotaPolicy
  usage: Record<string, number>
  exceeded: string[]
}

export interface PlatformSurface {
  id?: string
  platform: string
  label: string
  connected: boolean
  ready: boolean
  status: string
  display_name: string
  scopes: string[]
  auth_mode: string
  supports_thumbnail: boolean
  supports_scheduling: boolean
  aspect_ratios: string[]
  duration_limit_seconds: number
  title_limit: number
  body_limit: number
  required_fields: string[]
  missing_fields: string[]
  connection?: {
    id: string
    platform: string
    account_name?: string | null
    account_id?: string | null
    token_expiry?: string | null
    metadata_json?: string | null
  } | null
}

export interface CalendarSlotSurface {
  id: string
  platform: string
  scheduled_at: string
  status: 'scheduled' | 'processing' | 'published' | 'failed' | 'cancelled' | string
  clip_id?: string | null
  project_id?: string | null
  render_variant?: string | null
  publish_url?: string | null
  failure_reason?: string | null
  retry_count?: number
  correlation_id?: string | null
  metadata?: Record<string, unknown>
  title?: string
}

export interface GapSlot {
  platform: string
  suggested_at: string
  score: number
}

export interface AIProviderSurface {
  id: string
  provider: string
  model_key: string
  display_name: string
  task_types: string[]
  enabled: boolean
  capabilities?: Record<string, unknown>
  base_url?: string | null
  config?: Record<string, unknown>
}

export interface AICredentialSurface {
  id: string
  provider: string
  label?: string | null
  allowed_models: string[]
  is_active: boolean
  created_at?: string
}

export interface AIUsageSurface {
  id?: string
  task_type: string
  provider: string
  model?: string
  total_cost?: number
  cost_estimate?: number | null
  count?: number
  created_at?: string | null
  status?: string
}

export interface ReviewQueueSurface {
  id: string
  clip_id: string
  project_id: string
  title?: string
  status: string
  edit_confidence: number
  created_at: string
  thumbnail_urls?: string[]
}

export interface AutonomySettings {
  autonomy_mode: 'supervised' | 'review_then_publish' | 'auto_publish'
  confidence_threshold: number
  autonomy_confidence_threshold?: number
  allowed_platforms?: string[]
  quiet_hours?: string | null
  notification_preferences?: string | null
}

export interface UsageRecord {
  id: string
  category: string
  quantity: number
  unit?: string | null
  amount_usd?: number | null
  correlation_id?: string | null
  created_at?: string | null
}

export interface OverviewData {
  review: {
    pending: number
    items: ReviewQueueSurface[]
  }
  schedule: {
    upcoming: CalendarSlotSurface[]
    scheduled_count: number
    failed_count: number
    published_count: number
  }
  platforms: {
    items: PlatformSurface[]
    connected: number
    ready: number
    total: number
  }
  quota: QuotaSurface
  activity: Array<{
    id: string
    actor: string
    action: string
    target_type: string
    target_id?: string | null
    reason?: string | null
    created_at?: string | null
    metadata?: Record<string, unknown>
  }>
  onboarding: {
    items: Array<{ key: string; label: string; completed: boolean }>
    completed_count: number
    total: number
  }
  projects: {
    total: number
    recent: Array<{
      id: string
      name: string
      created_at?: string | null
      render_path?: string | null
      clip_count: number
    }>
  }
}

export interface ProjectWorkspaceData {
  project: Project
  clips: Clip[]
  timeline: { items: TimelineItem[] }
  assets: Asset[]
  music: {
    items: MusicItem[]
    volume_envelope: VolumeKeypoint[]
  }
  overlays: {
    titles: TitleItem[]
    captions: CaptionItem[]
    timestamps: TimestampItem[]
    trackers: TrackerItem[]
    subscribes: SubscribeItem[]
  }
  render: {
    status: string
    has_render: boolean
    render_path?: string | null
  }
  publish: {
    platforms: PlatformSurface[]
    recent_slots: CalendarSlotSurface[]
    autonomy: AutonomySettings
  }
}

export type Membership = WorkspaceMemberSurface
export type PlatformConnection = PlatformSurface
export type CalendarSlot = CalendarSlotSurface
export type ReviewQueueItem = ReviewQueueSurface
export type AIProviderConfig = AIProviderSurface
export type AICredential = AICredentialSurface
