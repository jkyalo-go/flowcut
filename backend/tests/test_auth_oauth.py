import pytest
from unittest.mock import patch, AsyncMock
from tests.conftest import _seed_workspace


def test_oauth_start_returns_redirect_url(client):
    resp = client.get("/api/auth/oauth/google/start")
    assert resp.status_code == 200
    body = resp.json()
    assert "redirect_url" in body
    assert "accounts.google.com" in body["redirect_url"]
    assert "state" in body


def test_oauth_callback_creates_user_and_session(client, db):
    from services.oauth import generate_state_token
    import os
    valid_state = generate_state_token(os.getenv("SECRET_KEY", "dev-secret-key-change-in-prod"))
    fake_user_info = {
        "sub": "google-uid-123",
        "email": "creator@gmail.com",
        "name": "Test Creator",
        "picture": "https://lh3.googleusercontent.com/photo.jpg",
    }
    with patch("services.oauth.exchange_google_code", AsyncMock(return_value=fake_user_info)):
        resp = client.post(
            "/api/auth/oauth/google/callback",
            json={"code": "auth-code-123", "state": valid_state},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert "token" in body
    assert "workspace_id" in body
    assert body["user"]["email"] == "creator@gmail.com"


def test_oauth_callback_reuses_existing_user(client, db, workspace_a):
    ws_id, token = workspace_a
    fake_user_info = {
        "sub": "google-uid-999",
        "email": "ws-a@test.local",  # matches seeded user email
        "name": "Workspace A",
        "picture": None,
    }
    from services.oauth import generate_state_token
    import os
    state1 = generate_state_token(os.getenv("SECRET_KEY", "dev-secret-key-change-in-prod"))
    state2 = generate_state_token(os.getenv("SECRET_KEY", "dev-secret-key-change-in-prod"))
    with patch("services.oauth.exchange_google_code", AsyncMock(return_value=fake_user_info)):
        resp1 = client.post("/api/auth/oauth/google/callback", json={"code": "c1", "state": state1})
        resp2 = client.post("/api/auth/oauth/google/callback", json={"code": "c2", "state": state2})
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    t1 = resp1.json()["token"]
    t2 = resp2.json()["token"]
    assert t1 != t2  # new session each time


def test_oauth_callback_rejects_invalid_state(client):
    resp = client.post(
        "/api/auth/oauth/google/callback",
        json={"code": "some-code", "state": "tampered-or-expired-state"},
    )
    assert resp.status_code == 400
    assert "state" in resp.json()["detail"].lower()
