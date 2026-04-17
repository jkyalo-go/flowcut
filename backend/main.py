from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

try:
    from .bootstrap import lifespan
    from .config import PROCESSED_DIR
    from .modules import register_routers
except ImportError:
    from bootstrap import lifespan
    from config import PROCESSED_DIR
    from modules import register_routers


app = FastAPI(title="Flowcut", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(PROCESSED_DIR.parent)), name="static")

register_routers(app)
