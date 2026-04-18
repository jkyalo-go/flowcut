import os

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

try:
    from ..database import get_db
except ImportError:
    from database import get_db

router = APIRouter(tags=["health"])

APP_VERSION = os.environ.get("APP_VERSION", "dev")


@router.get("/healthz")
def healthz():
    return {"status": "ok", "version": APP_VERSION}


@router.get("/readyz")
def readyz(db: Session = Depends(get_db)):
    checks: dict[str, str] = {}
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {type(exc).__name__}"
        return JSONResponse(status_code=503, content={"status": "degraded", "checks": checks})
    return {"status": "ready", "checks": checks}
