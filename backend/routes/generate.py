import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from contracts.generation import MetadataRequest, ThumbnailRequest
from domain.media import Clip
from domain.projects import Project
from services.title_generator import generate_titles, generate_description, generate_tags
from services.thumbnail_generator import extract_frame, compose_thumbnail
from config import PROCESSED_DIR

router = APIRouter()


@router.post("/{project_id}/generate-titles")
def gen_titles(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")

    clips = db.query(Clip).filter(
        Clip.project_id == project_id,
        Clip.transcript.isnot(None),
        Clip.transcript != "",
    ).all()

    combined = "\n".join(c.transcript for c in clips if c.transcript)
    if not combined.strip():
        raise HTTPException(400, "No transcripts available. Process some clips first.")

    try:
        titles = generate_titles(db, project.workspace, combined)
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        raise HTTPException(502, f"Title generation failed: {e}")

    return {"titles": titles}


def _get_combined_transcript(project_id: str, db: Session) -> str:
    clips = db.query(Clip).filter(
        Clip.project_id == project_id,
        Clip.transcript.isnot(None),
        Clip.transcript != "",
    ).all()
    combined = "\n".join(c.transcript for c in clips if c.transcript)
    if not combined.strip():
        raise HTTPException(400, "No transcripts available. Process some clips first.")
    return combined


@router.post("/{project_id}/generate-description")
def gen_description(project_id: str, body: MetadataRequest, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")

    combined = _get_combined_transcript(project_id, db)

    try:
        description = generate_description(db, project.workspace, combined, body.title, body.system_prompt)
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        raise HTTPException(502, f"Description generation failed: {e}")

    return {"description": description}


@router.post("/{project_id}/generate-tags")
def gen_tags(project_id: str, body: MetadataRequest, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")

    combined = _get_combined_transcript(project_id, db)

    try:
        tags = generate_tags(db, project.workspace, combined, body.title)
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        raise HTTPException(502, f"Tag generation failed: {e}")

    return {"tags": tags}


@router.post("/{project_id}/generate-thumbnails")
async def gen_thumbnails(project_id: str, body: ThumbnailRequest, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")

    # Prefer b-roll clips, fall back to any done clip
    clips = db.query(Clip).filter(
        Clip.project_id == project_id,
        Clip.clip_type == "broll",
        Clip.status == "done",
    ).all()
    if not clips:
        clips = db.query(Clip).filter(
            Clip.project_id == project_id,
            Clip.status == "done",
        ).all()
    if not clips:
        raise HTTPException(400, "No processed clips available for thumbnail.")

    # Collect candidate frame times from different clips/sub_clips
    candidates: list[tuple[str, float]] = []  # (source_path, time)
    for clip in clips:
        if clip.sub_clips:
            for sc in clip.sub_clips:
                candidates.append((clip.source_path, (sc.start_time + sc.end_time) / 2))
        elif clip.duration:
            # Sample a few points from the clip
            for frac in [0.25, 0.5, 0.75]:
                candidates.append((clip.source_path, clip.duration * frac))

    if not candidates:
        candidates = [(clips[0].source_path, 1.0)]

    # Pick up to 4 evenly-spaced candidates, shuffled for variety on regenerate
    import random
    random.shuffle(candidates)
    total_slots = 4
    count = min(total_slots, len(candidates))
    selected = candidates[:count]

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    thumbnail_urls: list[str] = []
    candidate_idx = 0

    for idx in range(total_slots):
        url = f"/static/processed/project_{project_id}_thumbnail_{idx}.jpg"
        output_path = str(PROCESSED_DIR / f"project_{project_id}_thumbnail_{idx}.jpg")

        # Skip locked indices — keep existing file
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
            os.unlink(frame_path)

    if not thumbnail_urls:
        raise HTTPException(500, "Failed to generate any thumbnails.")

    return {"thumbnail_urls": thumbnail_urls}
