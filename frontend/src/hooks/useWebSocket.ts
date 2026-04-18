import { useEffect, useRef } from "react";
import { api } from "@/lib/api";
import { useTimelineStore } from "../stores/timelineStore";
import type { Clip, Project, TimelineItem, WsMessage } from "../types";

export function useWebSocket(projectId: string | null) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!projectId) return;

    let cancelled = false;
    let reconnectAttempt = 0;

    const clearTimers = () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (heartbeatRef.current) {
        clearInterval(heartbeatRef.current);
        heartbeatRef.current = null;
      }
    };

    const scheduleReconnect = () => {
      if (cancelled) return;
      clearTimers();
      const delay = Math.min(1000 * 2 ** reconnectAttempt, 10000);
      reconnectAttempt += 1;
      reconnectTimerRef.current = setTimeout(connect, delay);
    };

    const connect = () => {
      if (cancelled) return;
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const host = process.env.NEXT_PUBLIC_WS_URL ?? window.location.host;
      const ws = new WebSocket(`${protocol}//${host}/ws/${projectId}`);
      wsRef.current = ws;

      ws.onopen = () => {
        reconnectAttempt = 0;
        clearTimers();
        heartbeatRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send("ping");
          }
        }, 30000);
      };

      ws.onmessage = (event) => {
        const msg: WsMessage = JSON.parse(event.data);
        const store = useTimelineStore.getState();

        switch (msg.event) {
          case "clip_detected":
            store.addClip({
              id: String(msg.data.clip_id ?? ""),
              source_path: (msg.data.filename as string) || "",
              processed_path: null,
              clip_type: null,
              status: "pending",
              duration: null,
              transcript: null,
              error_message: null,
              sub_clips: [],
            });
            break;
          case "clip_status":
            store.updateClipStatus(
              String(msg.data.clip_id ?? ""),
              msg.data.status as "pending" | "transcribing" | "classifying" | "processing" | "done" | "error"
            );
            break;
          case "clip_progress":
            store.updateClipStatus(
              String(msg.data.clip_id ?? ""),
              msg.data.status as "pending" | "transcribing" | "classifying" | "processing" | "done" | "error",
              msg.data.progress as number,
              msg.data.detail as string,
            );
            break;
          case "clip_done":
          case "clip_error":
            refreshData(projectId);
            break;
          case "timeline_updated":
            refreshTimeline(projectId);
            break;
          case "render_progress":
            store.setRenderProgress(
              msg.data.percent as number,
              msg.data.stage as string
            );
            break;
          case "render_done":
            store.setRenderProgress(100, "done");
            refreshProject(projectId);
            break;
          case "youtube_upload_progress":
            store.setYoutubeUploadProgress(msg.data.percent as number);
            break;
          case "youtube_upload_done":
            store.setYoutubeUploadProgress(100);
            store.setYoutubeUploadResult({
              videoId: msg.data.video_id as string,
              videoUrl: msg.data.video_url as string,
            });
            break;
          case "youtube_upload_error":
            store.setYoutubeUploadProgress(null);
            store.setYoutubeUploadError(msg.data.error as string);
            break;
          case "upload_progress": {
            const { session_id, stage, pct } = msg.data as { session_id: string; stage: string; pct: number }
            if (stage === "done") {
              store.setUploadProgress(session_id, null);
            } else {
              store.setUploadProgress(session_id, { stage, pct });
            }
            break;
          }
          case "clip.draft_ready":
          case "review_queue.updated":
          case "review_queue_updated":
            store.setReviewQueueDirty(true);
            break;
        }
      };

      ws.onerror = () => {
        ws.close();
      };

      ws.onclose = () => {
        if (wsRef.current === ws) {
          wsRef.current = null;
        }
        scheduleReconnect();
      };
    };

    connect();

    return () => {
      cancelled = true;
      clearTimers();
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [projectId]);
}

async function refreshData(projectId: string) {
  const store = useTimelineStore.getState();
  try {
    const [clips, timelineItems] = await Promise.all([
      api.get<Clip[]>(`/api/clips?project_id=${projectId}`),
      api.get<TimelineItem[]>(`/api/timeline/${projectId}`),
    ]);
    store.setClips(clips);
    store.setTimelineItems(timelineItems);
  } catch {
    void 0;
  }
}

async function refreshTimeline(projectId: string) {
  const store = useTimelineStore.getState();
  try {
    const timelineItems = await api.get<TimelineItem[]>(`/api/timeline/${projectId}`);
    store.setTimelineItems(timelineItems);
  } catch {
    void 0;
  }
}

async function refreshProject(projectId: string) {
  const store = useTimelineStore.getState();
  try {
    const project = await api.get<Project>(`/api/projects/${projectId}`);
    store.setProject(project);
  } catch {
    void 0;
  }
}
