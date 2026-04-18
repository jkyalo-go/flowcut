import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useTimelineStore } from "../stores/timelineStore";

export function ThumbnailGenerator() {
  const project = useTimelineStore((s) => s.project);
  const selectedTitle = useTimelineStore((s) => s.selectedTitle);

  const thumbnailText = useTimelineStore((s) => s.thumbnailText);
  const setThumbnailText = useTimelineStore((s) => s.setThumbnailText);
  const thumbnailUrls = useTimelineStore((s) => s.thumbnailUrls);
  const setThumbnailUrls = useTimelineStore((s) => s.setThumbnailUrls);
  const selectedIndices = useTimelineStore((s) => s.selectedThumbnailIndices);
  const setSelectedIndices = useTimelineStore((s) => s.setSelectedThumbnailIndices);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const isFirstMount = useRef(true);
  const [lastTitle, setLastTitle] = useState<string | null>(null);

  const selectedSet = new Set(selectedIndices);

  const toggleSelect = (idx: number) => {
    if (selectedSet.has(idx)) {
      setSelectedIndices([]);
    } else {
      setSelectedIndices([idx]);
    }
  };

  const doGenerate = async (title: string) => {
    if (!project || !title.trim()) return;
    setLoading(true);
    setError("");
    try {
      const data = await api.post<{ thumbnail_urls: string[] }>(`/api/projects/${project.id}/generate-thumbnails`, {
        title: title.trim(),
        skip_indices: [],
      });
      const t = Date.now();
      setThumbnailUrls(data.thumbnail_urls.map((u: string) => u + "?t=" + t));
      setSelectedIndices([]);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Failed to generate thumbnails");
    } finally {
      setLoading(false);
    }
  };

  const regenerate = async () => {
    if (!project || !thumbnailText.trim()) return;
    setLoading(true);
    setError("");
    try {
      const data = await api.post<{ thumbnail_urls: string[] }>(`/api/projects/${project.id}/generate-thumbnails`, {
          title: thumbnailText.trim(),
          skip_indices: selectedIndices,
      });
      const t = Date.now();
      setThumbnailUrls(
        data.thumbnail_urls.map((u: string, i: number) =>
          selectedSet.has(i)
            ? (thumbnailUrls[i] || u + "?t=" + t)
            : u + "?t=" + t
        )
      );
    } catch (error) {
      setError(error instanceof Error ? error.message : "Failed to generate thumbnails");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!selectedTitle || selectedTitle === lastTitle) return;
    if (isFirstMount.current) {
      isFirstMount.current = false;
      setLastTitle(selectedTitle);
      return;
    }
    setThumbnailText(selectedTitle);
    setLastTitle(selectedTitle);
  }, [lastTitle, selectedTitle, setThumbnailText]);

  if (!selectedTitle) return null;

  return (
    <div className="thumbnail-generator">
      <div className="thumbnail-generator-header">
        <h3>Thumbnails</h3>
        <span className="thumbnail-count">{selectedIndices.length ? "1 selected" : "None selected"}</span>
        <button
          className="btn btn-primary"
          onClick={() => {
            if (thumbnailUrls.length > 0) {
              regenerate();
              return;
            }
            void doGenerate(thumbnailText || selectedTitle);
          }}
          disabled={loading || !thumbnailText.trim()}
        >
          {loading ? "Generating..." : thumbnailUrls.length ? "Regenerate" : "Generate Thumbnails"}
        </button>
      </div>
      <div className="thumbnail-text-edit">
        <label>Thumbnail text</label>
        <input
          type="text"
          className="custom-title-input"
          value={thumbnailText}
          onChange={(e) => setThumbnailText(e.target.value)}
          placeholder="Text to display on thumbnail..."
        />
      </div>
      {error && <span className="error">{error}</span>}
      {thumbnailUrls.length > 0 && (
        <div className="thumbnail-grid">
          {thumbnailUrls.map((url, i) => {
            const isSelected = selectedSet.has(i);
            return (
              <button
                type="button"
                key={i}
                className={`thumbnail-preview ${isSelected ? "selected" : ""}`}
                onClick={() => toggleSelect(i)}
                aria-pressed={isSelected}
              >
                <img src={url} alt={`Thumbnail option ${i + 1}`} />
                <div className={`thumbnail-checkbox ${isSelected ? "checked" : ""}`}>
                  {isSelected && (
                    <>
                      <span className="thumbnail-check-icon">{"\u2713"}</span>
                      <span className="thumbnail-lock-icon">{"\u{1F512}"}</span>
                    </>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
