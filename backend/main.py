from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

try:
    from .bootstrap import lifespan
    from .config import CORS_ORIGINS, PROCESSED_DIR
    from .middleware.request_context import RequestContextMiddleware, configure_logging
    from .middleware.sentry import init_sentry
    from .modules import register_routers
except ImportError:
    from bootstrap import lifespan
    from config import CORS_ORIGINS, PROCESSED_DIR
    from middleware.request_context import RequestContextMiddleware, configure_logging
    from middleware.sentry import init_sentry
    from modules import register_routers


configure_logging()
init_sentry()

app = FastAPI(title="Flowcut", lifespan=lifespan)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Flowcut-Token",
        "X-Request-ID",
        "X-CSRF-Token",
    ],
    expose_headers=["X-Request-ID"],
    max_age=600,
)

app.mount("/static", StaticFiles(directory=str(PROCESSED_DIR.parent)), name="static")

register_routers(app)
