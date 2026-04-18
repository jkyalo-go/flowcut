import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Timeline as TimelineEditor, type TimelineState } from "@xzdarcy/react-timeline-editor";
import "@xzdarcy/react-timeline-editor/dist/react-timeline-editor.css";
import { api } from "@/lib/api";
import { useTimelineStore } from "../stores/timelineStore";
import { toEditorData, timelineSecondsToFrame, type VideoAction, type MusicAction, type TitleAction, type CaptionAction, type TimestampAction } from "../lib/remotion";
import type { EntityId } from "../types";

const effects = {
  video: {
    id: "video",
    name: "Video",
  },
  music: {
    id: "music",
    name: "Music",
  },
  title: {
    id: "title",
    name: "Title",
  },
  caption: {
    id: "caption",
    name: "Caption",
  },
  timestamp: {
    id: "timestamp",
    name: "Timestamp",
  },
  tracker: {
    id: "tracker",
    name: "Tracker",
  },
  subscribe: {
    id: "subscribe",
    name: "Subscribe",
  },
};

const SCALE = 5; // seconds per tick
const MIN_SCALE_WIDTH = 20;
const MAX_SCALE_WIDTH = 500;
const DEFAULT_SCALE_WIDTH = 160;

export function Timeline() {
  const {
    project, timelineItems, setTimelineItems, musicItems, playerRef,
    setMusicItems, setVolumeEnvelope, musicLoading, setMusicLoading,
    titleItems, setTitleItems, titleLoading, setTitleLoading, updateTitleItem,
    captionItems, setCaptionItems, captionLoading, setCaptionLoading, updateCaptionItem,
    timestampItems, setTimestampItems, timestampLoading, setTimestampLoading, updateTimestampItem,
    trackerItems, setTrackerItems, trackerLoading, setTrackerLoading,
    subscribeItems, setSubscribeItems, subscribeLoading, setSubscribeLoading,
    remixLoading, setRemixLoading,
  } = useTimelineStore();
  const timelineRef = useRef<TimelineState>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const syncingFromPlayer = useRef(false);
  const [scaleWidth, setScaleWidth] = useState(DEFAULT_SCALE_WIDTH);
  const [autoFit, setAutoFit] = useState(true);

  const [editingTitleId, setEditingTitleId] = useState<EntityId | null>(null);
  const [editingTitleText, setEditingTitleText] = useState("");
  const [editingCaptionId, setEditingCaptionId] = useState<EntityId | null>(null);
  const [editingCaptionText, setEditingCaptionText] = useState("");
  const [editingTimestampId, setEditingTimestampId] = useState<EntityId | null>(null);
  const [editingTimestampText, setEditingTimestampText] = useState("");

  const { rows, totalDuration } = useMemo(
    () => toEditorData(timelineItems, musicItems, titleItems, captionItems, timestampItems, trackerItems, subscribeItems),
    [timelineItems, musicItems, titleItems, captionItems, timestampItems, trackerItems, subscribeItems]
  );

  // Auto-fit: calculate scaleWidth so all clips fit in the container
  useEffect(() => {
    if (!autoFit || totalDuration === 0 || !wrapperRef.current) return;
    const containerWidth = wrapperRef.current.clientWidth - 40; // padding
    const numTicks = totalDuration / SCALE;
    if (numTicks > 0) {
      const fitted = Math.max(MIN_SCALE_WIDTH, Math.min(MAX_SCALE_WIDTH, containerWidth / numTicks));
      setScaleWidth(fitted);
    }
  }, [autoFit, totalDuration]);

  // Option + scroll wheel to zoom
  useEffect(() => {
    const el = wrapperRef.current;
    if (!el) return;

    const handleWheel = (e: WheelEvent) => {
      if (!e.altKey) return;
      e.preventDefault();
      setAutoFit(false);
      setScaleWidth((prev) => {
        const delta = e.deltaY > 0 ? -10 : 10;
        return Math.max(MIN_SCALE_WIDTH, Math.min(MAX_SCALE_WIDTH, prev + delta));
      });
    };

    el.addEventListener("wheel", handleWheel, { passive: false });
    return () => el.removeEventListener("wheel", handleWheel);
  }, []);

  // Sync Remotion Player frame -> timeline cursor
  useEffect(() => {
    const player = playerRef?.current;
    if (!player) return;

    const handler = () => {
      if (syncingFromPlayer.current) return;
      const frame = player.getCurrentFrame();
      let cursor = 0;
      let frameCursor = 0;
      for (const item of timelineItems) {
        if (item.duration < 0.034) continue;
        const frames = Math.max(Math.round(item.duration * 30), 1);
        if (frame < frameCursor + frames) {
          const offset = (frame - frameCursor) / 30;
          const time = cursor + offset;
          timelineRef.current?.setTime(time);
          return;
        }
        cursor += item.duration;
        frameCursor += frames;
      }
      timelineRef.current?.setTime(cursor);
    };

    player.addEventListener("frameupdate", handler);
    return () => player.removeEventListener("frameupdate", handler);
  }, [playerRef, timelineItems]);

  const handleCursorDrag = useCallback((time: number) => {
    syncingFromPlayer.current = true;
    const frame = timelineSecondsToFrame(time, timelineItems);
    playerRef?.current?.seekTo(frame);
    requestAnimationFrame(() => {
      syncingFromPlayer.current = false;
    });
  }, [playerRef, timelineItems]);

  const handleClickTimeArea = useCallback((time: number) => {
    handleCursorDrag(time);
    return true;
  }, [handleCursorDrag]);

  const handleAddMusic = async () => {
    if (!project) return;
    setMusicLoading(true);
    try {
      const data = await api.post<{ items: typeof musicItems; volume_envelope: ReturnType<typeof useTimelineStore.getState>["volumeEnvelope"] }>(`/api/music/${project.id}/auto`);
      setMusicItems(data.items);
      setVolumeEnvelope(data.volume_envelope);
    } finally {
      setMusicLoading(false);
    }
  };

  const handleClearMusic = async () => {
    if (!project) return;
    await api.delete(`/api/music/${project.id}`);
    setMusicItems([]);
    setVolumeEnvelope([]);
  };

  const handleAddTitles = async () => {
    if (!project) return;
    setTitleLoading(true);
    try {
      const data = await api.post<{ items: typeof titleItems }>(`/api/titles/${project.id}/auto`);
      setTitleItems(data.items);
    } finally {
      setTitleLoading(false);
    }
  };

  const handleClearTitles = async () => {
    if (!project) return;
    await api.delete(`/api/titles/${project.id}`);
    setTitleItems([]);
  };

  const handleSaveTitle = async (titleId: EntityId, text: string) => {
    if (!project) return;
    updateTitleItem(titleId, { text });
    setEditingTitleId(null);
    await api.put(`/api/titles/${project.id}/items/${titleId}`, { text });
  };

  const handleAddCaptions = async () => {
    if (!project) return;
    setCaptionLoading(true);
    try {
      const data = await api.post<{ items: typeof captionItems }>(`/api/captions/${project.id}/auto`);
      setCaptionItems(data.items);
    } finally {
      setCaptionLoading(false);
    }
  };

  const handleClearCaptions = async () => {
    if (!project) return;
    await api.delete(`/api/captions/${project.id}`);
    setCaptionItems([]);
  };

  const handleSaveCaption = async (captionId: EntityId, text: string) => {
    if (!project) return;
    updateCaptionItem(captionId, { text });
    setEditingCaptionId(null);
    await api.put(`/api/captions/${project.id}/items/${captionId}`, { text });
  };

  const handleAddTimestamps = async () => {
    if (!project) return;
    setTimestampLoading(true);
    try {
      const data = await api.post<{ items: typeof timestampItems }>(`/api/timestamps/${project.id}/auto`);
      setTimestampItems(data.items);
    } finally {
      setTimestampLoading(false);
    }
  };

  const handleClearTimestamps = async () => {
    if (!project) return;
    await api.delete(`/api/timestamps/${project.id}`);
    setTimestampItems([]);
  };

  const handleSaveTimestamp = async (timestampId: EntityId, text: string) => {
    if (!project) return;
    updateTimestampItem(timestampId, { text });
    setEditingTimestampId(null);
    await api.put(`/api/timestamps/${project.id}/items/${timestampId}`, { text });
  };

  const handleAddTrackers = async () => {
    if (!project) return;
    setTrackerLoading(true);
    try {
      const data = await api.post<{ items: typeof trackerItems }>(`/api/trackers/${project.id}/auto`);
      setTrackerItems(data.items);
    } finally {
      setTrackerLoading(false);
    }
  };

  const handleClearTrackers = async () => {
    if (!project) return;
    await api.delete(`/api/trackers/${project.id}`);
    setTrackerItems([]);
  };

  const handleAddSubscribe = async () => {
    if (!project) return;
    setSubscribeLoading(true);
    try {
      const data = await api.post<{ items: typeof subscribeItems }>(`/api/subscribes/${project.id}/auto`);
      setSubscribeItems(data.items);
    } finally {
      setSubscribeLoading(false);
    }
  };

  const handleClearSubscribe = async () => {
    if (!project) return;
    await api.delete(`/api/subscribes/${project.id}`);
    setSubscribeItems([]);
  };

  const handleAddRemixes = async () => {
    if (!project) return;
    setRemixLoading(true);
    try {
      const data = await api.post<{ items: typeof timelineItems }>(`/api/remixes/${project.id}/auto`);
      setTimelineItems(data.items);
    } catch (error) {
      alert(error instanceof Error ? error.message : "Failed to generate remixes");
    } finally {
      setRemixLoading(false);
    }
  };

  const handleClearRemixes = async () => {
    if (!project) return;
    const data = await api.delete<{ items: typeof timelineItems }>(`/api/remixes/${project.id}`);
    setTimelineItems(data.items);
  };

  const trackLabels = (() => {
    const labels: { id: string; track: string; label: string; hasItems: boolean; loading: boolean; onAdd: () => void; onClear: () => void }[] = [];
    for (const row of rows) {
      if (row.id === "video-track") {
        const hasRemixes = timelineItems.some(i => i.clip_type === "remix");
        labels.push({ id: row.id, track: "remix", label: "Remixes", hasItems: hasRemixes, loading: remixLoading, onAdd: handleAddRemixes, onClear: handleClearRemixes });
      } else if (row.id === "music-track") {
        labels.push({ id: row.id, track: "music", label: "Music", hasItems: musicItems.length > 0, loading: musicLoading, onAdd: handleAddMusic, onClear: handleClearMusic });
      } else if (row.id === "title-track") {
        labels.push({ id: row.id, track: "title", label: "Titles", hasItems: titleItems.length > 0, loading: titleLoading, onAdd: handleAddTitles, onClear: handleClearTitles });
      } else if (row.id === "caption-track") {
        labels.push({ id: row.id, track: "caption", label: "Captions", hasItems: captionItems.length > 0, loading: captionLoading, onAdd: handleAddCaptions, onClear: handleClearCaptions });
      } else if (row.id === "timestamp-track") {
        labels.push({ id: row.id, track: "timestamp", label: "Timestamps", hasItems: timestampItems.length > 0, loading: timestampLoading, onAdd: handleAddTimestamps, onClear: handleClearTimestamps });
      } else if (row.id === "tracker-track") {
        labels.push({ id: row.id, track: "tracker", label: "Trackers", hasItems: trackerItems.length > 0, loading: trackerLoading, onAdd: handleAddTrackers, onClear: handleClearTrackers });
      } else if (row.id === "subscribe-track") {
        labels.push({ id: row.id, track: "subscribe", label: "Subscribe", hasItems: subscribeItems.length > 0, loading: subscribeLoading, onAdd: handleAddSubscribe, onClear: handleClearSubscribe });
      }
    }
    return labels;
  })();

  if (!project) return null;

  return (
    <div className="timeline-container">
      <div className="timeline-header">
        <h3>Timeline</h3>
        <div className="timeline-controls">
          <label className="timeline-autofit">
            <input
              type="checkbox"
              checked={autoFit}
              onChange={(e) => {
                setAutoFit(e.target.checked);
                if (e.target.checked && totalDuration > 0 && wrapperRef.current) {
                  const containerWidth = wrapperRef.current.clientWidth - 40;
                  const numTicks = totalDuration / SCALE;
                  if (numTicks > 0) {
                    setScaleWidth(Math.max(MIN_SCALE_WIDTH, Math.min(MAX_SCALE_WIDTH, containerWidth / numTicks)));
                  }
                }
              }}
            />
            Fit all
          </label>
          <span className="timeline-duration">{totalDuration.toFixed(1)}s</span>
        </div>
      </div>
      {rows[0]?.actions.length === 0 ? (
        <p className="timeline-empty">Timeline is empty. Process some clips to get started.</p>
      ) : (
        <>
        <div className="timeline-with-sidebar">
          <div className="track-sidebar">
            <div className="track-sidebar-ruler" />
            {trackLabels.map((track) => (
              <div key={track.id} className="track-sidebar-cell">
                <button
                  className={`track-sidebar-btn ${track.loading ? "loading" : ""}`}
                  data-track={track.hasItems || track.loading ? track.track : undefined}
                  onClick={track.hasItems ? track.onClear : track.onAdd}
                  disabled={track.loading || timelineItems.length === 0}
                  title={track.hasItems ? `Clear ${track.label}` : `Add ${track.label}`}
                >
                  {track.loading ? track.label : track.hasItems ? `\u00d7 ${track.label}` : `+ ${track.label}`}
                </button>
              </div>
            ))}
          </div>
          <div className="timeline-editor-wrapper" ref={wrapperRef}>
            <TimelineEditor
            ref={timelineRef}
            editorData={rows}
            effects={effects}
            scale={SCALE}
            scaleWidth={scaleWidth}
            rowHeight={50}
            style={{ height: 52 + rows.length * 50 }}
            hideCursor={false}
            autoScroll={true}
            autoReRender={false}
            onCursorDrag={handleCursorDrag}
            onClickTimeArea={handleClickTimeArea}
            getActionRender={(action) => {
              if (action.effectId === "title") {
                const t = action as unknown as TitleAction;
                if (editingTitleId === t.titleId) {
                  return (
                    <div className="tl-action-render title editing">
                      <input
                        className="title-edit-input"
                        autoFocus
                        value={editingTitleText}
                        onChange={(e) => setEditingTitleText(e.target.value)}
                        onBlur={() => handleSaveTitle(t.titleId, editingTitleText)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") handleSaveTitle(t.titleId, editingTitleText);
                          if (e.key === "Escape") setEditingTitleId(null);
                        }}
                      />
                    </div>
                  );
                }
                return (
                  <div
                    className="tl-action-render title"
                    title="Double-click to edit"
                    onDoubleClick={() => {
                      setEditingTitleId(t.titleId);
                      setEditingTitleText(t.titleText);
                    }}
                  >
                    <span className="tl-action-label">{t.titleText}</span>
                  </div>
                );
              }
              if (action.effectId === "caption") {
                const c = action as unknown as CaptionAction;
                if (editingCaptionId === c.captionId) {
                  return (
                    <div className="tl-action-render caption editing">
                      <input
                        className="caption-edit-input"
                        autoFocus
                        value={editingCaptionText}
                        onChange={(e) => setEditingCaptionText(e.target.value)}
                        onBlur={() => handleSaveCaption(c.captionId, editingCaptionText)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") handleSaveCaption(c.captionId, editingCaptionText);
                          if (e.key === "Escape") setEditingCaptionId(null);
                        }}
                      />
                    </div>
                  );
                }
                return (
                  <div
                    className="tl-action-render caption"
                    title="Double-click to edit"
                    onDoubleClick={() => {
                      setEditingCaptionId(c.captionId);
                      setEditingCaptionText(c.captionText);
                    }}
                  >
                    <span className="tl-action-label">{c.captionText}</span>
                  </div>
                );
              }
              if (action.effectId === "timestamp") {
                const ts = action as unknown as TimestampAction;
                if (editingTimestampId === ts.timestampId) {
                  return (
                    <div className="tl-action-render timestamp editing">
                      <input
                        className="timestamp-edit-input"
                        autoFocus
                        value={editingTimestampText}
                        onChange={(e) => setEditingTimestampText(e.target.value)}
                        onBlur={() => handleSaveTimestamp(ts.timestampId, editingTimestampText)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") handleSaveTimestamp(ts.timestampId, editingTimestampText);
                          if (e.key === "Escape") setEditingTimestampId(null);
                        }}
                      />
                    </div>
                  );
                }
                return (
                  <div
                    className="tl-action-render timestamp"
                    title="Double-click to edit"
                    onDoubleClick={() => {
                      setEditingTimestampId(ts.timestampId);
                      setEditingTimestampText(ts.timestampText);
                    }}
                  >
                    <span className="tl-action-label">{ts.timestampText}</span>
                  </div>
                );
              }
              if (action.effectId === "tracker") {
                const trackerAction = action as { start: number; end: number };
                return (
                  <div className="tl-action-render tracker" title="Tracker overlay">
                    <span className="tl-action-label">Tracker</span>
                    <span className="tl-action-dur">
                      {(trackerAction.end - trackerAction.start).toFixed(1)}s
                    </span>
                  </div>
                );
              }
              if (action.effectId === "music") {
                const m = action as unknown as MusicAction;
                return (
                  <div className="tl-action-render music" title={m.assetName}>
                    <span className="tl-action-label">{m.assetName}</span>
                    <span className="tl-action-dur">
                      {(m.end - m.start).toFixed(1)}s
                    </span>
                  </div>
                );
              }
              const a = action as unknown as VideoAction;
              const clipClass = a.clipType === "broll" ? "broll" : a.clipType === "remix" ? "remix" : "talking";
              return (
                <div
                  className={`tl-action-render ${clipClass}`}
                  title={a.label}
                >
                  <span className="tl-action-label">{a.label}</span>
                  <span className="tl-action-dur">
                    {(a.end - a.start).toFixed(1)}s
                  </span>
                </div>
              );
            }}
          />
          </div>
        </div>
        </>
      )}
    </div>
  );
}
