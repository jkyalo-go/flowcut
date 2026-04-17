import { useState } from "react";
import { useTimelineStore } from "../stores/timelineStore";
import { api, getStoredToken } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";

const STAGE_LABELS: Record<string, string> = {
  starting: "Starting...",
  initializing: "Initializing...",
  bundling: "Bundling assets...",
  rendering: "Rendering video...",
  done: "Complete",
};

export function RenderControls() {
  const { project, timelineItems, renderProgress, renderStage, setRenderProgress, setProject } =
    useTimelineStore();
  const [renderError, setRenderError] = useState<string | null>(null);

  if (!project || timelineItems.length === 0) return null;

  const isDone = renderStage === "done" && renderProgress === 100;
  const rendering = renderProgress != null && !isDone;
  const hasRender = isDone || !!project.render_path;

  const startRender = async () => {
    setRenderError(null);
    setRenderProgress(0, "starting");
    try {
      await api.post(`/api/render/${project.id}`);
    } catch (e: any) {
      setRenderError(e.message || "Render failed to start");
      setRenderProgress(null);
    }
  };

  const handleDownload = async () => {
    if (!project) return;
    const token = getStoredToken();
    try {
      const res = await fetch(`/api/render/${project.id}/download`, {
        headers: token ? { "X-FlowCut-Token": token } : {},
      });
      if (!res.ok) throw new Error(`Download failed: HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${project.name || project.id}_render.mp4`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      setRenderError(e.message || "Download failed");
    }
  };

  const handleReveal = async () => {
    if (!project) return;
    try {
      await api.post(`/api/render/${project.id}/reveal`);
    } catch (e: any) {
      setRenderError(e.message || "Could not reveal file in Finder");
    }
  };

  const handleDismiss = () => {
    setProject({ ...project, render_path: `project_${project.id}_render.mp4` });
    setRenderProgress(null);
    setRenderError(null);
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium">Export</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {renderError && (
          <Alert variant="destructive">
            <AlertDescription>{renderError}</AlertDescription>
          </Alert>
        )}

        {rendering && renderProgress != null && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              {renderStage && (
                <Badge variant="secondary" className="text-xs">
                  {STAGE_LABELS[renderStage] ?? renderStage}
                </Badge>
              )}
              <span className="text-xs text-muted-foreground ml-auto">
                {renderProgress}%
              </span>
            </div>
            <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
              <div
                className="h-full rounded-full bg-primary transition-all duration-500"
                style={{ width: `${renderProgress}%` }}
              />
            </div>
          </div>
        )}

        {hasRender && !rendering && (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Badge variant="default" className="text-xs">
                {isDone ? "Render complete" : "Previously exported"}
              </Badge>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" onClick={handleDownload}>
                Download
              </Button>
              <Button variant="outline" size="sm" onClick={handleReveal}>
                Open in Finder
              </Button>
              <Button variant="default" size="sm" onClick={startRender}>
                Re-export
              </Button>
              {isDone && (
                <Button variant="ghost" size="sm" onClick={handleDismiss}>
                  Dismiss
                </Button>
              )}
            </div>
          </div>
        )}

        {!hasRender && !rendering && (
          <Button variant="default" size="sm" onClick={startRender}>
            Export Video
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
