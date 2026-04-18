import json
from datetime import UTC, datetime

from sqlalchemy import func as sqlfunc
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


def check_quota(workspace_id: str, dimension: str, requested_quantity: float, db) -> bool:
    """Returns True if quota remains, False if exceeded.

    Uses QuotaPolicy for the limit and aggregates UsageLedger for the current
    period (calendar month) usage. If no QuotaPolicy exists, defaults to
    unlimited (returns True).
    """
    from domain.enterprise import QuotaPolicy

    policy = db.query(QuotaPolicy).filter(
        QuotaPolicy.workspace_id == workspace_id,
    ).first()
    if not policy:
        return True  # no policy configured → unlimited

    # Map dimension names to QuotaPolicy columns
    limit_map = {
        "storage_mb": policy.storage_quota_mb,
        "ai_spend_usd": policy.ai_spend_cap_usd,
        "render_minutes": policy.render_minutes_quota,
    }
    limit_value = limit_map.get(dimension)
    if limit_value is None:
        return True  # unknown dimension → allow
    if limit_value < 0:
        return True  # -1 = unlimited

    # Sum usage for the current calendar month
    period_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    used = db.query(
        sqlfunc.coalesce(sqlfunc.sum(UsageLedger.quantity), 0.0)
    ).filter(
        UsageLedger.workspace_id == workspace_id,
        UsageLedger.category == dimension,
        UsageLedger.created_at >= period_start,
    ).scalar() or 0.0
    return (used + requested_quantity) <= limit_value
