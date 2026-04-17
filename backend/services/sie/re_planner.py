from __future__ import annotations
import json
import logging
from datetime import datetime, timezone

from database import SessionLocal

logger = logging.getLogger(__name__)


async def re_plan_clip(clip_id: str, corrections: list[dict]):
    """Re-generate the edit plan for a rejected clip incorporating creator corrections."""
    from domain.media import Clip
    from domain.projects import StyleProfile
    db = SessionLocal()
    try:
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            return

        profile = None
        if hasattr(clip, 'profile_id') and clip.profile_id:
            profile = db.query(StyleProfile).filter(StyleProfile.id == clip.profile_id).first()

        style_doc = {}
        if profile and profile.style_doc:
            try:
                style_doc = json.loads(profile.style_doc)
            except Exception:
                pass

        correction_text = "; ".join(c.get("instruction", "") for c in corrections if c.get("instruction"))
        augmented_style = {**style_doc, "corrections_to_apply": correction_text}

        try:
            from services.sie.planner import generate_edit_plan
            moments = []
            footage_duration = 60.0
            if hasattr(clip, 'moment_start_sec') and clip.moment_start_sec is not None:
                moments = [{"start_sec": clip.moment_start_sec, "end_sec": clip.moment_end_sec or 60.0,
                            "score": getattr(clip, 'moment_score', None) or 0.7,
                            "type": getattr(clip, 'moment_type', None) or "highlight"}]
                footage_duration = (clip.moment_end_sec or 60.0) + 5.0

            manifest = generate_edit_plan(
                footage_path=getattr(clip, 'source_path', '') or '',
                footage_duration_sec=footage_duration,
                moments=moments,
                style_profile=augmented_style,
                episodic_context=[{"correction": correction_text}],
            )

            if hasattr(clip, 'edit_manifest'):
                clip.edit_manifest = manifest.model_dump_json()
            if hasattr(clip, 'edit_confidence'):
                clip.edit_confidence = manifest.confidence

        except Exception as e:
            logger.warning("Re-plan generate_edit_plan failed for clip %s: %s", clip_id, e)

        if hasattr(clip, 'review_corrections'):
            clip.review_corrections = json.dumps(corrections)
        if hasattr(clip, 'status'):
            clip.status = "draft"
        db.commit()

        if profile and getattr(profile, 'mem0_user_id', None):
            try:
                from services.sie.memory import store_edit_episode
                store_edit_episode(
                    profile.mem0_user_id, clip_id,
                    f"re-plan with corrections: {correction_text}",
                    critique=None, action="correction",
                )
            except Exception:
                pass
    except Exception as e:
        logger.error("Re-plan failed for clip %s: %s", clip_id, e)
        db.rollback()
    finally:
        db.close()
