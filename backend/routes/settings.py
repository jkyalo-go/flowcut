from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from contracts.projects import SettingsResponse, SettingsUpdate
from database import get_db
from dependencies import get_current_workspace
from domain.projects import AppSettings

router = APIRouter()

DEFAULTS = {
    "timezone": "America/New_York",
}


def _get_setting(db: Session, key: str, workspace_id: str | None = None) -> str:
    query = db.query(AppSettings).filter(AppSettings.key == key)
    if workspace_id is not None:
        query = query.filter(AppSettings.workspace_id == workspace_id)
    row = query.first()
    return row.value if row else DEFAULTS.get(key, "")


def _set_setting(db: Session, key: str, value: str, workspace_id: str | None = None) -> None:
    query = db.query(AppSettings).filter(AppSettings.key == key)
    if workspace_id is not None:
        query = query.filter(AppSettings.workspace_id == workspace_id)
    row = query.first()
    if row:
        row.value = value
        db.commit()
    else:
        try:
            db.add(AppSettings(workspace_id=workspace_id, key=key, value=value))
            db.commit()
        except IntegrityError:
            db.rollback()
            row = query.first()
            if row:
                row.value = value
                db.commit()


@router.get("", response_model=SettingsResponse)
def get_settings(workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    return SettingsResponse(
        timezone=_get_setting(db, "timezone", workspace.id),
        workspace_id=workspace.id,
        ai_policy=workspace.ai_policy,
    )


@router.put("", response_model=SettingsResponse)
def update_settings(body: SettingsUpdate, workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    if body.timezone is not None:
        _set_setting(db, "timezone", body.timezone, workspace.id)
    if body.ai_policy is not None:
        workspace.ai_policy = body.ai_policy
        db.commit()
    return SettingsResponse(
        timezone=_get_setting(db, "timezone", workspace.id),
        workspace_id=workspace.id,
        ai_policy=workspace.ai_policy,
    )
