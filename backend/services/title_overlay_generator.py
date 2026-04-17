import logging
from sqlalchemy.orm import Session

from database import SessionLocal
from domain.identity import Workspace
from services.title_generator import generate_overlay_plan

logger = logging.getLogger(__name__)


def generate_title_overlays(timestamped_transcript: str, total_duration: float, workspace_id: str) -> list[dict]:
    """Generate section title overlays from a timestamped transcript."""
    db: Session = SessionLocal()
    try:
        workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
        if workspace is None:
            raise RuntimeError("Workspace not found for title overlay generation")
        validated = generate_overlay_plan(db, workspace, timestamped_transcript, total_duration)
        logger.info("Generated %d title overlays for %.1fs video", len(validated), total_duration)
        return validated
    finally:
        db.close()
