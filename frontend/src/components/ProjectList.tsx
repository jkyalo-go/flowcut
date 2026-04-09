import { useEffect, useState } from "react";
import { useTimelineStore } from "../stores/timelineStore";
import type { Project } from "../types";

export function ProjectList() {
  const { setProject, setClips, setTimelineItems, setIsWatching } = useTimelineStore();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [dir, setDir] = useState("");
  const [creating, setCreating] = useState(false);
  const [browsing, setBrowsing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchProjects();
  }, []);

  const fetchProjects = async () => {
    try {
      const res = await fetch("/api/projects");
      if (res.ok) setProjects(await res.json());
    } catch {} finally {
      setLoading(false);
    }
  };

  const openProject = async (id: number) => {
    const fullRes = await fetch(`/api/projects/${id}`);
    const proj = await fullRes.json();
    const watchRes = await fetch(`/api/projects/${id}/watch/start`, { method: "POST" });
    const watchData = await watchRes.json();
    setProject(proj);
    setClips(watchData.clips || proj.clips || []);
    const tlRes = await fetch(`/api/timeline/${id}`);
    if (tlRes.ok) setTimelineItems(await tlRes.json());
    setIsWatching(true);
  };

  const browse = async () => {
    setBrowsing(true);
    try {
      const res = await fetch("/api/fs/pick-folder");
      const data = await res.json();
      if (data.path && !data.cancelled) {
        setDir(data.path.replace(/\/$/, ""));
      }
    } catch {} finally {
      setBrowsing(false);
    }
  };

  const createProject = async () => {
    if (!name.trim() || !dir.trim()) return;
    setCreating(true);
    setError("");
    try {
      const res = await fetch("/api/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim(), watch_directory: dir.trim() }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to create project");
      }
      const proj = await res.json();
      const watchRes = await fetch(`/api/projects/${proj.id}/watch/start`, { method: "POST" });
      const watchData = await watchRes.json();
      setProject(proj);
      setClips(watchData.clips || []);
      setTimelineItems([]);
      setIsWatching(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setCreating(false);
    }
  };

  const deleteProject = async (e: React.MouseEvent, id: number, projectName: string) => {
    e.stopPropagation();
    if (!confirm(`Delete "${projectName}"? This cannot be undone.`)) return;
    await fetch(`/api/projects/${id}`, { method: "DELETE" });
    setProjects(projects.filter((p) => p.id !== id));
  };

  if (loading) {
    return <div className="project-list-loading">Loading projects...</div>;
  }

  return (
    <div className="project-list">
      <h2>Projects</h2>
      <div className="project-grid">
        {projects.map((p) => (
          <div key={p.id} className="project-card" onClick={() => openProject(p.id)}>
            <div className="project-card-header">
              <h3>{p.name}</h3>
              <button
                className="project-card-delete"
                onClick={(e) => deleteProject(e, p.id, p.name)}
                title="Delete project"
              >
                x
              </button>
            </div>
            <span className="project-card-dir">{p.watch_directory}</span>
            <span className="project-card-clips">{p.clips.length} clips</span>
          </div>
        ))}
        {!showForm ? (
          <div className="project-card new-project-card" onClick={() => setShowForm(true)}>
            <span className="new-project-icon">+</span>
            <span>New Project</span>
          </div>
        ) : (
          <div className="project-card new-project-form">
            <input
              type="text"
              placeholder="Project name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoFocus
            />
            <div className="folder-input-row">
              <input
                type="text"
                placeholder="Watch folder"
                value={dir}
                onChange={(e) => setDir(e.target.value)}
                readOnly={browsing}
              />
              <button className="btn btn-ghost" onClick={browse} disabled={browsing}>
                {browsing ? "..." : "Browse"}
              </button>
            </div>
            <div className="btn-row">
              <button className="btn btn-primary" onClick={createProject} disabled={creating}>
                {creating ? "Creating..." : "Create"}
              </button>
              <button className="btn btn-ghost" onClick={() => { setShowForm(false); setError(""); }}>
                Cancel
              </button>
            </div>
            {error && <p className="error">{error}</p>}
          </div>
        )}
      </div>
    </div>
  );
}
