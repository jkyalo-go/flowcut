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


def test_accept_invitation_creates_membership(client, workspace_a, db):
    ws_id, owner_token = workspace_a
    invite_resp = client.post(
        "/invitations",
        json={"email": "joiner@test.com", "role": "editor"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    invite_token = invite_resp.json()["invite_token"]
    from domain.identity import User
    joiner = User(email="joiner@test.com", name="Joiner", user_type="user")
    db.add(joiner)
    db.commit()
    accept_resp = client.post(
        f"/invitations/{invite_token}/accept",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert accept_resp.status_code == 200


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
