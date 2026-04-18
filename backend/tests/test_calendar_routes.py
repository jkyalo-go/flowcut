from datetime import datetime, timedelta, timezone

from domain.platforms import CalendarSlot
from domain.projects import Project
from domain.shared import PlatformType


def test_calendar_gaps_returns_frontend_contract(client, workspace_a, db):
    workspace_id, token = workspace_a
    project = Project(
        workspace_id=workspace_id,
        name="Calendar Project",
        intake_mode="upload",
        source_type="upload",
    )
    db.add(project)
    db.flush()
    slot = CalendarSlot(
        workspace_id=workspace_id,
        project_id=project.id,
        platform=PlatformType.YOUTUBE,
        scheduled_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1),
        status="scheduled",
    )
    db.add(slot)
    db.commit()

    resp = client.get(
        "/api/calendar/gaps?platform=youtube",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert "gaps" in payload
    if payload["gaps"]:
        first = payload["gaps"][0]
        assert set(first.keys()) == {"platform", "suggested_at", "score"}
        assert isinstance(first["suggested_at"], str)
        assert isinstance(first["score"], float)
