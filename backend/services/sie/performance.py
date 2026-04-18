from __future__ import annotations

import json
import logging
from datetime import timedelta

from sqlalchemy.orm import Session

from common.time import utc_now
from database import SessionLocal
from domain.platforms import CalendarSlot
from domain.projects import StyleProfile
from services.sie.feedback import apply_feedback_to_profile

logger = logging.getLogger(__name__)
MATURATION_HOURS = 72


def run_performance_feedback_sweep():
    """Check calendar slots published >72h ago and nudge style profiles."""
    db: Session = SessionLocal()
    try:
        cutoff = utc_now() - timedelta(hours=MATURATION_HOURS)
        slots = (
            db.query(CalendarSlot)
            .filter(
                CalendarSlot.scheduled_at <= cutoff,
                CalendarSlot.status == "published",
            )
            .limit(50)
            .all()
        )

        for slot in slots:
            try:
                _process_slot_feedback(slot, db)
                slot.status = "complete"
                db.commit()
            except Exception as e:
                logger.error(f"Performance feedback failed for slot {slot.id}: {e}")
                db.rollback()
    finally:
        db.close()


def _process_slot_feedback(slot: CalendarSlot, db: Session):
    if not slot.clip_id:
        return

    from domain.media import Clip
    clip = db.query(Clip).filter(Clip.id == slot.clip_id).first()
    if not clip:
        return

    # profile_id and edit_manifest are not yet on Clip model — graceful no-op
    profile_id = getattr(clip, "profile_id", None)
    if not profile_id:
        return

    profile = db.query(StyleProfile).filter(StyleProfile.id == profile_id).first()
    if not profile:
        return

    engagement = _estimate_engagement(slot)
    if engagement is None:
        return

    style_doc = json.loads(profile.style_doc or "{}")
    dimension_locks = json.loads(profile.dimension_locks or "{}")
    edit_manifest = json.loads(getattr(clip, "edit_manifest", None) or "{}") if getattr(clip, "edit_manifest", None) else {}

    diff = _engagement_to_diff(engagement, edit_manifest)
    if not diff:
        return

    action = "approved" if engagement > 0.6 else "rejected"
    updated_doc = apply_feedback_to_profile(style_doc, diff, dimension_locks, action=action)
    profile.style_doc = json.dumps(updated_doc)
    profile.version += 1
    db.add(profile)


def _estimate_engagement(slot: CalendarSlot) -> float | None:
    """Return 0.0-1.0 engagement score from stored analytics. None if unavailable."""
    meta = slot.metadata_json
    if not meta:
        return None
    try:
        data = json.loads(meta) if isinstance(meta, str) else meta
        views = data.get("views", 0)
        likes = data.get("likes", 0)
        if views == 0:
            return None
        return min(1.0, (likes / views) * 10)
    except Exception:
        return None


def _engagement_to_diff(engagement: float, manifest: dict) -> dict:
    """High engagement -> reinforce cuts/zooms. Low engagement -> flag pacing."""
    if not manifest:
        return {}
    diff = {}
    if engagement > 0.7 and manifest.get("transitions"):
        diff["transitions"] = f"added {len(manifest['transitions'])} cuts (high engagement)"
    if engagement > 0.7 and manifest.get("zooms"):
        diff["zooms"] = f"added {len(manifest['zooms'])} zooms (high engagement)"
    if engagement < 0.3:
        diff["pacing"] = "low engagement — consider slower cuts"
    return diff
