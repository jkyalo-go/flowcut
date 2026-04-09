import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database import engine, Base
from routes import projects, clips, timeline, render, ws, filesystem
from workers.queue import processing_queue, process_worker
from services.watcher import set_queue
from config import PROCESSED_DIR, DATA_DIR

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
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
