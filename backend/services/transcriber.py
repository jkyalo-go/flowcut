import asyncio
import logging
import tempfile
from pathlib import Path

# New imports for current SDK (v5+ / v6)
from deepgram import DeepgramClient

from config import DEEPGRAM_API_KEY
from database import SessionLocal
from domain.identity import Workspace
from domain.shared import AIProvider, AIUsageStatus, CredentialSource
from services.ai_registry import registry

logger = logging.getLogger(__name__)

_client: DeepgramClient | None = None


def get_client() -> DeepgramClient:
    global _client
    if _client is None:
        if not DEEPGRAM_API_KEY:
            raise RuntimeError("DEEPGRAM_API_KEY is not set in config or environment")
        _client = DeepgramClient(DEEPGRAM_API_KEY)   # or DeepgramClient() if key is in env
    return _client


async def extract_audio(video_path: str) -> str:
    """Extract audio from video as a small mono mp3 file (good for transcription)."""
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp.close()

    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vn", "-ac", "1", "-ar", "16000", "-b:a", "64k",
        tmp.name,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(f"Audio extraction failed: {stderr.decode()[-400:]}")

    size_kb = Path(tmp.name).stat().st_size / 1024
    logger.info(f"Extracted audio: {size_kb:.0f} KB → {tmp.name}")
    return tmp.name


def transcribe_file(
    audio_path: str,
    workspace_id: str,
    user_id: str | None = None,
    project_id: str | None = None,
    clip_id: str | None = None,
) -> tuple[str, list[dict]]:
    """Transcribe audio file using current Deepgram SDK (v5/v6)."""
    db = SessionLocal()
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    provider, model, credential_source, _api_key = registry.select_provider(db, workspace, "transcription")
    if provider != AIProvider.DEEPGRAM:
        provider = AIProvider.DEEPGRAM
        model = "nova-3"
        credential_source = CredentialSource.PLATFORM
    start = __import__("time").time()
    client = get_client()

    try:
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        # Modern way (no PrerecordedOptions / FileSource needed)
        response = client.listen.v1.media.transcribe_file(
            request=audio_bytes,          # raw bytes
            model="nova-3",               # best general model
            smart_format=True,
            utterances=True,              # good for speech regions
            punctuate=True,
            # diarize=True,               # uncomment if you want speaker detection
            # language="en",              # explicit if needed
        )

        # Extract full transcript
        full_text = ""
        if (response.results and
            response.results.channels and
            response.results.channels[0].alternatives):
            full_text = response.results.channels[0].alternatives[0].transcript or ""

        # Extract timed words (preferred for your speech regions logic)
        words = []
        alt = response.results.channels[0].alternatives[0]
        if hasattr(alt, "words") and alt.words:
            for w in alt.words:
                words.append({
                    "start": w.start,
                    "end": w.end,
                    "word": w.word
                })

        # Fallback to utterances if no word-level timestamps
        if not words and hasattr(response.results, "utterances") and response.results.utterances:
            utterances = response.results.utterances or []
            speech_regions = [
                {
                    "start": u.start,
                    "end": u.end,
                    "text": u.transcript.strip()
                }
                for u in utterances
                if (u.end - u.start) >= 0.1
            ]
            logger.info(f"Deepgram: Used {len(speech_regions)} utterances")
            registry._record_usage(
                db,
                workspace_id=workspace_id,
                user_id=user_id,
                project_id=project_id,
                clip_id=clip_id,
                task_type="transcription",
                provider=provider,
                model=model,
                credential_source=credential_source,
                start_time=start,
                request_units=float(len(audio_bytes)),
                response_units=float(len(full_text)),
                cost_estimate=len(audio_bytes) / 1_000_000,
            )
            return full_text, speech_regions

        # Your existing logic to merge words into speech regions (gaps < 0.3s)
        speech_regions = []
        if words:
            region_start = words[0]["start"]
            region_end = words[0]["end"]
            region_words = [words[0]["word"]]

            for w in words[1:]:
                gap = w["start"] - region_end
                if gap < 0.3:
                    region_end = w["end"]
                    region_words.append(w["word"])
                else:
                    speech_regions.append({
                        "start": region_start,
                        "end": region_end,
                        "text": " ".join(region_words).strip(),
                    })
                    region_start = w["start"]
                    region_end = w["end"]
                    region_words = [w["word"]]

            speech_regions.append({
                "start": region_start,
                "end": region_end,
                "text": " ".join(region_words).strip(),
            })

            logger.info(f"Deepgram: {len(words)} words → {len(speech_regions)} speech regions")

        registry._record_usage(
            db,
            workspace_id=workspace_id,
            user_id=user_id,
            project_id=project_id,
            clip_id=clip_id,
            task_type="transcription",
            provider=provider,
            model=model,
            credential_source=credential_source,
            start_time=start,
            request_units=float(len(audio_bytes)),
            response_units=float(len(full_text)),
            cost_estimate=len(audio_bytes) / 1_000_000,
        )
        return full_text, speech_regions

    except Exception as e:
        logger.error(f"Deepgram transcription failed: {e}")
        registry._record_usage(
            db,
            workspace_id=workspace_id,
            user_id=user_id,
            project_id=project_id,
            clip_id=clip_id,
            task_type="transcription",
            provider=provider,
            model=model,
            credential_source=credential_source,
            start_time=start,
            status=AIUsageStatus.ERROR,
            error_message=str(e),
        )
        raise
    finally:
        db.close()
