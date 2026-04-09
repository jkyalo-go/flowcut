from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PROCESSED_DIR = BASE_DIR / "backend" / "static" / "processed"

DATABASE_URL = f"sqlite:///{DATA_DIR / 'boost_vlog.db'}"

import os
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY", "")

SILENCE_THRESH_DB = -30
MIN_SILENCE_DURATION = 0.5

TALKING_WORD_THRESHOLD = 5

BROLL_NUM_CLIPS = 3
BROLL_CLIP_DURATION = 2.0

SCENE_DETECT_THRESHOLD = 27.0

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
