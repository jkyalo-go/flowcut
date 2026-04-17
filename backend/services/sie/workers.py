from __future__ import annotations
import asyncio
import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

try:
    from scenedetect import detect, ContentDetector
    _SCENEDETECT_AVAILABLE = True
except ImportError:
    detect = None
    ContentDetector = None
    _SCENEDETECT_AVAILABLE = False

try:
    from faster_whisper import WhisperModel
    _WHISPER_AVAILABLE = True
except ImportError:
    WhisperModel = None
    _WHISPER_AVAILABLE = False


_whisper_model = None


def _get_whisper_model():
    global _whisper_model
    if not _WHISPER_AVAILABLE:
        raise RuntimeError("faster-whisper is not installed")
    if _whisper_model is None:
        _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
    return _whisper_model


async def run_scene_detection(video_path: str) -> list[dict]:
    """CPU-only scene boundary detection via PySceneDetect."""
    if not _SCENEDETECT_AVAILABLE:
        logger.warning("scenedetect not installed — scene detection skipped")
        return []
    scenes = detect(video_path, ContentDetector(threshold=27.0))
    return [
        {"start_sec": round(s[0].get_seconds(), 2), "end_sec": round(s[1].get_seconds(), 2)}
        for s in scenes
    ]


async def run_transcription(video_path: str) -> dict:
    """Transcribe audio via faster-whisper. Returns {text, segments: [{start, end, text}]}."""
    model = _get_whisper_model()
    segments, info = model.transcribe(video_path, beam_size=5)
    seg_list = [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments]
    return {"text": " ".join(s["text"] for s in seg_list), "segments": seg_list}


async def run_gemini_visual_scoring(video_path: str, gcs_uri: str | None = None) -> list[dict]:
    """Score moments using Gemini 2.5 Flash multimodal analysis.
    Returns [] when GEMINI_API_KEY is absent or gcs_uri is not provided."""
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return []

    from google import genai
    client = genai.Client(api_key=api_key)
    prompt = (
        "Analyze this video. Return JSON array of compelling moments. "
        "Each item: {start_sec, end_sec, type, engagement_score (0-1), sentiment, description}. "
        'Moment types: highlight, reaction, educational, funny, transition. '
        "Only include moments with engagement_score > 0.5. Be precise about timestamps."
    )

    source = genai.types.Part.from_uri(file_uri=gcs_uri, mime_type="video/mp4") if gcs_uri else None
    if source is None:
        return []

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[source, prompt],
        config={"response_mime_type": "application/json"},
    )
    try:
        return json.loads(response.text)
    except (json.JSONDecodeError, AttributeError):
        return []


async def run_all_workers(video_path: str, gcs_uri: str | None = None) -> dict[str, Any]:
    """Fan out all analysis workers in parallel. Returns merged analysis state."""
    scenes, transcript, visual_moments = await asyncio.gather(
        run_scene_detection(video_path),
        run_transcription(video_path),
        run_gemini_visual_scoring(video_path, gcs_uri),
        return_exceptions=True,
    )

    return {
        "scenes": scenes if not isinstance(scenes, Exception) else [],
        "transcript": transcript if not isinstance(transcript, Exception) else {"text": "", "segments": []},
        "visual_moments": visual_moments if not isinstance(visual_moments, Exception) else [],
    }
