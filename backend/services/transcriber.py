import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Callable
from deepgram import DeepgramClient, PrerecordedOptions, FileSource
from config import DEEPGRAM_API_KEY

logger = logging.getLogger(__name__)

_client: DeepgramClient | None = None


def get_client() -> DeepgramClient:
    global _client
    if _client is None:
        if not DEEPGRAM_API_KEY:
            raise RuntimeError("DEEPGRAM_API_KEY environment variable is not set")
        _client = DeepgramClient(DEEPGRAM_API_KEY)
    return _client


async def extract_audio(video_path: str) -> str:
    """Extract audio from video as a small mp3 file for upload."""
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp.close()
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vn", "-ac", "1", "-ar", "16000", "-b:a", "64k",
        tmp.name,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"Audio extraction failed: {stderr.decode()[-300:]}")
    logger.info(f"Extracted audio: {Path(tmp.name).stat().st_size / 1024:.0f} KB")
    return tmp.name


def transcribe_file(audio_path: str) -> tuple[str, list[dict]]:
    client = get_client()

    with open(audio_path, "rb") as f:
        buffer_data = f.read()

    payload: FileSource = {"buffer": buffer_data}

    options = PrerecordedOptions(
        model="nova-3",
        smart_format=True,
        utterances=True,
        punctuate=True,
    )

    response = client.listen.rest.v("1").transcribe_file(
        payload, options, timeout=300
    )

    result = response.results
    full_text = result.channels[0].alternatives[0].transcript if result.channels else ""

    words = []
    if result.channels and result.channels[0].alternatives[0].words:
        for w in result.channels[0].alternatives[0].words:
            words.append({"start": w.start, "end": w.end, "word": w.word})

    if not words:
        utterances = response.results.utterances or []
        speech_regions = [
            {"start": u.start, "end": u.end, "text": u.transcript}
            for u in utterances
            if (u.end - u.start) >= 0.1
        ]
        return full_text, speech_regions

    # Merge words into speech regions: merge gaps < 0.3s
    speech_regions = []
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

    logger.info(f"Deepgram: {len(words)} words -> {len(speech_regions)} speech regions")

    return full_text, speech_regions
