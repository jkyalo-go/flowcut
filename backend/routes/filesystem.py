from pathlib import Path
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse

from services.storage import download_to_temp, resolve_storage_path, signed_url_for

router = APIRouter()


@router.get("/serve-video")
async def serve_video(path: str = Query(...), request: Request = None):
    """Serve a video file from the local filesystem for timeline playback."""
    p = download_to_temp(path)
    if not p.exists():
        p = resolve_storage_path(path)
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


@router.get("/storage-file")
async def serve_storage_file(path: str = Query(...)):
    p = download_to_temp(path)
    if not p.exists() or not p.is_file():
        raise HTTPException(404, "Stored file not found")
    return FileResponse(str(p))


@router.get("/signed-url")
async def get_signed_url(path: str = Query(...)):
    url = signed_url_for(path)
    if not url:
        raise HTTPException(400, "Signed URL is only available for GCS-backed assets")
    return {"url": url}
