import { create } from "zustand";
import type { RefObject } from "react";
import type { PlayerRef } from "@remotion/player";
import type { Project, Clip, TimelineItem } from "../types";

interface TimelineStore {
  project: Project | null;
  clips: Clip[];
  timelineItems: TimelineItem[];
  isWatching: boolean;
  renderProgress: number | null;
  renderStage: string | null;
  playerRef: RefObject<PlayerRef | null> | null;

  setProject: (p: Project | null) => void;
  setClips: (clips: Clip[]) => void;
  addClip: (clip: Clip) => void;
  updateClipStatus: (clipId: number, status: Clip["status"], progress?: number | null, detail?: string | null) => void;
  updateClip: (clip: Partial<Clip> & { id: number }) => void;
  setTimelineItems: (items: TimelineItem[]) => void;
  setIsWatching: (w: boolean) => void;
  setRenderProgress: (pct: number | null, stage?: string | null) => void;
  setPlayerRef: (ref: RefObject<PlayerRef | null> | null) => void;
}

export const useTimelineStore = create<TimelineStore>((set) => ({
  project: null,
  clips: [],
  timelineItems: [],
  isWatching: false,
  renderProgress: null,
  renderStage: null,
  playerRef: null,

  setProject: (project) => set({ project }),
  setClips: (clips) => set({ clips }),

  addClip: (clip) =>
    set((state) => ({
      clips: [...state.clips, clip],
    })),

  updateClipStatus: (clipId, status, progress, detail) =>
    set((state) => ({
      clips: state.clips.map((c) =>
        c.id === clipId
          ? { ...c, status, progress: progress ?? c.progress, progressDetail: detail ?? c.progressDetail }
          : c
      ),
    })),

  updateClip: (partial) =>
    set((state) => ({
      clips: state.clips.map((c) =>
        c.id === partial.id ? { ...c, ...partial } : c
      ),
    })),

  setTimelineItems: (items) => set({ timelineItems: items }),
  setIsWatching: (isWatching) => set({ isWatching }),
  setRenderProgress: (pct, stage) =>
    set({ renderProgress: pct, renderStage: stage ?? null }),
  setPlayerRef: (playerRef) => set({ playerRef }),
}));
