import asyncio
import re
import subprocess
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path

from config import MIN_SILENCE_DURATION, SILENCE_THRESH_DB

ProgressCb = Callable[[float, str], Awaitable[None]] | None


def get_creation_time(path: str) -> datetime | None:
    """Extract creation_time metadata from a video file. Returns None if unavailable."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format_tags=creation_time",
             "-of", "default=nw=1:nokey=1", path],
            capture_output=True, text=True, timeout=10,
        )
        raw = result.stdout.strip()
        if not raw:
            return None
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


async def get_duration(input_path: str) -> float:
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", input_path,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    return float(stdout.decode().strip())


async def detect_silences(input_path: str) -> list[tuple[float, float]]:
    cmd = [
        "ffmpeg", "-i", input_path, "-af",
        f"silencedetect=noise={SILENCE_THRESH_DB}dB:d={MIN_SILENCE_DURATION}",
        "-f", "null", "-",
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    output = stderr.decode()

    silences = []
    starts = re.findall(r"silence_start: ([\d.]+)", output)
    ends = re.findall(r"silence_end: ([\d.]+)", output)

    for s, e in zip(starts, ends):
        silences.append((float(s), float(e)))

    if len(starts) > len(ends):
        total = await get_duration(input_path)
        silences.append((float(starts[-1]), total))

    return silences


def invert_silences(silences: list[tuple[float, float]], total_duration: float) -> list[tuple[float, float]]:
    if not silences:
        return [(0, total_duration)]

    speech = []
    prev_end = 0.0
    for s_start, s_end in sorted(silences):
        if s_start > prev_end:
            speech.append((prev_end, s_start))
        prev_end = s_end
    if prev_end < total_duration:
        speech.append((prev_end, total_duration))
    return speech


def build_filter_complex(segments: list[tuple[float, float]]) -> tuple[str, str, str]:
    parts = []
    for i, (start, end) in enumerate(segments):
        parts.append(f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[v{i}];")
        parts.append(f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[a{i}];")

    concat_inputs = "".join(f"[v{i}][a{i}]" for i in range(len(segments)))
    parts.append(f"{concat_inputs}concat=n={len(segments)}:v=1:a=1[outv][outa]")

    return "".join(parts), "[outv]", "[outa]"


async def _stream_ffmpeg_progress(proc: asyncio.subprocess.Process, total_duration: float, on_progress: ProgressCb):
    """Parse ffmpeg stderr line-by-line for time= progress."""
    if not on_progress or not proc.stderr:
        await proc.communicate()
        return b""

    stderr_data = b""
    while True:
        chunk = await proc.stderr.read(512)
        if not chunk:
            break
        stderr_data += chunk
        text = chunk.decode(errors="replace")
        # ffmpeg outputs time=HH:MM:SS.xx or time=SS.xx
        matches = re.findall(r"time=(\d+):(\d+):(\d+\.\d+)", text)
        if matches:
            h, m, s = matches[-1]
            current = int(h) * 3600 + int(m) * 60 + float(s)
            pct = min(current / total_duration, 1.0) if total_duration > 0 else 0
            await on_progress(pct, "encoding")

    return stderr_data


async def remove_silences(input_path: str, output_dir: str, on_progress: ProgressCb = None) -> str:
    total_duration = await get_duration(input_path)

    if on_progress:
        await on_progress(0.0, "detecting silence")

    silences = await detect_silences(input_path)
    speech_segments = invert_silences(silences, total_duration)

    if on_progress:
        await on_progress(0.3, "silence detected")

    if not speech_segments:
        return input_path

    output_path = str(Path(output_dir) / f"{Path(input_path).stem}_no_silence.mp4")

    if len(speech_segments) == 1 and speech_segments[0] == (0, total_duration):
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", input_path, "-c", "copy", output_path,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        if on_progress:
            await on_progress(1.0, "done")
        return output_path

    # Calculate expected output duration for progress tracking
    output_duration = sum(end - start for start, end in speech_segments)

    filter_graph, v_map, a_map = build_filter_complex(speech_segments)

    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-filter_complex", filter_graph,
        "-map", v_map, "-map", a_map,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        "-progress", "pipe:2",
        output_path,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )

    if on_progress:
        async def encoding_progress(pct: float, stage: str):
            # Scale encoding progress from 0.3 to 1.0 (first 30% was detection)
            await on_progress(0.3 + pct * 0.7, stage)
        stderr_data = await _stream_ffmpeg_progress(proc, output_duration, encoding_progress)
    else:
        _, stderr_data = await proc.communicate()

    await proc.wait()
    if proc.returncode != 0:
        err = stderr_data.decode(errors="replace") if isinstance(stderr_data, bytes) else str(stderr_data)
        raise RuntimeError(f"ffmpeg silence removal failed: {err[-500:]}")

    if on_progress:
        await on_progress(1.0, "done")
    return output_path
