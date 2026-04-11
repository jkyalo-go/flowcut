import logging
from datetime import datetime, timedelta
from typing import Callable

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import google.auth.transport.requests

from sqlalchemy.orm import Session
from models import YouTubeCredential
from config import (
    YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REDIRECT_URI, PROCESSED_DIR,
)

logger = logging.getLogger(__name__)

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


_pending_flow: Flow | None = None


def get_auth_url() -> str:
    global _pending_flow
    if not YOUTUBE_CLIENT_ID or not YOUTUBE_CLIENT_SECRET:
        raise RuntimeError("YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET must be set")

    _pending_flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES)
    _pending_flow.redirect_uri = YOUTUBE_REDIRECT_URI

    auth_url, _ = _pending_flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )
    return auth_url


def exchange_code(code: str, db: Session) -> str:
    global _pending_flow
    if not _pending_flow:
        raise RuntimeError("No pending auth flow. Start auth first.")
    flow = _pending_flow
    _pending_flow = None
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

    # Upsert credentials — delete any existing, insert new
    db.query(YouTubeCredential).delete()
    cred = YouTubeCredential(
        channel_name=channel_name,
        access_token=creds.token,
        refresh_token=creds.refresh_token,
        token_expiry=creds.expiry,
    )
    db.add(cred)
    db.commit()

    logger.info(f"YouTube authenticated as: {channel_name}")
    return channel_name or "Unknown Channel"


def get_credentials(db: Session) -> Credentials | None:
    row = db.query(YouTubeCredential).first()
    if not row:
        return None

    creds = Credentials(
        token=row.access_token,
        refresh_token=row.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=YOUTUBE_CLIENT_ID,
        client_secret=YOUTUBE_CLIENT_SECRET,
        expiry=row.token_expiry,
    )

    # Refresh if expired
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(google.auth.transport.requests.Request())
            row.access_token = creds.token
            row.token_expiry = creds.expiry
            db.commit()
            logger.info("Refreshed YouTube access token")
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            return None

    return creds


def get_auth_status(db: Session) -> dict:
    row = db.query(YouTubeCredential).first()
    if not row:
        return {"authenticated": False, "channel_name": None}

    # Check if credentials are still usable
    creds = get_credentials(db)
    if creds is None:
        return {"authenticated": False, "channel_name": None}

    return {"authenticated": True, "channel_name": row.channel_name}


def upload_video(
    project_id: int,
    title: str,
    description: str,
    tags: list[str],
    category_id: str,
    privacy_status: str,
    thumbnail_index: int | None,
    db: Session,
    progress_callback: Callable[[int], None] | None = None,
) -> str:
    creds = get_credentials(db)
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


def revoke_credentials(db: Session):
    row = db.query(YouTubeCredential).first()
    if row:
        try:
            import requests
            requests.post(
                "https://oauth2.googleapis.com/revoke",
                params={"token": row.access_token},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        except Exception as e:
            logger.warning(f"Token revocation failed: {e}")
        db.query(YouTubeCredential).delete()
        db.commit()
        logger.info("YouTube credentials revoked")
