import asyncio
import tempfile
from pathlib import Path
from sqlalchemy.orm import Session
from database import SessionLocal
from models import TimelineItem, MusicItem, Asset
from routes.ws import broadcast
from services.ducker import compute_volume_envelope, envelope_to_ffmpeg_expr
from routes.music import _build_timeline_segments


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


async def extract_segment(source_path: str, start: float, end: float, output_path: str, width: int = 1920, height: int = 1080, fps: int = 30):
    """Extract and normalize a segment from a source video."""
    duration = end - start
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start), "-i", source_path, "-t", str(duration),
        "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps={fps}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        output_path,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"Segment extract failed: {stderr.decode()[-500:]}")


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

        await broadcast(project_id, "render_progress", {"percent": 0, "stage": "extracting"})

        with tempfile.TemporaryDirectory() as tmpdir:
            extracted = []
            for i, (source, start, end) in enumerate(segments):
                seg_path = str(Path(tmpdir) / f"seg_{i}.mp4")
                await extract_segment(source, start, end, seg_path)
                pct = int((i + 1) / len(segments) * 50)
                await broadcast(project_id, "render_progress", {"percent": pct, "stage": "extracting"})
                extracted.append(seg_path)

            # Write concat file
            concat_file = str(Path(tmpdir) / "concat.txt")
            with open(concat_file, "w") as f:
                for p in extracted:
                    f.write(f"file '{p}'\n")

            await broadcast(project_id, "render_progress", {"percent": 55, "stage": "concatenating"})

            cmd = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file,
                "-c", "copy",
                output_path,
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(f"Render failed: {stderr.decode()[-500:]}")

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
