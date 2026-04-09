import asyncio
import logging
import os
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from database import SessionLocal
from models import Clip, ProcessingStatus
from routes.ws import broadcast
from config import VIDEO_EXTENSIONS

logger = logging.getLogger(__name__)

_active_observers: dict[int, Observer] = {}
_processing_queue: asyncio.Queue | None = None
_main_loop: asyncio.AbstractEventLoop | None = None


def set_queue(queue: asyncio.Queue):
    global _processing_queue, _main_loop
    _processing_queue = queue
    _main_loop = asyncio.get_running_loop()


class VideoFileHandler(FileSystemEventHandler):
    def __init__(self, project_id: int, loop: asyncio.AbstractEventLoop):
        self.project_id = project_id
        self.loop = loop

    def _maybe_handle(self, path: str, event_type: str):
        ext = Path(path).suffix.lower()
        logger.info(f"[WATCHER] {event_type}: {path} (ext={ext}, is_video={ext in VIDEO_EXTENSIONS})")
        if ext in VIDEO_EXTENSIONS:
            asyncio.run_coroutine_threadsafe(
                self._handle_new_file(path), self.loop
            )

    def on_created(self, event):
        if not event.is_directory:
            self._maybe_handle(event.src_path, "CREATED")

    def on_modified(self, event):
        if not event.is_directory:
            self._maybe_handle(event.src_path, "MODIFIED")

    def on_moved(self, event):
        if not event.is_directory:
            self._maybe_handle(event.dest_path, "MOVED")

    async def _handle_new_file(self, path: str):
        logger.info(f"[WATCHER] Waiting for stable size: {path}")
        await _wait_for_stable_size(path)
        logger.info(f"[WATCHER] File stable, checking DB: {path}")

        db = SessionLocal()
        try:
            existing = db.query(Clip).filter(
                Clip.source_path == path, Clip.project_id == self.project_id
            ).first()
            if existing:
                logger.info(f"[WATCHER] Already in DB, skipping: {path}")
                return

            clip = Clip(
                project_id=self.project_id,
                source_path=path,
                status=ProcessingStatus.PENDING,
            )
            db.add(clip)
            db.commit()
            db.refresh(clip)

            await broadcast(self.project_id, "clip_detected", {
                "clip_id": clip.id,
                "filename": Path(path).name,
            })

            if _processing_queue:
                await _processing_queue.put(clip.id)
        finally:
            db.close()


async def _wait_for_stable_size(path: str, interval: float = 1.0, checks: int = 3):
    prev_size = -1
    stable_count = 0
    while stable_count < checks:
        await asyncio.sleep(interval)
        try:
            current_size = os.path.getsize(path)
        except OSError:
            return
        if current_size == prev_size:
            stable_count += 1
        else:
            stable_count = 0
        prev_size = current_size


def start_watching(project_id: int, directory: str) -> list[int]:
    """Start watching a directory. Returns list of newly created clip IDs from existing files."""
    clip_ids = _scan_existing(project_id, directory)
    logger.info(f"[WATCHER] start_watching project={project_id} dir={directory} existing_clips={len(clip_ids)} active_observers={list(_active_observers.keys())}")

    if project_id not in _active_observers:
        loop = _main_loop or asyncio.get_event_loop()
        handler = VideoFileHandler(project_id, loop)
        observer = Observer()
        observer.schedule(handler, directory, recursive=False)
        observer.start()
        _active_observers[project_id] = observer

    # Queue clips for processing (async, fire-and-forget)
    if clip_ids and _processing_queue and _main_loop:
        asyncio.run_coroutine_threadsafe(_queue_clips(clip_ids), _main_loop)

    return clip_ids


def _scan_existing(project_id: int, directory: str) -> list[int]:
    """Scan directory for video files, create Clip rows. Returns new clip IDs."""
    db = SessionLocal()
    new_ids = []
    try:
        for entry in Path(directory).iterdir():
            if entry.is_file() and entry.suffix.lower() in VIDEO_EXTENSIONS:
                path = str(entry)
                existing = db.query(Clip).filter(
                    Clip.source_path == path, Clip.project_id == project_id
                ).first()
                if existing:
                    continue
                clip = Clip(
                    project_id=project_id,
                    source_path=path,
                    status=ProcessingStatus.PENDING,
                )
                db.add(clip)
                db.commit()
                db.refresh(clip)
                new_ids.append(clip.id)
    finally:
        db.close()
    return new_ids


async def _queue_clips(clip_ids: list[int]):
    for clip_id in clip_ids:
        await _processing_queue.put(clip_id)


def get_watcher_state() -> dict:
    """Dump full watcher state for debugging."""
    state = {
        "active_observers": {},
        "queue_size": _processing_queue.qsize() if _processing_queue else None,
        "main_loop_alive": _main_loop is not None and _main_loop.is_running() if _main_loop else False,
    }
    for pid, obs in _active_observers.items():
        state["active_observers"][pid] = {
            "is_alive": obs.is_alive(),
            "watches": [str(w.path) for w in obs._watches.values()] if hasattr(obs, '_watches') else "unknown",
        }
    return state


def stop_watching(project_id: int):
    obs = _active_observers.pop(project_id, None)
    if obs:
        obs.stop()
        obs.join(timeout=5)
