"""
Proves that routes cannot access data from a different workspace.
Each test creates two workspaces (A, B), seeds a project in A,
then tries to read it with B's token. Should get 404, not the data.
"""
import pytest
from fastapi.testclient import TestClient

from domain.projects import Project


def _make_project(db, workspace_id: str, name: str = "My Project") -> str:
    p = Project(
        workspace_id=workspace_id,
        name=name,
        intake_mode="upload",
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p.id


# ── captions ──────────────────────────────────────────────────────────────────

def test_get_captions_blocked_for_foreign_workspace(client, db, workspace_a, workspace_b):
    ws_a_id, token_a = workspace_a
    _ws_b_id, token_b = workspace_b
    project_id = _make_project(db, ws_a_id)

    # Workspace B's token must not read workspace A's project captions
    resp = client.get(
        f"/api/captions/{project_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404


def test_auto_generate_captions_blocked_for_foreign_workspace(client, db, workspace_a, workspace_b):
    ws_a_id, token_a = workspace_a
    _ws_b_id, token_b = workspace_b
    project_id = _make_project(db, ws_a_id)

    resp = client.post(
        f"/api/captions/{project_id}/auto",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code in (400, 404)  # 404 = not found, 400 = no timeline (still blocked correctly)


# ── titles ────────────────────────────────────────────────────────────────────

def test_get_titles_blocked_for_foreign_workspace(client, db, workspace_a, workspace_b):
    ws_a_id, _token_a = workspace_a
    _ws_b_id, token_b = workspace_b
    project_id = _make_project(db, ws_a_id)

    resp = client.get(
        f"/api/titles/{project_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404


# ── timestamps ────────────────────────────────────────────────────────────────

def test_get_timestamps_blocked_for_foreign_workspace(client, db, workspace_a, workspace_b):
    ws_a_id, _token_a = workspace_a
    _ws_b_id, token_b = workspace_b
    project_id = _make_project(db, ws_a_id)

    resp = client.get(
        f"/api/timestamps/{project_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404


# ── trackers ──────────────────────────────────────────────────────────────────

def test_get_trackers_blocked_for_foreign_workspace(client, db, workspace_a, workspace_b):
    ws_a_id, _token_a = workspace_a
    _ws_b_id, token_b = workspace_b
    project_id = _make_project(db, ws_a_id)

    resp = client.get(
        f"/api/trackers/{project_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404


# ── subscribes ────────────────────────────────────────────────────────────────

def test_get_subscribes_blocked_for_foreign_workspace(client, db, workspace_a, workspace_b):
    ws_a_id, _token_a = workspace_a
    _ws_b_id, token_b = workspace_b
    project_id = _make_project(db, ws_a_id)

    resp = client.get(
        f"/api/subscribes/{project_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404


# ── music ─────────────────────────────────────────────────────────────────────

def test_get_music_blocked_for_foreign_workspace(client, db, workspace_a, workspace_b):
    ws_a_id, _token_a = workspace_a
    _ws_b_id, token_b = workspace_b
    project_id = _make_project(db, ws_a_id)

    resp = client.get(
        f"/api/music/{project_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404


# ── generate ──────────────────────────────────────────────────────────────────

def test_generate_titles_blocked_for_foreign_workspace(client, db, workspace_a, workspace_b):
    ws_a_id, _token_a = workspace_a
    _ws_b_id, token_b = workspace_b
    project_id = _make_project(db, ws_a_id)

    resp = client.post(
        f"/api/projects/{project_id}/generate-titles",  # mounted under /api/projects, not /api/generate
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404


# ── assets ────────────────────────────────────────────────────────────────────

def test_list_assets_requires_auth(client, db, workspace_a):
    resp = client.get("/api/assets/")
    assert resp.status_code == 401


def test_list_assets_scoped_to_workspace(client, db, workspace_a, workspace_b):
    from domain.media import Asset
    ws_a_id, token_a = workspace_a
    _ws_b_id, token_b = workspace_b

    asset = Asset(workspace_id=ws_a_id, name="track.mp3", file_path="/tmp/track.mp3", asset_type="music", duration=120.0)
    db.add(asset)
    db.commit()

    # Workspace A sees its asset
    resp_a = client.get("/api/assets/", headers={"Authorization": f"Bearer {token_a}"})
    assert resp_a.status_code == 200
    ids_a = [a["id"] for a in resp_a.json()]
    assert str(asset.id) in ids_a

    # Workspace B does NOT see workspace A's asset
    resp_b = client.get("/api/assets/", headers={"Authorization": f"Bearer {token_b}"})
    assert resp_b.status_code == 200
    ids_b = [a["id"] for a in resp_b.json()]
    assert str(asset.id) not in ids_b
