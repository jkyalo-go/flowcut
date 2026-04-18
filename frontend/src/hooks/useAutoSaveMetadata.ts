import { useEffect, useRef } from "react";
import { api } from "@/lib/api";
import { useTimelineStore } from "../stores/timelineStore";

export function useAutoSaveMetadata() {
  const project = useTimelineStore((s) => s.project);
  const selectedTitle = useTimelineStore((s) => s.selectedTitle);
  const videoDescription = useTimelineStore((s) => s.videoDescription);
  const videoTags = useTimelineStore((s) => s.videoTags);
  const videoCategory = useTimelineStore((s) => s.videoCategory);
  const videoVisibility = useTimelineStore((s) => s.videoVisibility);
  const selectedThumbnailIndices = useTimelineStore((s) => s.selectedThumbnailIndices);
  const descSystemPrompt = useTimelineStore((s) => s.descSystemPrompt);
  const thumbnailUrls = useTimelineStore((s) => s.thumbnailUrls);
  const thumbnailText = useTimelineStore((s) => s.thumbnailText);
  const setSaveStatus = useTimelineStore((s) => s.setSaveStatus);

  const initializedRef = useRef(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fadeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!initializedRef.current) {
      initializedRef.current = true;
      return;
    }
    if (!project) return;

    setSaveStatus("saving");
    if (timerRef.current) clearTimeout(timerRef.current);
    if (fadeTimerRef.current) clearTimeout(fadeTimerRef.current);

    timerRef.current = setTimeout(async () => {
      try {
        await api.put(`/api/projects/${project.id}/metadata`, {
            selected_title: selectedTitle,
            video_description: videoDescription,
            video_tags: JSON.stringify(videoTags),
            video_category: videoCategory,
            video_visibility: videoVisibility,
            selected_thumbnail_idx: selectedThumbnailIndices[0] ?? null,
            desc_system_prompt: descSystemPrompt,
            thumbnail_urls: JSON.stringify(thumbnailUrls),
            locked_thumbnail_indices: JSON.stringify(selectedThumbnailIndices),
            thumbnail_text: thumbnailText,
        });
        setSaveStatus("saved");
        fadeTimerRef.current = setTimeout(() => setSaveStatus("idle"), 2000);
      } catch {
        // Do not silently drop back to "idle" — surface a distinct "error"
        // state so the UI can tell the user their changes were not saved.
        setSaveStatus("error");
      }
    }, 1000);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [descSystemPrompt, project, selectedThumbnailIndices, selectedTitle, setSaveStatus, thumbnailText, thumbnailUrls, videoCategory, videoDescription, videoTags, videoVisibility]);
}
