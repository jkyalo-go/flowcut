import type { TimelineRow, TimelineAction } from "@xzdarcy/react-timeline-editor";
import type { TimelineItem } from "../types";

export const FPS = 30;

export function secondsToFrames(seconds: number): number {
  return Math.round(seconds * FPS);
}

export function framesToSeconds(frames: number): number {
  return frames / FPS;
}

export interface VideoAction extends TimelineAction {
  videoUrl: string;
  sourceStart: number;
  sourceEnd: number;
  label: string;
  clipType: string | null;
}

/**
 * Convert backend TimelineItem[] into react-timeline-editor format.
 * All clips go on a single video track, placed back-to-back.
 */
export function toEditorData(items: TimelineItem[]): {
  rows: TimelineRow[];
  actions: VideoAction[];
  totalDuration: number;
} {
  let cursor = 0;
  const actions: VideoAction[] = [];

  for (const item of items) {
    if (item.duration < 0.034) continue; // skip sub-frame clips
    const action: VideoAction = {
      id: String(item.id),
      start: cursor,
      end: cursor + item.duration,
      effectId: "video",
      videoUrl: item.video_url,
      sourceStart: item.start_time,
      sourceEnd: item.end_time,
      label: item.label,
      clipType: item.clip_type,
    };
    actions.push(action);
    cursor += item.duration;
  }

  const rows: TimelineRow[] = [
    {
      id: "video-track",
      actions,
    },
  ];

  return { rows, actions, totalDuration: cursor };
}

/**
 * Compute total duration in frames for the Remotion Player.
 */
export function totalDurationInFrames(items: TimelineItem[]): number {
  let total = 0;
  for (const item of items) {
    if (item.duration < 0.034) continue;
    total += Math.max(secondsToFrames(item.duration), 1);
  }
  return total;
}

/**
 * Given a timeline time in seconds, find which action it falls in
 * and compute the Remotion frame number for the composition.
 */
export function timelineSecondsToFrame(seconds: number, items: TimelineItem[]): number {
  let cursor = 0;
  let frameCursor = 0;
  for (const item of items) {
    if (item.duration < 0.034) continue;
    const dur = item.duration;
    const frames = Math.max(secondsToFrames(dur), 1);
    if (seconds < cursor + dur) {
      const offset = seconds - cursor;
      return frameCursor + Math.round(offset * FPS);
    }
    cursor += dur;
    frameCursor += frames;
  }
  return frameCursor;
}

/**
 * Given a Remotion frame number, compute the timeline time in seconds.
 */
export function frameToTimelineSeconds(frame: number, items: TimelineItem[]): number {
  let cursor = 0;
  let frameCursor = 0;
  for (const item of items) {
    if (item.duration < 0.034) continue;
    const dur = item.duration;
    const frames = Math.max(secondsToFrames(dur), 1);
    if (frame < frameCursor + frames) {
      const offsetFrames = frame - frameCursor;
      return cursor + offsetFrames / FPS;
    }
    cursor += dur;
    frameCursor += frames;
  }
  return cursor;
}

export interface FrameLayoutEntry {
  item: TimelineItem;
  startFrame: number;
  durationInFrames: number;
}

export function computeFrameLayout(items: TimelineItem[]): FrameLayoutEntry[] {
  let currentFrame = 0;
  return items
    .filter((item) => item.duration >= 0.034)
    .map((item) => {
      const durationInFrames = Math.max(secondsToFrames(item.duration), 1);
      const entry: FrameLayoutEntry = {
        item,
        startFrame: currentFrame,
        durationInFrames,
      };
      currentFrame += durationInFrames;
      return entry;
    });
}
