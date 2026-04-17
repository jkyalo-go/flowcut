from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from domain.platforms import CalendarSlot
from dependencies import get_current_workspace
from services.scheduler import find_gaps

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("/gaps")
def get_gaps(
    platform: str,
    window_days: int = 14,
    db: Session = Depends(get_db),
    workspace=Depends(get_current_workspace),
):
    slots = (
        db.query(CalendarSlot)
        .filter(
            CalendarSlot.workspace_id == workspace.id,
            CalendarSlot.platform == platform,
            CalendarSlot.scheduled_at >= datetime.utcnow(),
        )
        .all()
    )
    slot_dicts = [{"scheduled_at": s.scheduled_at} for s in slots]
    gaps = find_gaps(platform=platform, scheduled_slots=slot_dicts, window_days=window_days)
    return {"gaps": gaps}
