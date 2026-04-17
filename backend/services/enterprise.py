import json

from sqlalchemy.orm import Session

from domain.enterprise import AdminActionLog, UsageLedger


def record_usage(
    db: Session,
    workspace_id: str,
    category: str,
    quantity: float,
    unit: str,
    correlation_id: str,
    amount_usd: float = 0.0,
    project_id: str | None = None,
    user_id: str | None = None,
    metadata: dict | None = None,
) -> UsageLedger:
    row = UsageLedger(
        workspace_id=workspace_id,
        project_id=project_id,
        user_id=user_id,
        category=category,
        quantity=quantity,
        unit=unit,
        amount_usd=amount_usd,
        correlation_id=correlation_id,
        metadata_json=json.dumps(metadata or {}),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def record_admin_action(
    db: Session,
    admin_user_id: str,
    action: str,
    target_type: str,
    target_id: str | None = None,
    reason: str | None = None,
    metadata: dict | None = None,
) -> AdminActionLog:
    row = AdminActionLog(
        admin_user_id=admin_user_id,
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
