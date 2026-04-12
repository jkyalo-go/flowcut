from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import AppSettings
from schemas import SettingsResponse, SettingsUpdate

router = APIRouter()

DEFAULTS = {
    "timezone": "America/New_York",
}


def _get_setting(db: Session, key: str) -> str:
    row = db.query(AppSettings).filter(AppSettings.key == key).first()
    return row.value if row else DEFAULTS.get(key, "")


def _set_setting(db: Session, key: str, value: str) -> None:
    row = db.query(AppSettings).filter(AppSettings.key == key).first()
    if row:
        row.value = value
    else:
        db.add(AppSettings(key=key, value=value))
    db.commit()


@router.get("", response_model=SettingsResponse)
def get_settings(db: Session = Depends(get_db)):
    return SettingsResponse(
        timezone=_get_setting(db, "timezone"),
    )


@router.put("", response_model=SettingsResponse)
def update_settings(body: SettingsUpdate, db: Session = Depends(get_db)):
    if body.timezone is not None:
        _set_setting(db, "timezone", body.timezone)
    return SettingsResponse(
        timezone=_get_setting(db, "timezone"),
    )
