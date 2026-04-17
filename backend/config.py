from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
DATA_DIR = BASE_DIR / "data"
PROCESSED_DIR = BASE_DIR / "backend" / "static" / "processed"
STORAGE_DIR = DATA_DIR / "storage"
UPLOAD_TMP_DIR = DATA_DIR / "uploads"

DATABASE_URL = f"sqlite:///{DATA_DIR / 'boost_vlog.db'}"

import os
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DATA_DIR / 'boost_vlog.db'}")
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

YOUTUBE_CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REDIRECT_URI = "http://localhost:8000/api/platforms/youtube/callback"
TIKTOK_CLIENT_ID = os.environ.get("TIKTOK_CLIENT_ID", "")
TIKTOK_CLIENT_SECRET = os.environ.get("TIKTOK_CLIENT_SECRET", "")
TIKTOK_REDIRECT_URI = os.environ.get("TIKTOK_REDIRECT_URI", "http://localhost:8000/api/platforms/tiktok/callback")
LINKEDIN_CLIENT_ID = os.environ.get("LINKEDIN_CLIENT_ID", "")
LINKEDIN_CLIENT_SECRET = os.environ.get("LINKEDIN_CLIENT_SECRET", "")
LINKEDIN_REDIRECT_URI = os.environ.get("LINKEDIN_REDIRECT_URI", "http://localhost:8000/api/platforms/linkedin/callback")
X_CLIENT_ID = os.environ.get("X_CLIENT_ID", "")
X_CLIENT_SECRET = os.environ.get("X_CLIENT_SECRET", "")
X_REDIRECT_URI = os.environ.get("X_REDIRECT_URI", "http://localhost:8000/api/platforms/x/callback")
INSTAGRAM_CLIENT_ID = os.environ.get("INSTAGRAM_CLIENT_ID", "")
INSTAGRAM_CLIENT_SECRET = os.environ.get("INSTAGRAM_CLIENT_SECRET", "")
INSTAGRAM_REDIRECT_URI = os.environ.get("INSTAGRAM_REDIRECT_URI", "http://localhost:8000/api/platforms/instagram_reels/callback")

SILENCE_THRESH_DB = -30
MIN_SILENCE_DURATION = 0.5

TALKING_WORD_THRESHOLD = 5

BROLL_NUM_CLIPS = 3
BROLL_CLIP_DURATION = 2.0

SCENE_DETECT_THRESHOLD = 27.0

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
BROWSER_COMPATIBLE_CODECS = {"h264", "vp8", "vp9", "av1"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}

ASSETS_DIR = DATA_DIR / "assets"

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
