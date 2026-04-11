import asyncio
import logging
import re
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)
from sqlalchemy.orm import Session
from database import SessionLocal
from models import TimelineItem, MusicItem, Asset
from routes.ws import broadcast
from services.ducker import compute_volume_envelope, envelope_to_ffmpeg_expr
from routes.music import _build_timeline_segments

_OUT_TIME_RE = re.compile(r"out_time_us=(\d+)")


def _resolve_source_and_range(item: TimelineItem) -> tuple[str, float, float] | None:
    """Returns (source_path, start_time, end_time) for a timeline item."""
    if item.sub_clip_id and item.sub_clip:
        sub = item.sub_clip
        parent = sub.parent_clip
        if parent:
            return (parent.source_path, sub.start_time, sub.end_time)
    if item.clip_id and item.clip:
        clip = item.clip
        return (clip.source_path, 0, clip.duration or 0)
    return None


async def _probe_audio_streams(segments: list[tuple[str, float, float]]) -> dict[str, bool]:
    """Check which source files have audio streams. Returns {path: has_audio}."""
    unique_paths = set(source for source, _, _ in segments)

    async def _probe(path: str) -> tuple[str, bool]:
        proc = await asyncio.create_subprocess_exec(
            "ffprobe", "-v", "quiet", "-select_streams", "a",
            "-show_entries", "stream=index", "-of", "csv=p=0", path,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return (path, bool(stdout.strip()))

    results = await asyncio.gather(*[_probe(p) for p in unique_paths])
    return dict(results)


def _build_concat_filter(
    segments: list[tuple[str, float, float]],
    has_audio: dict[str, bool],
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
) -> tuple[list[str], str]:
    """Build FFmpeg input args and filter_complex for single-pass concat.

    Deduplicates source files so each is opened only once as an input.
    """
    # Map unique source paths to input indices
    source_to_idx: dict[str, int] = {}
    input_args = []
    for source, _, _ in segments:
        if source not in source_to_idx:
            source_to_idx[source] = len(source_to_idx)
            input_args.extend(["-i", source])

    filter_parts = []
    for i, (source, start, end) in enumerate(segments):
        inp = source_to_idx[source]
        duration = end - start

        vf = (
            f"[{inp}:v]trim=start={start}:end={end},setpts=PTS-STARTPTS,"
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
            f"fps={fps}[v{i}]"
        )
        filter_parts.append(vf)

        if has_audio.get(source, False):
            af = (
                f"[{inp}:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS,"
                f"aresample=48000,aformat=channel_layouts=stereo[a{i}]"
            )
        else:
            af = (
                f"anullsrc=r=48000:cl=stereo[_sil{i}];"
                f"[_sil{i}]atrim=duration={duration},asetpts=PTS-STARTPTS[a{i}]"
            )
        filter_parts.append(af)

    concat_inputs = "".join(f"[v{i}][a{i}]" for i in range(len(segments)))
    filter_parts.append(f"{concat_inputs}concat=n={len(segments)}:v=1:a=1[vout][aout]")

    return input_args, ";".join(filter_parts)


async def _run_ffmpeg_with_progress(
    cmd: list[str],
    total_duration: float,
    project_id: int,
    pct_start: int = 0,
    pct_end: int = 70,
) -> None:
    """Run FFmpeg with -progress pipe:1 for reliable progress reporting."""
    cmd = [*cmd, "-progress", "pipe:1"]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    last_pct = -1

    async def _read_progress():
        nonlocal last_pct
        async for raw_line in proc.stdout:
            line = raw_line.decode("utf-8", errors="replace").strip()
            match = _OUT_TIME_RE.match(line)
            if match and total_duration > 0:
                current = int(match.group(1)) / 1_000_000
                ratio = min(current / total_duration, 1.0)
                pct = pct_start + int(ratio * (pct_end - pct_start))
                if pct != last_pct:
                    await broadcast(project_id, "render_progress", {
                        "percent": pct, "stage": "rendering",
                    })
                    last_pct = pct

    async def _read_stderr():
        return await proc.stderr.read()

    _, stderr_output = await asyncio.gather(_read_progress(), _read_stderr())
    await proc.wait()
    if proc.returncode != 0:
        err = stderr_output.decode()[-1000:]
        logger.error("FFmpeg failed (rc=%d): %s", proc.returncode, err)
        raise RuntimeError(f"Render failed: {err}")


async def render_timeline(project_id: int, output_path: str) -> str:
    db: Session = SessionLocal()
    try:
        items = (
            db.query(TimelineItem)
            .filter(TimelineItem.project_id == project_id)
            .order_by(TimelineItem.position)
            .all()
        )

        if not items:
            raise ValueError("Timeline is empty")

        segments = []
        for item in items:
            seg = _resolve_source_and_range(item)
            if seg:
                segments.append(seg)

        if not segments:
            raise ValueError("No valid clips in timeline")

        await broadcast(project_id, "render_progress", {"percent": 0, "stage": "rendering"})

        logger.info("Rendering %d segments for project %d", len(segments), project_id)
        await broadcast(project_id, "render_progress", {"percent": 0, "stage": "initializing"})
        has_audio = await _probe_audio_streams(segments)
        logger.info("Audio probe results: %s", has_audio)
        input_args, filter_complex = _build_concat_filter(segments, has_audio)
        total_duration = sum(end - start for _, start, end in segments)

        with tempfile.TemporaryDirectory() as tmpdir:
            cmd = ["ffmpeg", "-y", *input_args]

            if len(filter_complex) > 500_000:
                script_path = str(Path(tmpdir) / "filter.txt")
                with open(script_path, "w") as f:
                    f.write(filter_complex)
                cmd.extend(["-filter_complex_script", script_path])
            else:
                cmd.extend(["-filter_complex", filter_complex])

            cmd.extend([
                "-map", "[vout]", "-map", "[aout]",
                "-c:v", "h264_videotoolbox", "-q:v", "65",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                output_path,
            ])

            await _run_ffmpeg_with_progress(cmd, total_duration, project_id, 0, 70)

        # Check for music items and mix if present
        music_items = (
            db.query(MusicItem)
            .filter(MusicItem.project_id == project_id)
            .order_by(MusicItem.start_time)
            .all()
        )

        if music_items:
            await broadcast(project_id, "render_progress", {"percent": 70, "stage": "mixing music"})
            await _mix_music(items, music_items, output_path, project_id)

        await broadcast(project_id, "render_progress", {"percent": 100, "stage": "done"})
        await broadcast(project_id, "render_done", {"output_path": output_path})

        return output_path
    except Exception as e:
        logger.exception("Render failed for project %d", project_id)
        await broadcast(project_id, "render_error", {"error": str(e)})
        raise
    finally:
        db.close()


async def _mix_music(
    timeline_items: list[TimelineItem],
    music_items: list[MusicItem],
    video_path: str,
    project_id: int,
):
    """Concatenate music files and mix into the video with ducking."""
    segments, total_duration = _build_timeline_segments(timeline_items)
    envelope = compute_volume_envelope(segments, total_duration)
    volume_expr = envelope_to_ffmpeg_expr(envelope)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Step 1: Build concatenated music track
        music_track_path = str(Path(tmpdir) / "music_track.wav")

        if len(music_items) == 1:
            mi = music_items[0]
            duration = mi.end_time - mi.start_time
            cmd = [
                "ffmpeg", "-y", "-i", mi.asset.file_path,
                "-t", str(duration), "-ac", "2", "-ar", "48000",
                music_track_path,
            ]
        else:
            inputs = []
            filter_parts = []
            for i, mi in enumerate(music_items):
                duration = mi.end_time - mi.start_time
                inputs.extend(["-i", mi.asset.file_path])
                filter_parts.append(f"[{i}:a]atrim=0:{duration},asetpts=PTS-STARTPTS[a{i}]")

            concat_labels = "".join(f"[a{i}]" for i in range(len(music_items)))
            filter_parts.append(f"{concat_labels}concat=n={len(music_items)}:v=0:a=1[music]")
            filter_complex = ";".join(filter_parts)

            cmd = [
                "ffmpeg", "-y", *inputs,
                "-filter_complex", filter_complex,
                "-map", "[music]", "-ac", "2", "-ar", "48000",
                music_track_path,
            ]

        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"Music concat failed: {stderr.decode()[-500:]}")

        await broadcast(project_id, "render_progress", {"percent": 80, "stage": "mixing music"})

        # Step 2: Mix music into video with ducking
        mixed_path = str(Path(tmpdir) / "mixed.mp4")
        filter_complex = (
            f"[1:a]volume='{volume_expr}':eval=frame[ducked];"
            f"[0:a][ducked]amix=inputs=2:duration=first:dropout_transition=0[aout]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", music_track_path,
            "-filter_complex", filter_complex,
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            mixed_path,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"Music mixing failed: {stderr.decode()[-500:]}")

        await broadcast(project_id, "render_progress", {"percent": 95, "stage": "mixing music"})

        # Replace original output with mixed version
        import shutil
        shutil.move(mixed_path, video_path)
