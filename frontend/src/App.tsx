import { useState } from "react";
import { ProjectList } from "./components/ProjectList";
import { Settings } from "./components/Settings";
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
  const [showSettings, setShowSettings] = useState(false);
  useWebSocket(project?.id ?? null);
  useAutoSaveMetadata();

  if (!project) {
    return (
      <div className="app">
        <header className="app-header">
          <h1>Boost Vlog</h1>
          <button
            className="btn btn-ghost settings-btn"
            onClick={() => setShowSettings(true)}
            title="Settings"
          >
            Settings
          </button>
        </header>
        {showSettings && <Settings onClose={() => setShowSettings(false)} />}
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
          <SaveIndicator />
          <button
            className="btn btn-ghost"
            onClick={() => setProject(null)}
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
