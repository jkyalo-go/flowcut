import base64
import logging
from datetime import datetime, timedelta
from typing import Callable

logger = logging.getLogger(__name__)

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import google.auth.transport.requests

from sqlalchemy import text
from sqlalchemy.orm import Session
from domain.platforms import PlatformConnection
from domain.shared import PlatformType
from config import (
    YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REDIRECT_URI, PROCESSED_DIR,
)
from services.token_crypto import decrypt_token, encrypt_token


def _enc(token: str | None) -> str | None:
    """Encrypt and base64-encode a token for DB storage."""
    if not token:
        return None
    return base64.b64encode(encrypt_token(token)).decode()


def _dec(stored: str | None) -> str | None:
    """Decrypt a base64-encoded AES-GCM token from the DB."""
    if not stored:
        return None
    try:
        return decrypt_token(base64.b64decode(stored))
    except Exception:
        logger.info("Token decrypt fallback: treating stored value as plaintext (legacy or unencrypted row)")
        return stored


SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

CLIENT_CONFIG = {
    "web": {
        "client_id": YOUTUBE_CLIENT_ID,
        "client_secret": YOUTUBE_CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [YOUTUBE_REDIRECT_URI],
    }
}

def _new_flow() -> Flow:
    flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES)
    flow.redirect_uri = YOUTUBE_REDIRECT_URI
    return flow


def get_auth_url(state: str | None = None) -> str:
    if not YOUTUBE_CLIENT_ID or not YOUTUBE_CLIENT_SECRET:
        raise RuntimeError("YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET must be set")

    auth_url, _ = _new_flow().authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
        state=state,
    )
    return auth_url


def exchange_code(code: str, db: Session, workspace_id: str | None = None) -> str:
    flow = _new_flow()
    flow.fetch_token(code=code)

    creds = flow.credentials

    # Fetch channel name
    channel_name = None
    try:
        yt = build("youtube", "v3", credentials=creds)
        resp = yt.channels().list(part="snippet", mine=True).execute()
        items = resp.get("items", [])
        if items:
            channel_name = items[0]["snippet"]["title"]
    except Exception as e:
        logger.warning(f"Could not fetch channel name: {e}")

    if workspace_id is None:
        workspace = db.execute(text("SELECT id FROM workspaces ORDER BY created_at ASC LIMIT 1")).fetchone()
        if workspace is None:
            raise RuntimeError("No workspace available for YouTube connection")
        workspace_id = workspace[0]

    cred = db.query(PlatformConnection).filter(
        PlatformConnection.workspace_id == workspace_id,
        PlatformConnection.platform == PlatformType.YOUTUBE,
    ).first()
    if cred is None:
        cred = PlatformConnection(
            workspace_id=workspace_id,
            platform=PlatformType.YOUTUBE,
        )
        db.add(cred)
    cred.account_name = channel_name
    cred.access_token = _enc(creds.token)
    cred.refresh_token = _enc(creds.refresh_token)
    cred.token_expiry = creds.expiry
    db.commit()

    logger.info(f"YouTube authenticated as: {channel_name}")
    return channel_name or "Unknown Channel"


def get_credentials(db: Session, workspace_id: str | None = None, connection: PlatformConnection | None = None) -> Credentials | None:
    row = connection
    if row is None:
        query = db.query(PlatformConnection).filter(PlatformConnection.platform == PlatformType.YOUTUBE)
        if workspace_id is not None:
            query = query.filter(PlatformConnection.workspace_id == workspace_id)
        row = query.first()
    if not row:
        return None

    creds = Credentials(
        token=_dec(row.access_token),
        refresh_token=_dec(row.refresh_token),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=YOUTUBE_CLIENT_ID,
        client_secret=YOUTUBE_CLIENT_SECRET,
        expiry=row.token_expiry,
    )

    # Refresh if expired
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(google.auth.transport.requests.Request())
            row.access_token = _enc(creds.token)
            row.token_expiry = creds.expiry
            db.commit()
            logger.info("Refreshed YouTube access token")
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            return None

    return creds


def get_auth_status(db: Session, workspace_id: str | None = None) -> dict:
    query = db.query(PlatformConnection).filter(PlatformConnection.platform == PlatformType.YOUTUBE)
    if workspace_id is not None:
        query = query.filter(PlatformConnection.workspace_id == workspace_id)
    row = query.first()
    if not row:
        return {"authenticated": False, "channel_name": None}

    # Check if credentials are still usable
    creds = get_credentials(db, workspace_id=workspace_id, connection=row)
    if creds is None:
        return {"authenticated": False, "channel_name": None}

    return {"authenticated": True, "channel_name": row.account_name}


def upload_video(
    project_id: str,
    workspace_id: str,
    title: str,
    description: str,
    tags: list[str],
    category_id: str,
    privacy_status: str,
    thumbnail_index: int | None,
    db: Session,
    connection: PlatformConnection | None = None,
    progress_callback: Callable[[int], None] | None = None,
) -> str:
    creds = get_credentials(db, workspace_id=workspace_id, connection=connection)
    if creds is None:
        raise RuntimeError("Not authenticated with YouTube. Connect your account first.")

    youtube = build("youtube", "v3", credentials=creds)

    render_path = str(PROCESSED_DIR / f"project_{project_id}_render.mp4")

    # YouTube forbids < and > in titles, and limits to 100 characters
    if not title or not title.strip():
        raise ValueError("Video title cannot be empty")
    invalid_chars = [c for c in ['<', '>'] if c in title]
    if invalid_chars:
        raise ValueError(
            f"Video title contains invalid characters: {' '.join(invalid_chars)}  "
            "YouTube does not allow < or > in titles."
        )
    if len(title) > 100:
        raise ValueError(f"Video title is {len(title)} characters — YouTube allows a maximum of 100.")

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        render_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=10 * 1024 * 1024,  # 10 MB chunks
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    video_id = None
    while True:
        status, response = request.next_chunk()
        if status and progress_callback:
            progress_callback(int(status.progress() * 100))
        if response:
            video_id = response["id"]
            break

    logger.info(f"Uploaded video: https://youtu.be/{video_id}")

    # Set custom thumbnail if selected
    if thumbnail_index is not None:
        thumb_path = str(PROCESSED_DIR / f"project_{project_id}_thumbnail_{thumbnail_index}.jpg")
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumb_path, mimetype="image/jpeg"),
            ).execute()
            logger.info("Custom thumbnail set")
        except Exception as e:
            logger.warning(f"Could not set custom thumbnail (channel may need verification): {e}")

    return video_id


def revoke_credentials(db: Session, workspace_id: str | None = None):
    query = db.query(PlatformConnection).filter(PlatformConnection.platform == PlatformType.YOUTUBE)
    if workspace_id is not None:
        query = query.filter(PlatformConnection.workspace_id == workspace_id)
    row = query.first()
    if row:
        try:
            import requests
            requests.post(
                "https://oauth2.googleapis.com/revoke",
                params={"token": _dec(row.access_token)},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        except Exception as e:
            logger.warning(f"Token revocation failed: {e}")
        delete_query = db.query(PlatformConnection).filter(PlatformConnection.platform == PlatformType.YOUTUBE)
        if workspace_id is not None:
            delete_query = delete_query.filter(PlatformConnection.workspace_id == workspace_id)
        delete_query.delete()
        db.commit()
        logger.info("YouTube credentials revoked")
