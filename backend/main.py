import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database import engine, Base
from routes import projects, clips, timeline, render, ws, filesystem, generate, youtube, assets, music
from workers.queue import processing_queue, process_worker
from services.watcher import set_queue
from config import PROCESSED_DIR, DATA_DIR, ASSETS_DIR

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    # Add new columns to existing tables (SQLite doesn't support IF NOT EXISTS for columns)
    with engine.connect() as conn:
        import sqlalchemy
        existing = {row[1] for row in conn.execute(sqlalchemy.text("PRAGMA table_info(projects)"))}
        for col, col_type, default in [
            ("selected_title", "VARCHAR", None),
            ("video_description", "VARCHAR", None),
            ("video_tags", "VARCHAR", None),
            ("video_category", "VARCHAR", "'22'"),
            ("video_visibility", "VARCHAR", "'private'"),
            ("selected_thumbnail_idx", "INTEGER", None),
            ("desc_system_prompt", "VARCHAR", None),
            ("thumbnail_urls", "VARCHAR", None),
            ("locked_thumbnail_indices", "VARCHAR", None),
            ("thumbnail_text", "VARCHAR", None),
            ("render_path", "VARCHAR", None),
        ]:
            if col not in existing:
                dflt = f" DEFAULT {default}" if default else ""
                conn.execute(sqlalchemy.text(f"ALTER TABLE projects ADD COLUMN {col} {col_type}{dflt}"))
        conn.commit()
        # Migrate clips table
        existing_clips = {row[1] for row in conn.execute(sqlalchemy.text("PRAGMA table_info(clips)"))}
        for col, col_type, default in [
            ("recorded_at", "DATETIME", None),
        ]:
            if col not in existing_clips:
                dflt = f" DEFAULT {default}" if default else ""
                conn.execute(sqlalchemy.text(f"ALTER TABLE clips ADD COLUMN {col} {col_type}{dflt}"))
        conn.commit()
    set_queue(processing_queue)
    task = asyncio.create_task(process_worker())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Boost Vlog", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(PROCESSED_DIR.parent)), name="static")

app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(clips.router, prefix="/api/clips", tags=["clips"])
app.include_router(timeline.router, prefix="/api/timeline", tags=["timeline"])
app.include_router(render.router, prefix="/api/render", tags=["render"])
app.include_router(filesystem.router, prefix="/api/fs", tags=["filesystem"])
app.include_router(ws.router, prefix="/ws", tags=["websocket"])
app.include_router(generate.router, prefix="/api/projects", tags=["generate"])
app.include_router(youtube.router, prefix="/api/youtube", tags=["youtube"])
app.include_router(assets.router, prefix="/api/assets", tags=["assets"])
app.include_router(music.router, prefix="/api/music", tags=["music"])
