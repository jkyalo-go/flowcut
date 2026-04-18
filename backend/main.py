from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

try:
    from .bootstrap import lifespan
    from .config import CORS_ORIGINS, PROCESSED_DIR
    from .modules import register_routers
except ImportError:
    from bootstrap import lifespan
    from config import CORS_ORIGINS, PROCESSED_DIR
    from modules import register_routers


app = FastAPI(title="Flowcut", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(PROCESSED_DIR.parent)), name="static")

register_routers(app)
