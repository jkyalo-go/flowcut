import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from config import PROCESSED_DIR
from contracts.generation import MetadataRequest, ThumbnailRequest
from database import get_db
from dependencies import get_current_workspace
from domain.media import Clip
from routes import require_project
from services.thumbnail_generator import compose_thumbnail, extract_frame
from services.title_generator import generate_description, generate_tags, generate_titles

router = APIRouter()


def _get_combined_transcript(project_id: str, workspace_id: str, db: Session) -> str:
    clips = db.query(Clip).filter(
        Clip.project_id == project_id,
        Clip.workspace_id == workspace_id,
        Clip.transcript.isnot(None),
        Clip.transcript != "",
    ).all()
    combined = "\n".join(c.transcript for c in clips if c.transcript)
    if not combined.strip():
        raise HTTPException(400, "No transcripts available. Process some clips first.")
    return combined


@router.post("/{project_id}/generate-titles")
def gen_titles(
    project_id: str,
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    require_project(project_id, workspace.id, db)
    combined = _get_combined_transcript(project_id, workspace.id, db)
    try:
        titles = generate_titles(db, workspace, combined)
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        raise HTTPException(502, f"Title generation failed: {e}")
    return {"titles": titles}


@router.post("/{project_id}/generate-description")
def gen_description(
    project_id: str,
    body: MetadataRequest,
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    require_project(project_id, workspace.id, db)
    combined = _get_combined_transcript(project_id, workspace.id, db)
    try:
        description = generate_description(db, workspace, combined, body.title, body.system_prompt)
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        raise HTTPException(502, f"Description generation failed: {e}")
    return {"description": description}


@router.post("/{project_id}/generate-tags")
def gen_tags(
    project_id: str,
    body: MetadataRequest,
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    require_project(project_id, workspace.id, db)
    combined = _get_combined_transcript(project_id, workspace.id, db)
    try:
        tags = generate_tags(db, workspace, combined, body.title)
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        raise HTTPException(502, f"Tag generation failed: {e}")
    return {"tags": tags}


@router.post("/{project_id}/generate-thumbnails")
async def gen_thumbnails(
    project_id: str,
    body: ThumbnailRequest,
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    require_project(project_id, workspace.id, db)

    clips = db.query(Clip).filter(
        Clip.project_id == project_id,
        Clip.workspace_id == workspace.id,
        Clip.clip_type == "broll",
        Clip.status == "done",
    ).all()
    if not clips:
        clips = db.query(Clip).filter(
            Clip.project_id == project_id,
            Clip.workspace_id == workspace.id,
            Clip.status == "done",
        ).all()
    if not clips:
        raise HTTPException(400, "No processed clips available for thumbnail.")

    candidates: list[tuple[str, float]] = []
    for clip in clips:
        if clip.sub_clips:
            for sc in clip.sub_clips:
                candidates.append((clip.source_path, (sc.start_time + sc.end_time) / 2))
        elif clip.duration:
            for frac in [0.25, 0.5, 0.75]:
                candidates.append((clip.source_path, clip.duration * frac))

    if not candidates:
        candidates = [(clips[0].source_path, 1.0)]

    import random
    random.shuffle(candidates)
    total_slots = 4
    selected = candidates[:min(total_slots, len(candidates))]

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    thumbnail_urls: list[str] = []
    candidate_idx = 0

    for idx in range(total_slots):
        url = f"/static/processed/project_{project_id}_thumbnail_{idx}.jpg"
        output_path = str(PROCESSED_DIR / f"project_{project_id}_thumbnail_{idx}.jpg")

        if idx in body.skip_indices:
            thumbnail_urls.append(url)
            continue

        if candidate_idx >= len(selected):
            break

        source_path, frame_time = selected[candidate_idx]
        candidate_idx += 1

        try:
            frame_path = await extract_frame(source_path, frame_time)
        except RuntimeError:
            continue

        try:
            compose_thumbnail(frame_path, body.title, output_path)
            thumbnail_urls.append(url)
        except Exception:
            pass
        finally:
            if os.path.exists(frame_path):
                os.unlink(frame_path)

    if not thumbnail_urls:
        raise HTTPException(500, "Failed to generate any thumbnails.")

    return {"thumbnail_urls": thumbnail_urls}
