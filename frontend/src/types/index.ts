export interface Project {
  id: string
  name: string
  workspace_id: string
  status?: string
  created_at?: string
}

export interface SubClip {
  id: number;
  start_time: number;
  end_time: number;
  score: number | null;
  label: string | null;
}

export interface Clip {
  id: number;
  source_path: string;
  processed_path: string | null;
  clip_type: "talking" | "broll" | "remix" | null;
  status: "pending" | "transcribing" | "classifying" | "processing" | "done" | "error";
  duration: number | null;
  transcript: string | null;
  error_message: string | null;
  sub_clips: SubClip[];
  progress?: number | null;
  progressDetail?: string | null;
}

export interface TimelineItem {
  id: number;
  clip_id: number | null;
  sub_clip_id: number | null;
  position: number;
  video_url: string;
  duration: number;
  start_time: number;
  end_time: number;
  label: string;
  clip_type: string | null;
}

export interface Asset {
  id: number;
  name: string;
  file_path: string;
  asset_type: "music" | "sfx";
  duration: number;
}

export interface MusicItem {
  id: number;
  asset_id: number;
  asset_name: string;
  file_path?: string;
  start_time: number;
  end_time: number;
  volume: number;
}

export interface TitleItem {
  id: number
  text: string
  start_time: number
  end_time: number
}

export interface CaptionItem {
  id: number
  text: string
  start_time: number
  end_time: number
}

export interface TimestampItem {
  id: number
  text: string
  start_time: number
  end_time: number
}

export interface TrackerItem {
  id: number
  start_time: number
  end_time: number
  overlay_url: string
}

export interface SubscribeItem {
  id: number
  text: string
  start_time: number
  end_time: number
}

export interface VolumeKeypoint {
  t: number;
  v: number;
}

export interface WsMessage {
  event: string;
  data: Record<string, unknown>;
}

export interface TitleSuggestionsResponse {
  titles: string[];
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
}

export interface Membership {
  user_id: string
  email: string
  name: string
  role: 'owner' | 'admin' | 'editor' | 'viewer'
}

export interface Invitation {
  id: string
  email: string
  role: string
  status: string
  expires_at: string
}

export interface StyleProfile {
  id: string
  name: string
  genre: string
  style_doc: string
  confidence_scores: Record<string, number>
  dimension_locks: Record<string, boolean>
  version: number
}

export interface SubscriptionPlan {
  id: string
  key: string
  name: string
  monthly_price_usd: number
  quotas_json: string
  features_json: string
}

export interface WorkspaceSubscription {
  id: string
  plan_id: string
  status: string
  current_period_end: string
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

export interface UsageRecord {
  dimension: string
  used: number
  limit: number
}

export interface PlatformConnection {
  id: string
  platform: string
  display_name: string
  status: string
  scopes: string[]
}

export interface CalendarSlot {
  id: string
  platform: string
  scheduled_at: string
  status: string
  clip_id: string
  publish_url?: string
  failure_reason?: string
}

export interface AIProviderConfig {
  id: string
  provider: string
  model_key: string
  display_name: string
  task_types: string[]
  enabled: boolean
}

export interface AICredential {
  id: string
  provider: string
  allowed_models: string[]
  is_active: boolean
}

export interface ReviewQueueItem {
  id: string
  clip_id: string
  project_id: string
  title?: string
  status: string
  edit_confidence: number
  created_at: string
}

export interface AutonomySettings {
  autonomy_mode: 'supervised' | 'review_then_publish' | 'auto_publish'
  autonomy_confidence_threshold: number
}

export interface GapSlot {
  platform: string
  suggested_at: string
  score: number
}
