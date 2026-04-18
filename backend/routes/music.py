import random

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from contracts.media import MusicAutoResponse, MusicItemResponse, VolumeKeypoint
from database import get_db
from dependencies import get_current_workspace
from domain.media import Asset, MusicItem, TimelineItem
from domain.shared import AssetType
from routes import require_project
from services.ducker import compute_volume_envelope

router = APIRouter()


def _build_timeline_segments(items: list[TimelineItem]) -> tuple[list[dict], float]:
    """Walk ordered timeline items and produce sequential segment dicts."""
    segments = []
    cursor = 0.0
    for item in items:
        if item.sub_clip_id and item.sub_clip:
            sub = item.sub_clip
            duration = sub.end_time - sub.start_time
            clip_type = sub.parent_clip.clip_type.value if sub.parent_clip and sub.parent_clip.clip_type else None
        elif item.clip_id and item.clip:
            clip = item.clip
            duration = clip.duration or 0
            clip_type = clip.clip_type.value if clip.clip_type else None
        else:
            continue

        if duration < 0.034:
            continue

        segments.append({
            "start": cursor,
            "end": cursor + duration,
            "clip_type": clip_type,
        })
        cursor += duration

    return segments, cursor


def _music_item_to_response(item: MusicItem) -> MusicItemResponse:
    return MusicItemResponse(
        id=item.id,
        asset_id=item.asset_id,
        asset_name=item.asset.name if item.asset else "Unknown",
        start_time=item.start_time,
        end_time=item.end_time,
        volume=item.volume,
    )


@router.get("/{project_id}", response_model=MusicAutoResponse)
def get_music(
    project_id: str,
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    require_project(project_id, workspace.id, db)

    items = (
        db.query(MusicItem)
        .filter(
            MusicItem.project_id == project_id,
            MusicItem.workspace_id == workspace.id,
        )
        .order_by(MusicItem.start_time)
        .all()
    )

    timeline_items = (
        db.query(TimelineItem)
        .filter(TimelineItem.project_id == project_id)
        .order_by(TimelineItem.position)
        .all()
    )
    segments, total_duration = _build_timeline_segments(timeline_items)
    envelope = compute_volume_envelope(segments, total_duration)

    return MusicAutoResponse(
        items=[_music_item_to_response(mi) for mi in items],
        volume_envelope=[VolumeKeypoint(**kp) for kp in envelope],
    )


@router.post("/{project_id}/auto", response_model=MusicAutoResponse)
def auto_place_music(
    project_id: str,
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    require_project(project_id, workspace.id, db)

    # Compute total timeline duration
    timeline_items = (
        db.query(TimelineItem)
        .filter(TimelineItem.project_id == project_id)
        .order_by(TimelineItem.position)
        .all()
    )
    segments, total_duration = _build_timeline_segments(timeline_items)

    if total_duration <= 0:
        raise HTTPException(400, "Timeline is empty")

    # Fetch music assets scoped to this workspace
    music_assets = (
        db.query(Asset)
        .filter(
            Asset.asset_type == AssetType.MUSIC,
            Asset.workspace_id == workspace.id,
        )
        .all()
    )
    if not music_assets:
        raise HTTPException(400, "No music assets in library")

    # Shuffle and place back-to-back
    shuffled = list(music_assets)
    random.shuffle(shuffled)

    db.query(MusicItem).filter(
        MusicItem.project_id == project_id,
        MusicItem.workspace_id == workspace.id,
    ).delete()

    new_items = []
    cursor = 0.0
    idx = 0
    while cursor < total_duration:
        asset = shuffled[idx % len(shuffled)]
        end = min(cursor + asset.duration, total_duration)
        item = MusicItem(
            project_id=project_id,
            asset_id=asset.id,
            start_time=cursor,
            end_time=end,
            volume=0.25,
            workspace_id=workspace.id,
        )
        db.add(item)
        new_items.append(item)
        cursor = end
        idx += 1

    db.commit()
    for item in new_items:
        db.refresh(item)

    envelope = compute_volume_envelope(segments, total_duration)

    return MusicAutoResponse(
        items=[_music_item_to_response(mi) for mi in new_items],
        volume_envelope=[VolumeKeypoint(**kp) for kp in envelope],
    )


@router.delete("/{project_id}")
def clear_music(
    project_id: str,
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    require_project(project_id, workspace.id, db)

    db.query(MusicItem).filter(
        MusicItem.project_id == project_id,
        MusicItem.workspace_id == workspace.id,
    ).delete()
    db.commit()
    return {"ok": True}
