import json
from sqlalchemy.orm import Session

from domain.automation import AuditLog, Notification


def record_audit(
    db: Session,
    workspace_id: str,
    action: str,
    target_type: str,
    target_id: str | None = None,
    actor: str = "system",
    user_id: str | None = None,
    reason: str | None = None,
    metadata: dict | None = None,
) -> AuditLog:
    row = AuditLog(
        workspace_id=workspace_id,
        user_id=user_id,
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=target_id,
        reason=reason,
        metadata_json=json.dumps(metadata or {}),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def create_notification(
    db: Session,
    workspace_id: str,
    category: str,
    title: str,
    body: str,
    user_id: str | None = None,
    metadata: dict | None = None,
) -> Notification:
    row = Notification(
        workspace_id=workspace_id,
        user_id=user_id,
        category=category,
        title=title,
        body=body,
        metadata_json=json.dumps(metadata or {}),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
