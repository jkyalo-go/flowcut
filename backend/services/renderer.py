import asyncio
import tempfile
from pathlib import Path
from sqlalchemy.orm import Session
from database import SessionLocal
from models import TimelineItem
from routes.ws import broadcast


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
                pct = int((i + 1) / len(segments) * 60)
                await broadcast(project_id, "render_progress", {"percent": pct, "stage": "extracting"})
                extracted.append(seg_path)

            # Write concat file
            concat_file = str(Path(tmpdir) / "concat.txt")
            with open(concat_file, "w") as f:
                for p in extracted:
                    f.write(f"file '{p}'\n")

            await broadcast(project_id, "render_progress", {"percent": 65, "stage": "concatenating"})

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

        await broadcast(project_id, "render_progress", {"percent": 100, "stage": "done"})
        await broadcast(project_id, "render_done", {"output_path": output_path})

        return output_path
    finally:
        db.close()
