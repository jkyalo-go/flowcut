from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)

import httpx
from sqlalchemy.orm import Session

from config import PROCESSED_DIR
from domain.media import Clip
from domain.platforms import CalendarSlot, PlatformConnection
from domain.projects import Project
from domain.shared import PlatformType, ReviewStatus
from services.audit import create_notification, record_audit
from services.enterprise import record_usage
from services.platform_auth import ensure_valid_platform_connection
from services.storage import signed_url_for
from services.token_crypto import decrypt_token
from services.youtube_service import upload_video

import base64


def _decrypt_stored_token(stored: str | None) -> str | None:
    """Decrypt a base64-encoded AES-GCM ciphertext token from the DB."""
    if not stored:
        return None
    try:
        return decrypt_token(base64.b64decode(stored))
    except Exception:
        logger.info("Token decrypt fallback: treating stored value as plaintext (legacy or unencrypted row)")
        return stored


class PlatformPublishError(RuntimeError):
    pass


@dataclass
class PublishPayload:
    title: str
    description: str
    tags: list[str]
    privacy_status: str
    thumbnail_index: int | None = None


@dataclass
class PublishResult:
    remote_id: str
    publish_url: str | None = None
    raw: dict | None = None
    status: str = "published"


@dataclass
class SyncResult:
    status: str
    publish_url: str | None = None
    raw: dict | None = None


class PlatformAdapter(Protocol):
    platform: PlatformType

    def publish(
        self,
        db: Session,
        workspace_id: str,
        project: Project,
        connection: PlatformConnection,
        payload: PublishPayload,
        render_path: Path,
    ) -> PublishResult:
        ...

    def sync_status(
        self,
        db: Session,
        workspace_id: str,
        project: Project,
        connection: PlatformConnection,
        remote_id: str,
        slot_metadata: dict,
    ) -> SyncResult:
        ...


def _parse_metadata(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _render_path_for_project(project: Project) -> Path:
    if project.render_path:
        return Path(project.render_path)
    return PROCESSED_DIR / f"project_{project.id}_render.mp4"


def _public_video_url(project: Project) -> str:
    if project.render_path:
        maybe = signed_url_for(project.render_path)
        if maybe:
            return maybe
    raise PlatformPublishError("This platform requires a publicly accessible render URL. Configure GCS-backed render storage.")


def _require_account_id(connection: PlatformConnection, field_name: str = "account_id") -> str:
    if connection.account_id:
        return connection.account_id
    metadata = _parse_metadata(connection.metadata_json)
    value = metadata.get(field_name)
    if value:
        return str(value)
    raise PlatformPublishError(f"Platform connection is missing `{field_name}`.")


def _auth_headers(connection: PlatformConnection) -> dict[str, str]:
    if not connection.access_token:
        raise PlatformPublishError("Platform connection is missing an access token.")
    raw_token = _decrypt_stored_token(connection.access_token)
    if not raw_token:
        raise PlatformPublishError("Platform connection is missing an access token.")
    return {"Authorization": f"Bearer {raw_token}"}


def _x_create_tweet(connection: PlatformConnection, status_text: str, media_id: str | None) -> PublishResult:
    headers = _auth_headers(connection) | {"Content-Type": "application/json"}
    payload: dict[str, object] = {"text": status_text[:280]}
    if media_id:
        payload["media"] = {"media_ids": [media_id]}
    with httpx.Client(timeout=120) as client:
        response = client.post("https://api.x.com/2/tweets", headers=headers, json=payload)
        if response.status_code >= 300:
            raise PlatformPublishError(f"X publish failed: {response.text}")
        data = response.json()
    tweet_id = str(data.get("data", {}).get("id", ""))
    return PublishResult(remote_id=tweet_id, publish_url=f"https://x.com/i/web/status/{tweet_id}", raw=data)


def _x_upload_video(connection: PlatformConnection, render_path: Path) -> str:
    headers = _auth_headers(connection)
    total_bytes = render_path.stat().st_size
    with httpx.Client(timeout=300) as client:
        init_response = client.post(
            "https://upload.twitter.com/1.1/media/upload.json",
            headers=headers,
            data={
                "command": "INIT",
                "media_type": "video/mp4",
                "media_category": "tweet_video",
                "total_bytes": str(total_bytes),
            },
        )
        if init_response.status_code >= 300:
            raise PlatformPublishError(f"X media INIT failed: {init_response.text}")
        init_data = init_response.json()
        media_id = str(init_data.get("media_id_string") or init_data.get("media_id") or "")
        if not media_id:
            raise PlatformPublishError("X media INIT did not return a media id.")

        chunk_size = 5 * 1024 * 1024
        with render_path.open("rb") as handle:
            segment_index = 0
            while True:
                chunk = handle.read(chunk_size)
                if not chunk:
                    break
                append_response = client.post(
                    "https://upload.twitter.com/1.1/media/upload.json",
                    headers=headers,
                    data={"command": "APPEND", "media_id": media_id, "segment_index": str(segment_index)},
                    files={"media": ("chunk.bin", chunk, "application/octet-stream")},
                )
                if append_response.status_code >= 300:
                    raise PlatformPublishError(f"X media APPEND failed: {append_response.text}")
                segment_index += 1

        finalize_response = client.post(
            "https://upload.twitter.com/1.1/media/upload.json",
            headers=headers,
            data={"command": "FINALIZE", "media_id": media_id},
        )
        if finalize_response.status_code >= 300:
            raise PlatformPublishError(f"X media FINALIZE failed: {finalize_response.text}")
        finalize_data = finalize_response.json()
        processing = finalize_data.get("processing_info")
        while processing and processing.get("state") in {"pending", "in_progress"}:
            wait_seconds = int(processing.get("check_after_secs") or 2)
            import time
            time.sleep(wait_seconds)
            status_response = client.get(
                "https://upload.twitter.com/1.1/media/upload.json",
                headers=headers,
                params={"command": "STATUS", "media_id": media_id},
            )
            if status_response.status_code >= 300:
                raise PlatformPublishError(f"X media STATUS failed: {status_response.text}")
            status_data = status_response.json()
            processing = status_data.get("processing_info")
        if processing and processing.get("state") == "failed":
            raise PlatformPublishError(f"X media processing failed: {processing}")
    return media_id


class YouTubeAdapter:
    platform = PlatformType.YOUTUBE

    def publish(self, db: Session, workspace_id: str, project: Project, connection: PlatformConnection, payload: PublishPayload, render_path: Path) -> PublishResult:
        video_id = upload_video(
            project_id=project.id,
            workspace_id=workspace_id,
            title=payload.title,
            description=payload.description,
            tags=payload.tags,
            category_id=project.video_category or "22",
            privacy_status=payload.privacy_status,
            thumbnail_index=payload.thumbnail_index,
            db=db,
            connection=connection,
        )
        return PublishResult(remote_id=video_id, publish_url=f"https://youtu.be/{video_id}")

    def sync_status(self, db: Session, workspace_id: str, project: Project, connection: PlatformConnection, remote_id: str, slot_metadata: dict) -> SyncResult:
        return SyncResult(status="published", publish_url=f"https://youtu.be/{remote_id}")


class TikTokAdapter:
    platform = PlatformType.TIKTOK

    def publish(self, db: Session, workspace_id: str, project: Project, connection: PlatformConnection, payload: PublishPayload, render_path: Path) -> PublishResult:
        headers = _auth_headers(connection) | {"Content-Type": "application/json"}
        metadata = _parse_metadata(connection.metadata_json)
        privacy_level = metadata.get("privacy_level", "SELF_ONLY")
        with httpx.Client(timeout=300) as client:
            init_response = client.post(
                "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/",
                headers=headers,
                json={
                    "post_info": {
                        "title": payload.title[:150],
                        "privacy_level": privacy_level,
                        "disable_duet": bool(metadata.get("disable_duet", False)),
                        "disable_comment": bool(metadata.get("disable_comment", False)),
                        "disable_stitch": bool(metadata.get("disable_stitch", False)),
                    },
                    "source_info": {
                        "source": "FILE_UPLOAD",
                        "video_size": render_path.stat().st_size,
                        "chunk_size": render_path.stat().st_size,
                        "total_chunk_count": 1,
                    },
                },
            )
            if init_response.status_code >= 300:
                raise PlatformPublishError(f"TikTok init failed: {init_response.text}")
            init_data = init_response.json()
            data = init_data.get("data") or {}
            upload_url = data.get("upload_url")
            publish_id = data.get("publish_id") or data.get("video_id") or ""
            if not upload_url:
                raise PlatformPublishError("TikTok did not return an upload URL.")
            with render_path.open("rb") as handle:
                upload_response = client.put(upload_url, content=handle.read(), headers={"Content-Type": "video/mp4"})
            if upload_response.status_code >= 300:
                raise PlatformPublishError(f"TikTok upload failed: {upload_response.text}")
        return PublishResult(remote_id=str(publish_id), raw=init_data, status="processing")

    def sync_status(self, db: Session, workspace_id: str, project: Project, connection: PlatformConnection, remote_id: str, slot_metadata: dict) -> SyncResult:
        headers = _auth_headers(connection)
        with httpx.Client(timeout=120) as client:
            response = client.post(
                "https://open.tiktokapis.com/v2/post/publish/status/fetch/",
                headers=headers | {"Content-Type": "application/json"},
                json={"publish_id": remote_id},
            )
            if response.status_code >= 300:
                return SyncResult(status=slot_metadata.get("platform_status", "processing"), raw={"error": response.text})
            data = response.json()
        publish_status = str((data.get("data") or {}).get("status", "processing")).lower()
        normalized = "published" if "publish" in publish_status or publish_status == "success" else "processing"
        return SyncResult(status=normalized, raw=data)


class InstagramReelsAdapter:
    platform = PlatformType.INSTAGRAM_REELS

    def publish(self, db: Session, workspace_id: str, project: Project, connection: PlatformConnection, payload: PublishPayload, render_path: Path) -> PublishResult:
        ig_user_id = _require_account_id(connection, "ig_user_id")
        video_url = _public_video_url(project)
        headers = _auth_headers(connection)
        with httpx.Client(timeout=180) as client:
            create_response = client.post(
                f"https://graph.facebook.com/v23.0/{ig_user_id}/media",
                headers=headers,
                data={
                    "media_type": "REELS",
                    "video_url": video_url,
                    "caption": payload.description[:2200] or payload.title,
                    "share_to_feed": "true",
                },
            )
            if create_response.status_code >= 300:
                raise PlatformPublishError(f"Instagram media creation failed: {create_response.text}")
            creation_id = str(create_response.json().get("id", ""))
            if not creation_id:
                raise PlatformPublishError("Instagram did not return a creation id.")
            publish_response = client.post(
                f"https://graph.facebook.com/v23.0/{ig_user_id}/media_publish",
                headers=headers,
                data={"creation_id": creation_id},
            )
            if publish_response.status_code >= 300:
                raise PlatformPublishError(f"Instagram media publish failed: {publish_response.text}")
            media_id = str(publish_response.json().get("id", creation_id))
        return PublishResult(remote_id=media_id, publish_url=f"https://www.instagram.com/reel/{media_id}/")

    def sync_status(self, db: Session, workspace_id: str, project: Project, connection: PlatformConnection, remote_id: str, slot_metadata: dict) -> SyncResult:
        headers = _auth_headers(connection)
        with httpx.Client(timeout=120) as client:
            response = client.get(
                f"https://graph.facebook.com/v23.0/{remote_id}",
                headers=headers,
                params={"fields": "status,status_code,permalink"},
            )
            if response.status_code >= 300:
                return SyncResult(status=slot_metadata.get("platform_status", "processing"), raw={"error": response.text})
            data = response.json()
        status_code = str(data.get("status_code") or data.get("status") or "").upper()
        publish_url = data.get("permalink") or f"https://www.instagram.com/reel/{remote_id}/"
        normalized = "published" if status_code in {"FINISHED", "PUBLISHED"} or not status_code else "processing"
        return SyncResult(status=normalized, publish_url=publish_url, raw=data)


class LinkedInAdapter:
    platform = PlatformType.LINKEDIN

    def publish(self, db: Session, workspace_id: str, project: Project, connection: PlatformConnection, payload: PublishPayload, render_path: Path) -> PublishResult:
        author_urn = _require_account_id(connection, "author_urn")
        headers = _auth_headers(connection)
        rest_headers = headers | {
            "LinkedIn-Version": "202501",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=300) as client:
            init_response = client.post(
                "https://api.linkedin.com/rest/videos?action=initializeUpload",
                headers=rest_headers,
                json={"initializeUploadRequest": {"owner": author_urn, "fileSizeBytes": render_path.stat().st_size}},
            )
            if init_response.status_code >= 300:
                raise PlatformPublishError(f"LinkedIn initialize upload failed: {init_response.text}")
            init_data = init_response.json()
            value = init_data.get("value") or {}
            upload_instructions = value.get("uploadInstructions") or []
            if not upload_instructions:
                raise PlatformPublishError("LinkedIn did not return upload instructions.")
            upload_url = upload_instructions[0].get("uploadUrl")
            video_urn = value.get("video")
            if not upload_url or not video_urn:
                raise PlatformPublishError("LinkedIn upload response missing upload url or video urn.")
            with render_path.open("rb") as handle:
                upload_response = client.put(upload_url, content=handle.read(), headers={"Content-Type": "application/octet-stream"})
            if upload_response.status_code >= 300:
                raise PlatformPublishError(f"LinkedIn binary upload failed: {upload_response.text}")

            post_response = client.post(
                "https://api.linkedin.com/rest/posts",
                headers=rest_headers,
                json={
                    "author": author_urn,
                    "commentary": payload.description[:3000] or payload.title,
                    "visibility": "PUBLIC",
                    "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
                    "content": {"media": {"id": video_urn}},
                    "lifecycleState": "PUBLISHED",
                    "isReshareDisabledByAuthor": False,
                },
            )
            if post_response.status_code >= 300:
                raise PlatformPublishError(f"LinkedIn post publish failed: {post_response.text}")
            post_id = str(post_response.json().get("id", video_urn))
        return PublishResult(remote_id=post_id, raw={"video": video_urn}, status="processing")

    def sync_status(self, db: Session, workspace_id: str, project: Project, connection: PlatformConnection, remote_id: str, slot_metadata: dict) -> SyncResult:
        headers = _auth_headers(connection) | {
            "LinkedIn-Version": "202501",
            "X-Restli-Protocol-Version": "2.0.0",
        }
        with httpx.Client(timeout=120) as client:
            response = client.get(f"https://api.linkedin.com/rest/posts/{remote_id}", headers=headers)
            if response.status_code >= 300:
                return SyncResult(status=slot_metadata.get("platform_status", "processing"), raw={"error": response.text})
            data = response.json()
        lifecycle = str(data.get("lifecycleState") or "").upper()
        normalized = "published" if lifecycle == "PUBLISHED" else "processing"
        return SyncResult(status=normalized, raw=data)


class XAdapter:
    platform = PlatformType.X

    def publish(self, db: Session, workspace_id: str, project: Project, connection: PlatformConnection, payload: PublishPayload, render_path: Path) -> PublishResult:
        media_id = _x_upload_video(connection, render_path)
        text = payload.description or payload.title
        return _x_create_tweet(connection, text, str(media_id) if media_id else None)

    def sync_status(self, db: Session, workspace_id: str, project: Project, connection: PlatformConnection, remote_id: str, slot_metadata: dict) -> SyncResult:
        return SyncResult(status="published", publish_url=f"https://x.com/i/web/status/{remote_id}")


ADAPTERS: dict[str, PlatformAdapter] = {
    PlatformType.YOUTUBE.value: YouTubeAdapter(),
    PlatformType.TIKTOK.value: TikTokAdapter(),
    PlatformType.INSTAGRAM_REELS.value: InstagramReelsAdapter(),
    PlatformType.LINKEDIN.value: LinkedInAdapter(),
    PlatformType.X.value: XAdapter(),
}


def publish_slot(db: Session, slot: CalendarSlot, project: Project, connection: PlatformConnection) -> PublishResult:
    connection = ensure_valid_platform_connection(db, connection)
    adapter = ADAPTERS.get(slot.platform.value if hasattr(slot.platform, "value") else str(slot.platform))
    if not adapter:
        raise PlatformPublishError(f"No adapter registered for platform `{slot.platform}`.")
    payload_data = _parse_metadata(slot.metadata_json)
    payload = PublishPayload(
        title=str(payload_data.get("title", "")),
        description=str(payload_data.get("description", "")),
        tags=list(payload_data.get("tags", [])),
        privacy_status=str(payload_data.get("privacy_status", "private")),
        thumbnail_index=payload_data.get("thumbnail_index"),
    )
    render_path = _render_path_for_project(project)
    if not render_path.exists():
        raise PlatformPublishError("Render not found. Export the video first.")
    return adapter.publish(db, slot.workspace_id, project, connection, payload, render_path)


def _update_slot_metadata(slot: CalendarSlot, patch: dict) -> None:
    current = _parse_metadata(slot.metadata_json)
    current.update(patch)
    slot.metadata_json = json.dumps(current)


def sync_slot_status(db: Session, slot: CalendarSlot) -> CalendarSlot:
    project = db.query(Project).filter(Project.id == slot.project_id).first()
    if not project:
        raise PlatformPublishError("Project not found for calendar slot.")
    connection = db.query(PlatformConnection).filter(
        PlatformConnection.workspace_id == slot.workspace_id,
        PlatformConnection.platform == slot.platform,
    ).first()
    if not connection:
        raise PlatformPublishError("Platform connection not found for calendar slot.")
    connection = ensure_valid_platform_connection(db, connection)
    adapter = ADAPTERS.get(slot.platform.value if hasattr(slot.platform, "value") else str(slot.platform))
    if not adapter:
        raise PlatformPublishError(f"No adapter registered for platform `{slot.platform}`.")
    metadata = _parse_metadata(slot.metadata_json)
    remote_id = str(metadata.get("remote_id", "")).strip()
    if not remote_id:
        return slot
    result = adapter.sync_status(db, slot.workspace_id, project, connection, remote_id, metadata)
    slot.status = result.status
    if result.publish_url:
        slot.publish_url = result.publish_url
    _update_slot_metadata(slot, {"platform_status": result.status, "sync_raw": result.raw or {}})
    if result.status == "published":
        slot.failure_reason = None
    db.commit()
    return slot


def execute_slot(db: Session, slot: CalendarSlot) -> CalendarSlot:
    project = db.query(Project).filter(Project.id == slot.project_id).first()
    if not project:
        raise PlatformPublishError("Project not found for calendar slot.")
    connection = db.query(PlatformConnection).filter(
        PlatformConnection.workspace_id == slot.workspace_id,
        PlatformConnection.platform == slot.platform,
    ).first()
    if not connection:
        raise PlatformPublishError("Platform connection not found for calendar slot.")
    slot.status = "publishing"
    db.commit()

    try:
        result = publish_slot(db, slot, project, connection)
    except Exception as exc:
        slot.status = "failed"
        slot.failure_reason = str(exc)
        slot.retry_count = (slot.retry_count or 0) + 1
        db.commit()
        record_audit(
            db,
            workspace_id=slot.workspace_id,
            actor="system",
            action="publish.failed",
            target_type="calendar_slot",
            target_id=slot.id,
            reason=str(exc),
            metadata={"platform": slot.platform.value if hasattr(slot.platform, "value") else str(slot.platform)},
        )
        create_notification(
            db,
            workspace_id=slot.workspace_id,
            category="publish",
            title="Flowcut publish failed",
            body=str(exc),
            metadata={"slot_id": slot.id, "project_id": slot.project_id},
        )
        raise

    slot.status = result.status
    slot.publish_url = result.publish_url
    slot.failure_reason = None
    _update_slot_metadata(
        slot,
        {
            "remote_id": result.remote_id,
            "platform_status": result.status,
            "publish_raw": result.raw or {},
        },
    )
    db.commit()
    record_usage(
        db,
        workspace_id=slot.workspace_id,
        project_id=slot.project_id,
        category="publish_jobs",
        quantity=1.0,
        unit="job",
        amount_usd=0.0,
        correlation_id=slot.correlation_id or slot.id,
        metadata={"platform": slot.platform.value if hasattr(slot.platform, "value") else str(slot.platform), "render_variant": slot.render_variant},
    )

    clip = db.query(Clip).filter(Clip.id == slot.clip_id).first() if slot.clip_id else None
    if clip and result.status == "published":
        clip.review_status = ReviewStatus.PUBLISHED
        db.commit()

    record_audit(
        db,
        workspace_id=slot.workspace_id,
        actor="system",
        action="publish.succeeded" if result.status == "published" else "publish.started",
        target_type="calendar_slot",
        target_id=slot.id,
        metadata={
            "platform": slot.platform.value if hasattr(slot.platform, "value") else str(slot.platform),
            "publish_url": result.publish_url,
            "remote_id": result.remote_id,
            "status": result.status,
        },
    )
    create_notification(
        db,
        workspace_id=slot.workspace_id,
        category="publish",
        title="Flowcut publish completed" if result.status == "published" else "Flowcut publish started",
        body=f"{slot.platform.value if hasattr(slot.platform, 'value') else slot.platform} publish {result.status}.",
        metadata={"slot_id": slot.id, "publish_url": result.publish_url, "project_id": slot.project_id, "remote_id": result.remote_id},
    )
    return slot


def execute_due_slots(db: Session, workspace_id: str | None = None) -> list[CalendarSlot]:
    query = db.query(CalendarSlot).filter(CalendarSlot.status.in_(["scheduled", "publishing", "processing"]))
    if workspace_id is not None:
        query = query.filter(CalendarSlot.workspace_id == workspace_id)
    now = datetime.now(timezone.utc)
    slots = query.all()
    scheduled = [slot for slot in slots if slot.status == "scheduled" and (not slot.scheduled_at or slot.scheduled_at <= now)]
    in_flight = [slot for slot in slots if slot.status in {"publishing", "processing"}]
    touched: list[CalendarSlot] = []
    for slot in scheduled:
        touched.append(execute_slot(db, slot))
    for slot in in_flight:
        try:
            touched.append(sync_slot_status(db, slot))
        except Exception:
            continue
    return touched
