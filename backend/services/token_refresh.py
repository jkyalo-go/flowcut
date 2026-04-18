from __future__ import annotations

import logging
from datetime import timedelta

import httpx
from sqlalchemy.orm import Session

from common.time import utc_now
from domain.platforms import PlatformAuth
from services.token_crypto import decrypt_token, encrypt_token

logger = logging.getLogger(__name__)

PLATFORM_REFRESH_URLS = {
    "youtube": "https://oauth2.googleapis.com/token",
    "tiktok": "https://open.tiktokapis.com/v2/oauth/token/",
    "instagram": "https://graph.facebook.com/v19.0/oauth/access_token",
    "linkedin": "https://www.linkedin.com/oauth/v2/accessToken",
    "x": "https://api.x.com/2/oauth2/token",
}


def get_tokens_needing_refresh(db: Session, refresh_window_minutes: int = 10) -> list[PlatformAuth]:
    cutoff = utc_now() + timedelta(minutes=refresh_window_minutes)
    return (
        db.query(PlatformAuth)
        .filter(
            PlatformAuth.status == "active",   # excludes "refreshing" and "error"
            PlatformAuth.token_expires_at != None,
            PlatformAuth.token_expires_at <= cutoff,
            PlatformAuth.refresh_token_enc != None,
        )
        .all()
    )


async def refresh_token(pa: PlatformAuth, db: Session, client_id: str, client_secret: str) -> bool:
    """Refresh a single platform token. Returns True on success, False on failure."""
    refresh_url = PLATFORM_REFRESH_URLS.get(pa.platform)
    if not refresh_url or not pa.refresh_token_enc:
        return False

    try:
        refresh_tok = decrypt_token(pa.refresh_token_enc)
    except Exception:
        pa.status = "error"
        pa.error_message = "refresh token decryption failed"
        db.commit()
        return False

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                refresh_url,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_tok,
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        pa.access_token_enc = encrypt_token(data["access_token"])
        if "refresh_token" in data:
            pa.refresh_token_enc = encrypt_token(data["refresh_token"])
        if "expires_in" in data:
            pa.token_expires_at = utc_now() + timedelta(seconds=int(data["expires_in"]))
        pa.status = "active"
        pa.error_message = None
        db.commit()
        return True

    except Exception as e:
        pa.status = "error"
        pa.error_message = str(e)[:500]
        db.commit()
        logger.error(f"Token refresh failed for {pa.platform} ws={pa.workspace_id}: {e}")
        return False


def refresh_token_sync(pa: PlatformAuth, db: Session, client_id: str, client_secret: str) -> bool:
    """Synchronous version for use in threadpool contexts."""
    refresh_url = PLATFORM_REFRESH_URLS.get(pa.platform)
    if not refresh_url or not pa.refresh_token_enc:
        return False

    try:
        refresh_tok = decrypt_token(pa.refresh_token_enc)
    except Exception:
        pa.status = "error"
        pa.error_message = "refresh token decryption failed"
        db.commit()
        return False

    # Set sentinel before HTTP call so concurrent loop iterations skip this row
    pa.status = "refreshing"
    db.commit()

    try:
        with httpx.Client(timeout=15) as client:
            resp = client.post(
                refresh_url,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_tok,
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        pa.access_token_enc = encrypt_token(data["access_token"])
        if "refresh_token" in data:
            pa.refresh_token_enc = encrypt_token(data["refresh_token"])
        if "expires_in" in data:
            pa.token_expires_at = utc_now() + timedelta(seconds=int(data["expires_in"]))
        pa.status = "active"
        pa.error_message = None
        db.commit()
        return True

    except Exception as e:
        pa.status = "error"
        pa.error_message = str(e)[:500]
        db.commit()
        logger.error("Token refresh failed for %s ws=%s: %s", pa.platform, pa.workspace_id, e)
        return False
