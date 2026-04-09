export interface Project {
  id: number;
  name: string;
  watch_directory: string;
  clips: Clip[];
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
  clip_type: "talking" | "broll" | null;
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

export interface WsMessage {
  event: string;
  data: Record<string, unknown>;
}
