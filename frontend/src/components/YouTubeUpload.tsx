import { useEffect, useRef, useState } from "react";
import { useTimelineStore } from "../stores/timelineStore";
import { api, getStoredToken } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";

const CATEGORY_LABELS: Record<string, string> = {
  "1": "Film & Animation",
  "2": "Autos & Vehicles",
  "10": "Music",
  "15": "Pets & Animals",
  "17": "Sports",
  "20": "Gaming",
  "22": "People & Blogs",
  "23": "Comedy",
  "24": "Entertainment",
  "25": "News & Politics",
  "26": "Howto & Style",
  "27": "Education",
  "28": "Science & Technology",
};

export function YouTubeUpload() {
  const project = useTimelineStore((s) => s.project);
  const selectedTitle = useTimelineStore((s) => s.selectedTitle);
  const description = useTimelineStore((s) => s.videoDescription);
  const tags = useTimelineStore((s) => s.videoTags);
  const category = useTimelineStore((s) => s.videoCategory);
  const visibility = useTimelineStore((s) => s.videoVisibility);
  const thumbnailIndices = useTimelineStore((s) => s.selectedThumbnailIndices);
  const renderStage = useTimelineStore((s) => s.renderStage);

  const auth = useTimelineStore((s) => s.youtubeAuth);
  const setAuth = useTimelineStore((s) => s.setYoutubeAuth);
  const uploadProgress = useTimelineStore((s) => s.youtubeUploadProgress);
  const setUploadProgress = useTimelineStore((s) => s.setYoutubeUploadProgress);
  const uploadResult = useTimelineStore((s) => s.youtubeUploadResult);
  const setUploadResult = useTimelineStore((s) => s.setYoutubeUploadResult);
  const uploadError = useTimelineStore((s) => s.youtubeUploadError);
  const setUploadError = useTimelineStore((s) => s.setYoutubeUploadError);

  const thumbnailUrls = useTimelineStore((s) => s.thumbnailUrls);

  const [connecting, setConnecting] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Check auth status on mount
  useEffect(() => {
    checkAuth();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  // Fetch authenticated blob URL for video preview when dialog opens
  useEffect(() => {
    if (!showConfirm || !project) return;

    let objectUrl: string | null = null;
    const token = getStoredToken();

    fetch(`/api/render/${project.id}/download`, {
      headers: token ? { "X-FlowCut-Token": token } : {},
    })
      .then((res) => {
        if (!res.ok) throw new Error("Preview unavailable");
        return res.blob();
      })
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob);
        setPreviewUrl(objectUrl);
      })
      .catch(() => {
        setPreviewUrl(null);
      });

    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      setPreviewUrl(null);
    };
  }, [showConfirm, project]);

  // Reset uploading state when done or error
  useEffect(() => {
    if (uploadResult || uploadError) {
      setUploading(false);
    }
  }, [uploadResult, uploadError]);

  const checkAuth = async () => {
    try {
      const data = await api.get<{ authenticated: boolean; channel_name: string | null }>(
        "/api/youtube/status"
      );
      setAuth({ authenticated: data.authenticated, channelName: data.channel_name });
    } catch {}
  };

  const connect = async () => {
    setConnecting(true);
    try {
      const data = await api.get<{ auth_url: string }>("/api/youtube/auth");

      // Open OAuth popup
      window.open(data.auth_url, "_blank", "width=600,height=700");

      // Poll for auth completion every 2s
      pollRef.current = setInterval(async () => {
        try {
          const status = await api.get<{ authenticated: boolean; channel_name: string | null }>(
            "/api/youtube/status"
          );
          if (status.authenticated) {
            if (pollRef.current) clearInterval(pollRef.current);
            pollRef.current = null;
            setAuth({ authenticated: true, channelName: status.channel_name });
            setConnecting(false);
          }
        } catch {}
      }, 2000);

      // Stop polling after 5 minutes
      setTimeout(() => {
        if (pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setConnecting(false);
        }
      }, 300000);
    } catch {
      setConnecting(false);
    }
  };

  const disconnect = async () => {
    try {
      await api.post("/api/youtube/disconnect");
    } catch {}
    setAuth({ authenticated: false, channelName: null });
  };

  const upload = async () => {
    if (!project || !selectedTitle) return;
    setShowConfirm(false);
    setUploading(true);
    setUploadProgress(null);
    setUploadResult(null);
    setUploadError(null);
    try {
      await api.post(`/api/youtube/upload/${project.id}`, {
        title: selectedTitle,
        description,
        tags,
        category_id: category,
        privacy_status: visibility,
        thumbnail_index: thumbnailIndices[0] ?? null,
      });
      // Progress comes via WebSocket → youtubeUploadProgress in store
    } catch (e: any) {
      setUploadError(e.message || "Upload failed");
      setUploading(false);
    }
  };

  const hasRender = renderStage === "done" || !!project?.render_path;

  const canUpload =
    auth.authenticated &&
    hasRender &&
    !!selectedTitle &&
    !uploading &&
    !uploadResult;

  if (!selectedTitle) return null;

  return (
    <div className="space-y-3">
      <p className="text-sm font-medium">Publish</p>

      {/* Auth section */}
      <div>
        {auth.authenticated ? (
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-green-500 inline-block" />
              <span className="text-sm text-muted-foreground">
                Connected as <strong>{auth.channelName}</strong>
              </span>
            </div>
            <Button variant="ghost" size="sm" onClick={disconnect}>
              Disconnect
            </Button>
          </div>
        ) : (
          <Button variant="default" size="sm" onClick={connect} disabled={connecting}>
            {connecting ? "Waiting for authorization..." : "Connect YouTube"}
          </Button>
        )}
      </div>

      {/* Upload section */}
      {auth.authenticated && (
        <div className="space-y-3">
          {!hasRender ? (
            <p className="text-xs text-muted-foreground">
              Export your video first before publishing.
            </p>
          ) : (
            <>
              <Button
                variant="default"
                size="sm"
                onClick={() => setShowConfirm(true)}
                disabled={!canUpload}
              >
                {uploading ? "Publishing..." : "Publish to YouTube"}
              </Button>

              {uploadProgress !== null && !uploadResult && (
                <div className="space-y-1">
                  <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
                    <div
                      className="h-full rounded-full bg-primary transition-all duration-500"
                      style={{ width: `${uploadProgress}%` }}
                    />
                  </div>
                  <p className="text-xs text-muted-foreground">{uploadProgress}% uploaded</p>
                </div>
              )}

              {uploadResult && (
                <Alert>
                  <AlertDescription className="space-y-2">
                    <div className="flex items-center gap-2">
                      <Badge variant="default">Published</Badge>
                    </div>
                    <a
                      href={uploadResult.videoUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-primary underline underline-offset-2 break-all"
                    >
                      {uploadResult.videoUrl}
                    </a>
                    <div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => navigator.clipboard.writeText(uploadResult.videoUrl)}
                      >
                        Copy Link
                      </Button>
                    </div>
                  </AlertDescription>
                </Alert>
              )}

              {uploadError && (
                <Alert variant="destructive">
                  <AlertDescription className="flex items-center justify-between gap-2">
                    <span>{uploadError}</span>
                    <Button variant="outline" size="sm" onClick={upload}>
                      Retry
                    </Button>
                  </AlertDescription>
                </Alert>
              )}
            </>
          )}
        </div>
      )}

      {/* Confirmation Dialog */}
      <Dialog open={showConfirm} onOpenChange={setShowConfirm}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Confirm Publish to YouTube</DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-2">
            {/* Video preview */}
            {previewUrl ? (
              <video
                className="w-full rounded-md border"
                src={previewUrl}
                controls
              />
            ) : (
              <div className="w-full h-32 rounded-md border bg-muted flex items-center justify-center">
                <span className="text-xs text-muted-foreground">Loading preview...</span>
              </div>
            )}

            <Separator />

            {/* Title */}
            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                Title
              </p>
              <p className="text-sm">{selectedTitle}</p>
            </div>

            {/* Thumbnails */}
            {thumbnailIndices.length > 0 && (
              <div className="space-y-1">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Thumbnail
                </p>
                <div className="flex flex-wrap gap-2">
                  {thumbnailIndices.map((idx) =>
                    thumbnailUrls[idx] ? (
                      <img
                        key={idx}
                        src={thumbnailUrls[idx]}
                        alt={`Thumbnail ${idx + 1}`}
                        className="h-16 rounded border object-cover"
                      />
                    ) : null
                  )}
                </div>
              </div>
            )}

            {/* Description */}
            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                Description
              </p>
              <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                {description || "(none)"}
              </p>
            </div>

            {/* Tags */}
            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                Tags
              </p>
              <p className="text-sm">{tags.length ? tags.join(", ") : "(none)"}</p>
            </div>

            {/* Category + Visibility row */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Category
                </p>
                <p className="text-sm">{CATEGORY_LABELS[category] || category}</p>
              </div>
              <div className="space-y-1">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Visibility
                </p>
                <p className="text-sm">
                  {visibility.charAt(0).toUpperCase() + visibility.slice(1)}
                </p>
              </div>
            </div>

            {/* Channel */}
            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                Channel
              </p>
              <p className="text-sm">{auth.channelName}</p>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowConfirm(false)}>
              Cancel
            </Button>
            <Button variant="default" onClick={upload}>
              Publish
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
