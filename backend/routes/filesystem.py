import asyncio
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse

router = APIRouter()


@router.get("/pick-folder")
async def pick_folder():
    script = """
import subprocess, sys, json
result = subprocess.run(
    ["osascript", "-e", 'POSIX path of (choose folder with prompt "Select folder to watch")'],
    capture_output=True, text=True, timeout=120
)
path = result.stdout.strip()
print(json.dumps({"path": path, "cancelled": not bool(path)}))
"""
    proc = await asyncio.create_subprocess_exec(
        "python3", "-c", script,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    data = json.loads(stdout.decode())
    return data


@router.get("/serve-video")
async def serve_video(path: str = Query(...), request: Request = None):
    """Serve a video file from the local filesystem for timeline playback."""
    p = Path(path)
    if not p.exists() or not p.is_file():
        raise HTTPException(404, "File not found")

    range_header = request.headers.get("range") if request else None
    file_size = p.stat().st_size
    print(f"[serve-video] {p.name} size={file_size} range={range_header}")

    suffix = p.suffix.lower()
    media_types = {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".avi": "video/x-msvideo",
        ".mkv": "video/x-matroska",
        ".webm": "video/webm",
    }
    media_type = media_types.get(suffix, "video/mp4")
    return FileResponse(str(p), media_type=media_type)
