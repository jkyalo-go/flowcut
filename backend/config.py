import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
PROCESSED_DIR = BASE_DIR / "backend" / "static" / "processed"
STORAGE_DIR = DATA_DIR / "storage"
UPLOAD_TMP_DIR = DATA_DIR / "uploads"
ASSETS_DIR = DATA_DIR / "assets"


def _bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _clean_origin(value: str) -> str:
    return value.rstrip("/")


def _csv_env(name: str, default: list[str]) -> list[str]:
    raw = os.environ.get(name)
    if raw is None:
        return default
    values = [_clean_origin(item.strip()) for item in raw.split(",") if item.strip()]
    return values or default


FRONTEND_URL = _clean_origin(os.environ.get("FRONTEND_URL", "http://localhost:3000"))
API_BASE_URL = _clean_origin(os.environ.get("API_BASE_URL", "http://localhost:8000"))
RENDER_BASE_URL = _clean_origin(os.environ.get("RENDER_BASE_URL", API_BASE_URL))
CORS_ORIGINS = _csv_env(
    "CORS_ORIGINS",
    [FRONTEND_URL, "http://localhost:5173", "http://127.0.0.1:3000"],
)
REQUIRE_DB_MIGRATIONS = _bool_env("REQUIRE_DB_MIGRATIONS", True)

APP_ENV = os.environ.get("APP_ENV", "development").strip().lower()
APP_VERSION = os.environ.get("APP_VERSION", "dev")
SECRET_KEY = os.environ.get("SECRET_KEY", "")
SESSION_COOKIE_NAME = os.environ.get("SESSION_COOKIE_NAME", "flowcut_session")
SESSION_COOKIE_SECURE = _bool_env("SESSION_COOKIE_SECURE", False)
ENABLE_DEV_LOGIN = _bool_env("ENABLE_DEV_LOGIN", False)
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY", "")

DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DATA_DIR / 'boost_vlog.db'}")

_DEV_SECRETS = {"dev-secret-key-change-in-prod", "change-me-before-starting", "change-me", ""}


def validate_production_config() -> None:
    """Fail-fast validation called at startup. Only enforces rules in production."""
    if APP_ENV != "production":
        return
    errors: list[str] = []
    if SECRET_KEY in _DEV_SECRETS or len(SECRET_KEY) < 32:
        errors.append("SECRET_KEY must be set to a 32+ char non-default secret in production")
    if ENABLE_DEV_LOGIN:
        errors.append("ENABLE_DEV_LOGIN must be false in production")
    if DATABASE_URL.startswith("sqlite:"):
        errors.append("DATABASE_URL must not be SQLite in production")
    if errors:
        raise RuntimeError("Invalid production config:\n  - " + "\n  - ".join(errors))
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

YOUTUBE_CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REDIRECT_URI = os.environ.get("YOUTUBE_REDIRECT_URI", f"{API_BASE_URL}/api/platforms/youtube/callback")
TIKTOK_CLIENT_ID = os.environ.get("TIKTOK_CLIENT_ID", "")
TIKTOK_CLIENT_SECRET = os.environ.get("TIKTOK_CLIENT_SECRET", "")
TIKTOK_REDIRECT_URI = os.environ.get("TIKTOK_REDIRECT_URI", f"{API_BASE_URL}/api/platforms/tiktok/callback")
LINKEDIN_CLIENT_ID = os.environ.get("LINKEDIN_CLIENT_ID", "")
LINKEDIN_CLIENT_SECRET = os.environ.get("LINKEDIN_CLIENT_SECRET", "")
LINKEDIN_REDIRECT_URI = os.environ.get("LINKEDIN_REDIRECT_URI", f"{API_BASE_URL}/api/platforms/linkedin/callback")
X_CLIENT_ID = os.environ.get("X_CLIENT_ID", "")
X_CLIENT_SECRET = os.environ.get("X_CLIENT_SECRET", "")
X_REDIRECT_URI = os.environ.get("X_REDIRECT_URI", f"{API_BASE_URL}/api/platforms/x/callback")
INSTAGRAM_CLIENT_ID = os.environ.get("INSTAGRAM_CLIENT_ID", "")
INSTAGRAM_CLIENT_SECRET = os.environ.get("INSTAGRAM_CLIENT_SECRET", "")
INSTAGRAM_REDIRECT_URI = os.environ.get("INSTAGRAM_REDIRECT_URI", f"{API_BASE_URL}/api/platforms/instagram_reels/callback")

SILENCE_THRESH_DB = -30
MIN_SILENCE_DURATION = 0.5

TALKING_WORD_THRESHOLD = 5

BROLL_NUM_CLIPS = 3
BROLL_CLIP_DURATION = 2.0

SCENE_DETECT_THRESHOLD = 27.0

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
BROWSER_COMPATIBLE_CODECS = {"h264", "vp8", "vp9", "av1"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}

MUSIC_BASE_VOLUME = 0.25
MUSIC_DUCK_VOLUME = 0.08
MUSIC_FADE_DURATION = 0.5

BROLL_AUDIO_VOLUME = 0.15

VERTEX_PROJECT_ID = os.environ.get("VERTEX_PROJECT_ID", "")
VERTEX_LOCATION = os.environ.get("VERTEX_LOCATION", "us-central1")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
ALIBABA_DASHSCOPE_API_KEY = os.environ.get("ALIBABA_DASHSCOPE_API_KEY", "")
REMIX_DIR = PROCESSED_DIR.parent / "remixes"
REMIX_DURATION = 4.0

TITLE_SFX_VOLUME = 0.5
STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "local")
GCS_MEDIA_BUCKET = os.environ.get("GCS_MEDIA_BUCKET", "")
GCS_MODELS_BUCKET = os.environ.get("GCS_MODELS_BUCKET", "")
GCS_SIGNED_URL_TTL_SECONDS = int(os.environ.get("GCS_SIGNED_URL_TTL_SECONDS", "3600"))
