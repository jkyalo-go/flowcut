from datetime import datetime, timedelta


def test_owner_can_invite(client, workspace_a):
    ws_id, token = workspace_a
    resp = client.post(
        "/invitations",
        json={"email": "newmember@test.com", "role": "editor"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "invite_token" in data
    assert data["email"] == "newmember@test.com"


def test_accept_invitation_creates_membership_and_switches_session(client, workspace_a, workspace_b, db):
    invited_ws_id, owner_token = workspace_a
    current_ws_id, _ = workspace_b
    invite_resp = client.post(
        "/invitations",
        json={"email": "joiner@test.com", "role": "editor"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    invite_token = invite_resp.json()["invite_token"]
    from uuid import uuid4
    from domain.identity import AuthSession, Membership, User
    joiner = User(email="joiner@test.com", name="Joiner", user_type="user")
    db.add(joiner)
    db.flush()
    joiner_token = str(uuid4())
    db.add(Membership(workspace_id=current_ws_id, user_id=joiner.id, role="editor"))
    db.add(AuthSession(user_id=joiner.id, workspace_id=current_ws_id, token=joiner_token))
    db.commit()
    accept_resp = client.post(
        f"/invitations/{invite_token}/accept",
        headers={"Authorization": f"Bearer {joiner_token}"},
    )
    assert accept_resp.status_code == 200
    membership = db.query(Membership).filter(Membership.workspace_id == invited_ws_id, Membership.user_id == joiner.id).first()
    assert membership is not None
    assert membership.role == "editor"
    payload = accept_resp.json()
    assert payload["workspace"]["id"] == invited_ws_id
    assert payload["token"] != joiner_token


def test_editor_cannot_invite(client, workspace_a, db):
    ws_id, owner_token = workspace_a
    from domain.identity import User, Membership, AuthSession
    from uuid import uuid4
    editor = User(email="editor@test.local", name="Editor")
    db.add(editor)
    db.flush()
    db.add(Membership(workspace_id=ws_id, user_id=editor.id, role="editor"))
    editor_token = str(uuid4())
    db.add(AuthSession(user_id=editor.id, workspace_id=ws_id, token=editor_token))
    db.commit()

    resp = client.post(
        "/invitations",
        json={"email": "x@x.com", "role": "editor"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert resp.status_code == 403


def test_invalid_role_is_rejected(client, workspace_a):
    _, token = workspace_a
    resp = client.post(
        "/invitations",
        json={"email": "badrole@test.com", "role": "super-admin"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
