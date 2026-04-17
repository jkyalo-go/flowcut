import asyncio
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import get_db
from contracts.media import AssetResponse
from domain.media import Asset
from domain.shared import AssetType
from config import ASSETS_DIR, AUDIO_EXTENSIONS

router = APIRouter()


async def _probe_duration(file_path: str) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    try:
        return float(stdout.decode().strip())
    except ValueError:
        raise RuntimeError("Could not determine audio duration")


@router.get("", response_model=list[AssetResponse])
def list_assets(asset_type: str | None = Query(None), db: Session = Depends(get_db)):
    q = db.query(Asset)
    if asset_type:
        q = q.filter(Asset.asset_type == asset_type)
    return q.order_by(Asset.created_at.desc()).all()


@router.post("/upload", response_model=AssetResponse)
async def upload_asset(
    file: UploadFile = File(...),
    asset_type: str = Query("music"),
    db: Session = Depends(get_db),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in AUDIO_EXTENSIONS:
        raise HTTPException(400, f"Unsupported audio format: {ext}")

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}_{file.filename}"
    dest = ASSETS_DIR / filename

    content = await file.read()
    dest.write_bytes(content)

    try:
        duration = await _probe_duration(str(dest))
    except Exception:
        dest.unlink(missing_ok=True)
        raise HTTPException(400, "Could not read audio file")

    asset = Asset(
        name=Path(file.filename or filename).stem,
        file_path=str(dest),
        asset_type=AssetType(asset_type),
        duration=duration,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


@router.delete("/{asset_id}")
def delete_asset(asset_id: str, db: Session = Depends(get_db)):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(404, "Asset not found")
    Path(asset.file_path).unlink(missing_ok=True)
    db.delete(asset)
    db.commit()
    return {"ok": True}


@router.get("/{asset_id}/file")
def serve_asset_file(asset_id: str, db: Session = Depends(get_db)):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(404, "Asset not found")
    path = Path(asset.file_path)
    if not path.exists():
        raise HTTPException(404, "File not found on disk")
    return FileResponse(str(path))
