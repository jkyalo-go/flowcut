import { useState } from "react";
import { api } from "@/lib/api";
import { useTimelineStore } from "../stores/timelineStore";

const YOUTUBE_CATEGORIES = [
  { id: "1", label: "Film & Animation" },
  { id: "2", label: "Autos & Vehicles" },
  { id: "10", label: "Music" },
  { id: "15", label: "Pets & Animals" },
  { id: "17", label: "Sports" },
  { id: "20", label: "Gaming" },
  { id: "22", label: "People & Blogs" },
  { id: "23", label: "Comedy" },
  { id: "24", label: "Entertainment" },
  { id: "25", label: "News & Politics" },
  { id: "26", label: "Howto & Style" },
  { id: "27", label: "Education" },
  { id: "28", label: "Science & Technology" },
];

const VISIBILITY_OPTIONS = ["public", "unlisted", "private"] as const;

export function VideoMetadata() {
  const project = useTimelineStore((s) => s.project);
  const selectedTitle = useTimelineStore((s) => s.selectedTitle);

  const description = useTimelineStore((s) => s.videoDescription);
  const setDescription = useTimelineStore((s) => s.setVideoDescription);
  const tags = useTimelineStore((s) => s.videoTags);
  const setTags = useTimelineStore((s) => s.setVideoTags);
  const category = useTimelineStore((s) => s.videoCategory);
  const setCategory = useTimelineStore((s) => s.setVideoCategory);
  const visibility = useTimelineStore((s) => s.videoVisibility);
  const setVisibility = useTimelineStore((s) => s.setVideoVisibility);

  const [tagInput, setTagInput] = useState("");
  const [loadingDesc, setLoadingDesc] = useState(false);
  const [loadingTags, setLoadingTags] = useState(false);
  const [error, setError] = useState("");
  const [showPrompt, setShowPrompt] = useState(false);
  const descSystemPrompt = useTimelineStore((s) => s.descSystemPrompt);
  const setDescSystemPrompt = useTimelineStore((s) => s.setDescSystemPrompt);

  const title = selectedTitle || "";

  const generateDescription = async () => {
    if (!project || !title) return;
    setLoadingDesc(true);
    setError("");
    try {
      const data = await api.post<{ description: string }>(`/api/projects/${project.id}/generate-description`, {
        title,
        system_prompt: descSystemPrompt,
      });
      setDescription(data.description);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Failed to generate description");
    } finally {
      setLoadingDesc(false);
    }
  };

  const generateTags = async () => {
    if (!project || !title) return;
    setLoadingTags(true);
    setError("");
    try {
      const data = await api.post<{ tags: string[] }>(`/api/projects/${project.id}/generate-tags`, { title });
      setTags(data.tags);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Failed to generate tags");
    } finally {
      setLoadingTags(false);
    }
  };

  const addTag = () => {
    const t = tagInput.trim();
    if (t && !tags.includes(t)) {
      setTags([...tags, t]);
    }
    setTagInput("");
  };

  const removeTag = (idx: number) => {
    setTags(tags.filter((_, i) => i !== idx));
  };

  if (!selectedTitle) return null;

  return (
    <div className="video-metadata">
      <h3>Video Metadata</h3>

      {error && <span className="error">{error}</span>}

      {/* Description */}
      <div className="metadata-field">
        <div className="metadata-field-header">
          <label>Description</label>
          <div className="metadata-field-actions">
            <button
              className={`btn btn-ghost btn-sm ${showPrompt ? "active" : ""}`}
              onClick={() => setShowPrompt(!showPrompt)}
              title="Edit system prompt"
            >
              System Prompt
            </button>
            <button
              className="btn btn-primary btn-sm"
              onClick={generateDescription}
              disabled={loadingDesc}
            >
              {loadingDesc ? "Generating..." : description ? "Regenerate" : "Generate"}
            </button>
          </div>
        </div>
        {showPrompt && (
          <textarea
            className="metadata-textarea prompt-editor"
            value={descSystemPrompt}
            onChange={(e) => setDescSystemPrompt(e.target.value)}
            rows={5}
          />
        )}
        <textarea
          className="metadata-textarea"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Video description..."
          rows={6}
        />
      </div>

      {/* Tags */}
      <div className="metadata-field">
        <div className="metadata-field-header">
          <label>Tags</label>
          <button
            className="btn btn-primary btn-sm"
            onClick={generateTags}
            disabled={loadingTags}
          >
            {loadingTags ? "Generating..." : tags.length ? "Regenerate" : "Generate"}
          </button>
        </div>
        <div className="tags-container">
          {tags.map((tag, i) => (
            <span key={i} className="tag-chip">
              {tag}
              <button className="tag-remove" onClick={() => removeTag(i)}>&times;</button>
            </span>
          ))}
        </div>
        <div className="tag-input-row">
          <input
            type="text"
            className="custom-title-input"
            value={tagInput}
            onChange={(e) => setTagInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addTag();
              }
            }}
            placeholder="Add a tag..."
          />
          <button className="btn btn-ghost" onClick={addTag} disabled={!tagInput.trim()}>
            Add
          </button>
        </div>
      </div>

      {/* Category */}
      <div className="metadata-field">
        <label>Category</label>
        <select
          className="metadata-select"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          {YOUTUBE_CATEGORIES.map((c) => (
            <option key={c.id} value={c.id}>{c.label}</option>
          ))}
        </select>
      </div>

      {/* Visibility */}
      <div className="metadata-field">
        <label>Visibility</label>
        <div className="visibility-options">
          {VISIBILITY_OPTIONS.map((v) => (
            <button
              key={v}
              className={`visibility-btn ${visibility === v ? "active" : ""}`}
              onClick={() => setVisibility(v)}
            >
              {v.charAt(0).toUpperCase() + v.slice(1)}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
