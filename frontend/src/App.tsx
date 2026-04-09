import { ProjectList } from "./components/ProjectList";
import { ClipList } from "./components/ClipList";
import { Timeline } from "./components/Timeline";
import { VideoPlayer } from "./components/VideoPlayer";
import { RenderControls } from "./components/RenderControls";
import { useWebSocket } from "./hooks/useWebSocket";
import { useTimelineStore } from "./stores/timelineStore";
import "./App.css";

function App() {
  const project = useTimelineStore((s) => s.project);
  const setProject = useTimelineStore((s) => s.setProject);
  const setIsWatching = useTimelineStore((s) => s.setIsWatching);
  useWebSocket(project?.id ?? null);

  if (!project) {
    return (
      <div className="app">
        <header className="app-header">
          <h1>Boost Vlog</h1>
        </header>
        <main className="app-main">
          <ProjectList />
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

export default App;
