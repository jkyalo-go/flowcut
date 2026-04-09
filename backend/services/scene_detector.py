import asyncio
from pathlib import Path
from typing import Callable, Awaitable
from scenedetect import open_video, SceneManager, ContentDetector
from config import SCENE_DETECT_THRESHOLD, BROLL_NUM_CLIPS, BROLL_CLIP_DURATION

ProgressCb = Callable[[float, str], Awaitable[None]] | None


def detect_scenes(input_path: str) -> list[dict]:
    video = open_video(input_path)
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector(threshold=SCENE_DETECT_THRESHOLD))
    scene_manager.detect_scenes(video)
    scene_list = scene_manager.get_scene_list()

    scored = []
    for start, end in scene_list:
        duration = end.get_seconds() - start.get_seconds()
        score = min(duration, BROLL_CLIP_DURATION) / BROLL_CLIP_DURATION
        scored.append({
            "start": start.get_seconds(),
            "end": end.get_seconds(),
            "duration": duration,
            "score": score,
        })

    return scored


async def extract_best_moments(input_path: str, output_dir: str, on_progress: ProgressCb = None) -> list[dict]:
    if on_progress:
        await on_progress(0.0, "analyzing scenes")

    scenes = await asyncio.to_thread(detect_scenes, input_path)

    if on_progress:
        await on_progress(0.3, "scenes detected")

    if not scenes:
        proc = await asyncio.create_subprocess_exec(
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", input_path,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        total_dur = float(stdout.decode().strip())

        scenes = []
        step = total_dur / (BROLL_NUM_CLIPS + 1)
        for i in range(BROLL_NUM_CLIPS):
            start = step * (i + 1) - BROLL_CLIP_DURATION / 2
            start = max(0, start)
            scenes.append({
                "start": start,
                "end": min(start + BROLL_CLIP_DURATION, total_dur),
                "duration": BROLL_CLIP_DURATION,
                "score": 0.5,
            })

    top_scenes = sorted(scenes, key=lambda s: s["score"], reverse=True)[:BROLL_NUM_CLIPS]

    results = []
    for i, scene in enumerate(top_scenes):
        start = scene["start"]
        dur = min(BROLL_CLIP_DURATION, scene["end"] - scene["start"])
        out_path = str(Path(output_dir) / f"{Path(input_path).stem}_broll_{i}.mp4")

        if on_progress:
            pct = 0.3 + (i / BROLL_NUM_CLIPS) * 0.7
            await on_progress(pct, f"extracting clip {i + 1}/{BROLL_NUM_CLIPS}")

        cmd = [
            "ffmpeg", "-y", "-ss", str(start), "-i", input_path,
            "-t", str(dur),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "192k",
            out_path,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg b-roll extract failed: {stderr.decode()[-500:]}")

        results.append({
            "path": out_path,
            "start": start,
            "end": start + dur,
            "score": scene["score"],
        })

    if on_progress:
        await on_progress(1.0, "done")

    return results
