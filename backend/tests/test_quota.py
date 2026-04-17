import pytest


def test_check_quota_passes_when_no_record(db):
    """No QuotaPolicy → quota check always passes."""
    from services.enterprise import check_quota
    result = check_quota("ws-x", "storage_mb", 5.0, db)
    assert result is True


def test_check_quota_fails_when_exceeded(db):
    """Quota check fails when usage + requested exceeds QuotaPolicy limit."""
    from services.enterprise import check_quota
    from domain.enterprise import QuotaPolicy, UsageLedger
    from uuid import uuid4

    ws_id = str(uuid4())
    # Set a tight quota
    db.add(QuotaPolicy(workspace_id=ws_id, storage_quota_mb=10, ai_spend_cap_usd=50.0,
                       render_minutes_quota=300, connected_platforms_quota=2,
                       team_seats_quota=1, retained_footage_days=30))
    db.flush()

    # Record 9.5 MB already used this month
    db.add(UsageLedger(workspace_id=ws_id, category="storage_mb", quantity=9.5,
                       unit="mb", amount_usd=0.0, correlation_id="test-corr-1"))
    db.commit()

    # 9.5 + 1.0 > 10.0 → should fail
    result = check_quota(ws_id, "storage_mb", 1.0, db)
    assert result is False


def test_check_quota_passes_within_limit(db):
    """Quota check passes when usage + requested is within limit."""
    from services.enterprise import check_quota
    from domain.enterprise import QuotaPolicy, UsageLedger
    from uuid import uuid4

    ws_id = str(uuid4())
    db.add(QuotaPolicy(workspace_id=ws_id, storage_quota_mb=100, ai_spend_cap_usd=50.0,
                       render_minutes_quota=300, connected_platforms_quota=2,
                       team_seats_quota=1, retained_footage_days=30))
    db.flush()

    db.add(UsageLedger(workspace_id=ws_id, category="storage_mb", quantity=50.0,
                       unit="mb", amount_usd=0.0, correlation_id="test-corr-2"))
    db.commit()

    # 50 + 10 <= 100 → should pass
    result = check_quota(ws_id, "storage_mb", 10.0, db)
    assert result is True


def test_check_quota_passes_unlimited(db):
    """Quota check passes when policy limit is -1 (unlimited)."""
    from services.enterprise import check_quota
    from domain.enterprise import QuotaPolicy, UsageLedger
    from uuid import uuid4

    ws_id = str(uuid4())
    db.add(QuotaPolicy(workspace_id=ws_id, storage_quota_mb=-1, ai_spend_cap_usd=50.0,
                       render_minutes_quota=300, connected_platforms_quota=2,
                       team_seats_quota=1, retained_footage_days=30))
    db.flush()

    db.add(UsageLedger(workspace_id=ws_id, category="storage_mb", quantity=999.0,
                       unit="mb", amount_usd=0.0, correlation_id="test-corr-3"))
    db.commit()

    result = check_quota(ws_id, "storage_mb", 999.0, db)
    assert result is True
