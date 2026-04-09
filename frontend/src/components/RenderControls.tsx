import { useState } from "react";
import { useTimelineStore } from "../stores/timelineStore";

export function RenderControls() {
  const { project, timelineItems, renderProgress, renderStage, setRenderProgress } =
    useTimelineStore();
  const [rendering, setRendering] = useState(false);

  if (!project || timelineItems.length === 0) return null;

  const startRender = async () => {
    setRendering(true);
    setRenderProgress(0, "starting");
    try {
      const res = await fetch(`/api/render/${project.id}`, { method: "POST" });
      if (!res.ok) {
        const data = await res.json();
        alert(data.detail || "Render failed to start");
        setRendering(false);
        setRenderProgress(null);
      }
    } catch {
      setRendering(false);
      setRenderProgress(null);
    }
  };

  const isDone = renderStage === "done" && renderProgress === 100;

  if (isDone) {
    return (
      <div className="render-controls done">
        <span className="render-status">Render complete!</span>
        <a
          href={`/api/render/${project.id}/download`}
          className="btn btn-primary"
          download
        >
          Download Video
        </a>
        <button
          className="btn btn-ghost"
          onClick={() => {
            setRenderProgress(null);
            setRendering(false);
          }}
        >
          Dismiss
        </button>
      </div>
    );
  }

  if (rendering && renderProgress != null) {
    return (
      <div className="render-controls rendering">
        <div className="render-bar-bg">
          <div
            className="render-bar-fill"
            style={{ width: `${renderProgress}%` }}
          />
        </div>
        <span className="render-status">
          {renderStage === "normalizing"
            ? "Normalizing clips..."
            : "Rendering..."}
          {" "}
          {renderProgress}%
        </span>
      </div>
    );
  }

  return (
    <div className="render-controls">
      <button className="btn btn-primary" onClick={startRender}>
        Export Video
      </button>
    </div>
  );
}
