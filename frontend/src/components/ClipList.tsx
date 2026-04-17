import { useTimelineStore } from "../stores/timelineStore";
import type { Clip } from "../types";

const STATUS_LABELS: Record<string, string> = {
  pending: "Pending",
  transcribing: "Transcribing",
  classifying: "Classifying",
  processing: "Processing",
  done: "Done",
  error: "Error",
};

const STATUS_COLORS: Record<string, string> = {
  pending: "#888",
  transcribing: "#f59e0b",
  classifying: "#f59e0b",
  processing: "#3b82f6",
  done: "#10b981",
  error: "#ef4444",
};

export function ClipList() {
  const clips = useTimelineStore((s) => s.clips);

  if (clips.length === 0) {
    return (
      <div className="clip-list empty">
        <p>No clips yet. Upload a video to get started.</p>
      </div>
    );
  }

  return (
    <div className="clip-list">
      <h3>Clips ({clips.length})</h3>
      <div className="clip-items">
        {clips.map((clip) => (
          <ClipCard key={clip.id} clip={clip} />
        ))}
      </div>
    </div>
  );
}

function ClipCard({ clip }: { clip: Clip }) {
  const filename = clip.source_path.split("/").pop() || "Unknown";
  const isProcessing = ["pending", "transcribing", "classifying", "processing"].includes(clip.status);
  const progress = clip.progress ?? 0;

  return (
    <div className={`clip-card ${clip.status}`}>
      <div className="clip-header">
        <span className="clip-filename" title={clip.source_path}>
          {filename}
        </span>
        <span
          className="clip-badge"
          style={{ backgroundColor: STATUS_COLORS[clip.status] }}
        >
          {STATUS_LABELS[clip.status]}
        </span>
      </div>
      {clip.clip_type && (
        <span className={`clip-type ${clip.clip_type}`}>
          {clip.clip_type === "talking" ? "Talking" : "B-Roll"}
        </span>
      )}
      {clip.duration != null && clip.status === "done" && (
        <span className="clip-duration">{clip.duration.toFixed(1)}s</span>
      )}
      {clip.clip_type === "broll" && clip.sub_clips.length > 0 && (
        <span className="clip-sub-count">{clip.sub_clips.length} moments</span>
      )}
      {isProcessing && (
        <div className="clip-progress">
          <div className="clip-progress-bar">
            <div
              className="clip-progress-fill"
              style={{
                width: `${progress}%`,
                backgroundColor: STATUS_COLORS[clip.status],
              }}
            />
          </div>
          <div className="clip-progress-info">
            <span className="clip-progress-detail">
              {clip.progressDetail || STATUS_LABELS[clip.status]}
            </span>
            <span className="clip-progress-pct">{progress}%</span>
          </div>
        </div>
      )}
      {clip.status === "error" && (
        <p className="clip-error">{clip.error_message || "Unknown error"}</p>
      )}
    </div>
  );
}
