import { ProjectList } from "./components/ProjectList";
import { ClipList } from "./components/ClipList";
import { AssetLibrary } from "./components/AssetLibrary";
import { Timeline } from "./components/Timeline";
import { VideoPlayer } from "./components/VideoPlayer";
import { RenderControls } from "./components/RenderControls";
import { TitleSuggestions } from "./components/TitleSuggestions";
import { ThumbnailGenerator } from "./components/ThumbnailGenerator";
import { VideoMetadata } from "./components/VideoMetadata";
import { YouTubeUpload } from "./components/YouTubeUpload";
import { useWebSocket } from "./hooks/useWebSocket";
import { useAutoSaveMetadata } from "./hooks/useAutoSaveMetadata";
import { useTimelineStore } from "./stores/timelineStore";
import "./App.css";

function App() {
  const project = useTimelineStore((s) => s.project);
  const setProject = useTimelineStore((s) => s.setProject);
  const setIsWatching = useTimelineStore((s) => s.setIsWatching);
  useWebSocket(project?.id ?? null);
  useAutoSaveMetadata();

  if (!project) {
    return (
      <div className="app">
        <header className="app-header">
          <h1>Boost Vlog</h1>
        </header>
        <main className="app-main">
          <div className="home-layout">
            <aside className="home-sidebar">
              <AssetLibrary />
            </aside>
            <div className="home-primary">
              <ProjectList />
            </div>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Boost Vlog</h1>
        <div className="header-project">
          <span className="header-project-name">{project.name}</span>
          <span className="header-project-dir">{project.watch_directory}</span>
          <WatchToggle />
          <SaveIndicator />
          <button
            className="btn btn-ghost"
            onClick={() => {
              setProject(null);
              setIsWatching(false);
            }}
          >
            Back to Projects
          </button>
        </div>
      </header>
      <main className="app-main">
        <div className="main-layout">
          <aside className="sidebar">
            <ClipList />
          </aside>
          <section className="content">
            <VideoPlayer />
            <Timeline />
            <RenderControls />
            <TitleSuggestions />
            <ThumbnailGenerator />
            <VideoMetadata />
            <YouTubeUpload />
          </section>
        </div>
      </main>
    </div>
  );
}

function WatchToggle() {
  const project = useTimelineStore((s) => s.project);
  const isWatching = useTimelineStore((s) => s.isWatching);
  const setIsWatching = useTimelineStore((s) => s.setIsWatching);

  const toggle = async () => {
    if (!project) return;
    const action = isWatching ? "stop" : "start";
    await fetch(`/api/projects/${project.id}/watch/${action}`, { method: "POST" });
    setIsWatching(!isWatching);
  };

  return (
    <button
      className={`watch-toggle ${isWatching ? "on" : "off"}`}
      onClick={toggle}
      title={isWatching ? "Watching folder" : "Not watching folder"}
    >
      <span className="watch-toggle-dot" />
      <span className="watch-toggle-label">{isWatching ? "Watching" : "Paused"}</span>
    </button>
  );
}

function SaveIndicator() {
  const saveStatus = useTimelineStore((s) => s.saveStatus);
  if (saveStatus === "idle") return null;
  return (
    <span className={`save-indicator ${saveStatus}`}>
      {saveStatus === "saving" ? "Saving..." : "Saved"}
    </span>
  );
}

export default App;
