from __future__ import annotations

import base64
import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from services.token_crypto import decrypt_token, encrypt_token


def _encrypt_token_str(token: str | None) -> str | None:
    """Encrypt a token string and return base64-encoded ciphertext for DB storage."""
    if not token:
        return None
    return base64.b64encode(encrypt_token(token)).decode()


def _decrypt_token_str(stored: str | None) -> str | None:
    """Decrypt a base64-encoded ciphertext token from the DB back to plaintext."""
    if not stored:
        return None
    try:
        return decrypt_token(base64.b64decode(stored))
    except Exception:
        # Fallback: token may have been stored as plaintext before encryption was introduced
        return stored

from config import (
    INSTAGRAM_CLIENT_ID,
    INSTAGRAM_CLIENT_SECRET,
    INSTAGRAM_REDIRECT_URI,
    LINKEDIN_CLIENT_ID,
    LINKEDIN_CLIENT_SECRET,
    LINKEDIN_REDIRECT_URI,
    TIKTOK_CLIENT_ID,
    TIKTOK_CLIENT_SECRET,
    TIKTOK_REDIRECT_URI,
    X_CLIENT_ID,
    X_CLIENT_SECRET,
    X_REDIRECT_URI,
)
from domain.platforms import PlatformAuthState, PlatformConnection
from domain.shared import PlatformType
from services.youtube_service import exchange_code as exchange_youtube_code
from services.youtube_service import get_auth_status as get_youtube_auth_status
from services.youtube_service import get_auth_url as get_youtube_auth_url
from services.youtube_service import revoke_credentials as revoke_youtube_credentials


MANUAL_PLATFORM_REQUIREMENTS: dict[str, list[str]] = {
    PlatformType.INSTAGRAM_REELS.value: ["access_token", "ig_user_id"],
}

@dataclass
class AuthStartResponse:
    mode: str
    auth_url: str | None = None
    instructions: str | None = None
    required_fields: list[str] | None = None


def _state_for(db: Session, platform: str, workspace_id: str, code_verifier: str | None = None) -> str:
    state = secrets.token_urlsafe(24)
    row = PlatformAuthState(
        workspace_id=workspace_id,
        platform=platform,
        state=state,
        code_verifier=code_verifier,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=20),
    )
    db.add(row)
    db.commit()
    return state


def _consume_state(db: Session, platform: str, workspace_id: str, state: str | None) -> dict[str, Any]:
    if not state:
        raise RuntimeError("Invalid or expired auth state.")
    row = db.query(PlatformAuthState).filter(PlatformAuthState.state == state).first()
    if not row or row.expires_at <= datetime.now(timezone.utc):
        raise RuntimeError("Invalid or expired auth state.")
    row_platform = row.platform.value if hasattr(row.platform, "value") else str(row.platform)
    if row_platform != platform or row.workspace_id != workspace_id:
        raise RuntimeError("Auth state does not match the current platform/workspace.")
    payload = {
        "platform": row_platform,
        "workspace_id": row.workspace_id,
        "code_verifier": row.code_verifier,
    }
    db.delete(row)
    db.commit()
    return payload


def _upsert_connection(
    db: Session,
    workspace_id: str,
    platform: str,
    *,
    account_name: str | None = None,
    account_id: str | None = None,
    access_token: str | None = None,
    refresh_token: str | None = None,
    token_expiry: datetime | None = None,
    metadata: dict | None = None,
) -> PlatformConnection:
    row = db.query(PlatformConnection).filter(
        PlatformConnection.workspace_id == workspace_id,
        PlatformConnection.platform == platform,
    ).first()
    metadata_json = json.dumps(metadata or {})
    if row:
        row.account_name = account_name or row.account_name
        row.account_id = account_id or row.account_id
        row.access_token = _encrypt_token_str(access_token) if access_token else row.access_token
        row.refresh_token = _encrypt_token_str(refresh_token) if refresh_token else row.refresh_token
        row.token_expiry = token_expiry or row.token_expiry
        row.metadata_json = metadata_json
    else:
        row = PlatformConnection(
            workspace_id=workspace_id,
            platform=platform,
            account_name=account_name,
            account_id=account_id,
            access_token=_encrypt_token_str(access_token),
            refresh_token=_encrypt_token_str(refresh_token),
            token_expiry=token_expiry,
            metadata_json=metadata_json,
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _tiktok_auth_url(db: Session, workspace_id: str) -> str:
    state = _state_for(db, PlatformType.TIKTOK.value, workspace_id)
    query = urlencode(
        {
            "client_key": TIKTOK_CLIENT_ID,
            "scope": "user.info.basic,video.publish",
            "response_type": "code",
            "redirect_uri": TIKTOK_REDIRECT_URI,
            "state": state,
        }
    )
    return f"https://www.tiktok.com/v2/auth/authorize/?{query}"


def _linkedin_auth_url(db: Session, workspace_id: str) -> str:
    state = _state_for(db, PlatformType.LINKEDIN.value, workspace_id)
    query = urlencode(
        {
            "response_type": "code",
            "client_id": LINKEDIN_CLIENT_ID,
            "redirect_uri": LINKEDIN_REDIRECT_URI,
            "state": state,
            "scope": "openid profile w_member_social",
        }
    )
    return f"https://www.linkedin.com/oauth/v2/authorization?{query}"


def _x_auth_url(db: Session, workspace_id: str) -> str:
    code_verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).decode().rstrip("=")
    state = _state_for(db, PlatformType.X.value, workspace_id, code_verifier=code_verifier)
    query = urlencode(
        {
            "response_type": "code",
            "client_id": X_CLIENT_ID,
            "redirect_uri": X_REDIRECT_URI,
            "scope": "tweet.read tweet.write users.read offline.access",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"https://x.com/i/oauth2/authorize?{query}"


def _instagram_auth_url(db: Session, workspace_id: str) -> str:
    state = _state_for(db, PlatformType.INSTAGRAM_REELS.value, workspace_id)
    query = urlencode(
        {
            "client_id": INSTAGRAM_CLIENT_ID,
            "redirect_uri": INSTAGRAM_REDIRECT_URI,
            "scope": "instagram_business_basic,instagram_business_content_publish",
            "response_type": "code",
            "state": state,
        }
    )
    return f"https://www.instagram.com/oauth/authorize?{query}"


def platform_auth_status(db: Session, workspace_id: str, platform: str) -> dict:
    if platform == PlatformType.YOUTUBE.value:
        status = get_youtube_auth_status(db, workspace_id=workspace_id)
        return {"platform": platform, "mode": "oauth", **status}

    row = db.query(PlatformConnection).filter(
        PlatformConnection.workspace_id == workspace_id,
        PlatformConnection.platform == platform,
    ).first()
    metadata = {}
    if row and row.metadata_json:
        try:
            metadata = json.loads(row.metadata_json) or {}
        except Exception:
            metadata = {}
    required_fields = MANUAL_PLATFORM_REQUIREMENTS.get(platform, [])
    checks = {
        "access_token": bool(row and row.access_token),
        "ig_user_id": bool(metadata.get("ig_user_id")),
    }
    missing_fields = [field for field in required_fields if not checks.get(field)]
    return {
        "platform": platform,
        "mode": "oauth" if platform in {PlatformType.TIKTOK.value, PlatformType.LINKEDIN.value, PlatformType.X.value, PlatformType.INSTAGRAM_REELS.value} else "manual_token",
        "authenticated": row is not None and not missing_fields,
        "missing_fields": missing_fields,
        "required_fields": required_fields,
        "account_name": row.account_name if row else None,
    }


def platform_auth_start(db: Session, platform: str, workspace_id: str) -> AuthStartResponse:
    if platform == PlatformType.YOUTUBE.value:
        state = _state_for(db, PlatformType.YOUTUBE.value, workspace_id)
        return AuthStartResponse(mode="oauth", auth_url=get_youtube_auth_url(state=state))
    if platform == PlatformType.TIKTOK.value:
        return AuthStartResponse(mode="oauth", auth_url=_tiktok_auth_url(db, workspace_id))
    if platform == PlatformType.LINKEDIN.value:
        return AuthStartResponse(mode="oauth", auth_url=_linkedin_auth_url(db, workspace_id))
    if platform == PlatformType.X.value:
        return AuthStartResponse(mode="oauth", auth_url=_x_auth_url(db, workspace_id))
    if platform == PlatformType.INSTAGRAM_REELS.value and INSTAGRAM_CLIENT_ID and INSTAGRAM_CLIENT_SECRET:
        return AuthStartResponse(mode="oauth", auth_url=_instagram_auth_url(db, workspace_id))
    if platform == PlatformType.INSTAGRAM_REELS.value:
        return AuthStartResponse(
            mode="manual_token",
            instructions="Provide an Instagram Graph access token and IG user id.",
            required_fields=MANUAL_PLATFORM_REQUIREMENTS[platform],
        )
    raise ValueError(f"Unsupported platform: {platform}")


def complete_platform_auth(db: Session, workspace_id: str | None, platform: str, code: str, state: str | None) -> PlatformConnection:
    if platform == PlatformType.YOUTUBE.value:
        if workspace_id is None:
            auth_state = db.query(PlatformAuthState).filter(PlatformAuthState.state == state).first()
            if not auth_state:
                raise RuntimeError("Workspace is required for YouTube callback completion.")
            workspace_id = auth_state.workspace_id
            db.delete(auth_state)
            db.commit()
        exchange_youtube_code(code, db, workspace_id=workspace_id)
        row = db.query(PlatformConnection).filter(
            PlatformConnection.workspace_id == workspace_id,
            PlatformConnection.platform == platform,
        ).first()
        if not row:
            raise RuntimeError("YouTube auth completed but no connection was persisted for this workspace.")
        return row

    if workspace_id is None:
        auth_state = db.query(PlatformAuthState).filter(PlatformAuthState.state == state).first()
        if not auth_state:
            raise RuntimeError("Invalid or expired auth state.")
        workspace_id = str(auth_state.workspace_id)
    pending = _consume_state(db, platform, workspace_id, state)

    if platform == PlatformType.TIKTOK.value:
        with httpx.Client(timeout=120) as client:
            response = client.post(
                "https://open.tiktokapis.com/v2/oauth/token/",
                data={
                    "client_key": TIKTOK_CLIENT_ID,
                    "client_secret": TIKTOK_CLIENT_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": TIKTOK_REDIRECT_URI,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if response.status_code >= 300:
                raise RuntimeError(f"TikTok token exchange failed: {response.text}")
            token_data = response.json()
            profile_response = client.get(
                "https://open.tiktokapis.com/v2/user/info/?fields=display_name,avatar_url,open_id,union_id",
                headers={"Authorization": f"Bearer {token_data.get('access_token')}"},
            )
            profile_data = profile_response.json() if profile_response.status_code < 300 else {}
        user_data = (profile_data.get("data") or {}).get("user") or {}
        expires_in = int(token_data.get("expires_in") or 0)
        return _upsert_connection(
            db,
            workspace_id,
            platform,
            account_name=user_data.get("display_name") or "TikTok account",
            account_id=str(user_data.get("open_id") or token_data.get("open_id", "tiktok-account")),
            access_token=token_data.get("access_token"),
            refresh_token=token_data.get("refresh_token"),
            token_expiry=datetime.now(timezone.utc) + timedelta(seconds=expires_in) if expires_in else None,
            metadata={"token_response": token_data, "profile": profile_data},
        )

    if platform == PlatformType.LINKEDIN.value:
        with httpx.Client(timeout=120) as client:
            token_response = client.post(
                "https://www.linkedin.com/oauth/v2/accessToken",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": LINKEDIN_CLIENT_ID,
                    "client_secret": LINKEDIN_CLIENT_SECRET,
                    "redirect_uri": LINKEDIN_REDIRECT_URI,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if token_response.status_code >= 300:
                raise RuntimeError(f"LinkedIn token exchange failed: {token_response.text}")
            token_data = token_response.json()
            profile_response = client.get(
                "https://api.linkedin.com/v2/userinfo",
                headers={"Authorization": f"Bearer {token_data.get('access_token')}"},
            )
            profile_data = profile_response.json() if profile_response.status_code < 300 else {}
        sub = str(profile_data.get("sub", "linkedin-account"))
        expires_in = int(token_data.get("expires_in") or 0)
        return _upsert_connection(
            db,
            workspace_id,
            platform,
            account_name=profile_data.get("name") or "LinkedIn account",
            account_id=sub,
            access_token=token_data.get("access_token"),
            refresh_token=token_data.get("refresh_token"),
            token_expiry=datetime.now(timezone.utc) + timedelta(seconds=expires_in) if expires_in else None,
            metadata={"author_urn": f"urn:li:person:{sub}", "token_response": token_data, "profile": profile_data},
        )

    if platform == PlatformType.X.value:
        code_verifier = pending.get("code_verifier")
        with httpx.Client(timeout=120) as client:
            token_response = client.post(
                "https://api.x.com/2/oauth2/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": X_REDIRECT_URI,
                    "client_id": X_CLIENT_ID,
                    "code_verifier": code_verifier,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                auth=(X_CLIENT_ID, X_CLIENT_SECRET) if X_CLIENT_SECRET else None,
            )
            if token_response.status_code >= 300:
                raise RuntimeError(f"X token exchange failed: {token_response.text}")
            token_data = token_response.json()
            me_response = client.get(
                "https://api.x.com/2/users/me",
                headers={"Authorization": f"Bearer {token_data.get('access_token')}"},
            )
            me_data = me_response.json() if me_response.status_code < 300 else {}
        user_data = me_data.get("data", {})
        expires_in = int(token_data.get("expires_in") or 0)
        return _upsert_connection(
            db,
            workspace_id,
            platform,
            account_name=user_data.get("name") or "X account",
            account_id=user_data.get("id") or "x-account",
            access_token=token_data.get("access_token"),
            refresh_token=token_data.get("refresh_token"),
            token_expiry=datetime.now(timezone.utc) + timedelta(seconds=expires_in) if expires_in else None,
            metadata={"token_response": token_data, "profile": me_data},
        )

    if platform == PlatformType.INSTAGRAM_REELS.value and INSTAGRAM_CLIENT_ID and INSTAGRAM_CLIENT_SECRET:
        with httpx.Client(timeout=120) as client:
            token_response = client.post(
                "https://api.instagram.com/oauth/access_token",
                data={
                    "client_id": INSTAGRAM_CLIENT_ID,
                    "client_secret": INSTAGRAM_CLIENT_SECRET,
                    "grant_type": "authorization_code",
                    "redirect_uri": INSTAGRAM_REDIRECT_URI,
                    "code": code,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if token_response.status_code >= 300:
                raise RuntimeError(f"Instagram token exchange failed: {token_response.text}")
            token_data = token_response.json()
            profile_response = client.get(
                "https://graph.instagram.com/me",
                params={"fields": "id,username", "access_token": token_data.get("access_token")},
            )
            profile_data = profile_response.json() if profile_response.status_code < 300 else {}
        user_id = str(token_data.get("user_id", "instagram-account"))
        return _upsert_connection(
            db,
            workspace_id,
            platform,
            account_name=profile_data.get("username") or "Instagram account",
            account_id=user_id,
            access_token=token_data.get("access_token"),
            refresh_token=None,
            metadata={"ig_user_id": profile_data.get("id") or user_id, "token_response": token_data, "profile": profile_data},
        )

    raise RuntimeError(f"Platform `{platform}` does not support callback completion in the current configuration.")


def disconnect_platform_auth(db: Session, workspace_id: str, platform: str) -> None:
    if platform == PlatformType.YOUTUBE.value:
        revoke_youtube_credentials(db, workspace_id=workspace_id)
        return
    db.query(PlatformConnection).filter(
        PlatformConnection.workspace_id == workspace_id,
        PlatformConnection.platform == platform,
    ).delete()
    db.commit()


def ensure_valid_platform_connection(db: Session, connection: PlatformConnection) -> PlatformConnection:
    if not connection.token_expiry or connection.token_expiry > datetime.now(timezone.utc) + timedelta(minutes=2):
        return connection
    platform = connection.platform.value if hasattr(connection.platform, "value") else str(connection.platform)
    if not connection.refresh_token:
        return connection

    # Decrypt the stored refresh token before sending it to the platform API
    raw_refresh_token = _decrypt_token_str(connection.refresh_token)

    refreshed: dict[str, Any] | None = None
    if platform == PlatformType.TIKTOK.value:
        with httpx.Client(timeout=120) as client:
            response = client.post(
                "https://open.tiktokapis.com/v2/oauth/token/",
                data={
                    "client_key": TIKTOK_CLIENT_ID,
                    "client_secret": TIKTOK_CLIENT_SECRET,
                    "grant_type": "refresh_token",
                    "refresh_token": raw_refresh_token,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if response.status_code < 300:
                refreshed = response.json()
    elif platform == PlatformType.LINKEDIN.value:
        with httpx.Client(timeout=120) as client:
            response = client.post(
                "https://www.linkedin.com/oauth/v2/accessToken",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": raw_refresh_token,
                    "client_id": LINKEDIN_CLIENT_ID,
                    "client_secret": LINKEDIN_CLIENT_SECRET,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if response.status_code < 300:
                refreshed = response.json()
    elif platform == PlatformType.X.value:
        with httpx.Client(timeout=120) as client:
            response = client.post(
                "https://api.x.com/2/oauth2/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": raw_refresh_token,
                    "client_id": X_CLIENT_ID,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                auth=(X_CLIENT_ID, X_CLIENT_SECRET) if X_CLIENT_SECRET else None,
            )
            if response.status_code < 300:
                refreshed = response.json()

    if not refreshed:
        return connection

    # Re-encrypt new tokens before persisting
    new_access = refreshed.get("access_token")
    new_refresh = refreshed.get("refresh_token")
    connection.access_token = _encrypt_token_str(new_access) if new_access else connection.access_token
    connection.refresh_token = _encrypt_token_str(new_refresh) if new_refresh else connection.refresh_token
    expires_in = int(refreshed.get("expires_in") or 0)
    if expires_in:
        connection.token_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    metadata = {}
    if connection.metadata_json:
        try:
            metadata = json.loads(connection.metadata_json) or {}
        except Exception:
            metadata = {}
    metadata["refresh_response"] = refreshed
    connection.metadata_json = json.dumps(metadata)
    db.commit()
    db.refresh(connection)
    return connection
