import { useTimelineStore } from "../stores/timelineStore";

export function RenderControls() {
  const { project, timelineItems, renderProgress, renderStage, setRenderProgress, setProject } =
    useTimelineStore();

  if (!project || timelineItems.length === 0) return null;

  const startRender = async () => {
    setRenderProgress(0, "starting");
    try {
      const res = await fetch(`/api/render/${project.id}`, { method: "POST" });
      if (!res.ok) {
        const data = await res.json();
        alert(data.detail || "Render failed to start");
        setRenderProgress(null);
      }
    } catch {
      setRenderProgress(null);
    }
  };

  const isDone = renderStage === "done" && renderProgress === 100;
  const rendering = renderProgress != null && !isDone;
  const hasRender = isDone || project.render_path;

  if (hasRender && !rendering) {
    return (
      <div className="render-controls done">
        <video
          className="render-preview"
          src={`/api/render/${project.id}/download`}
          controls
        />
        <div className="render-actions">
          <span className="render-status">
            {isDone ? "Render complete!" : "Previously exported"}
          </span>
          <button className="btn btn-primary" onClick={startRender}>
            Re-export
          </button>
          <button
            className="btn btn-ghost"
            onClick={() => fetch(`/api/render/${project.id}/reveal`, { method: "POST" })}
          >
            Open in Finder
          </button>
          {isDone && (
            <button
              className="btn btn-ghost"
              onClick={() => {
                // Update project in store so render_path is set for future reference
                setProject({ ...project, render_path: `project_${project.id}_render.mp4` });
                setRenderProgress(null);
              }}
            >
              Dismiss
            </button>
          )}
        </div>
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
          {renderStage === "initializing"
            ? "Initializing..."
            : renderStage === "mixing music"
            ? "Mixing music..."
            : "Rendering..."}{" "}
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
