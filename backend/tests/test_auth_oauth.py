from datetime import timedelta
from unittest.mock import AsyncMock, patch


def _seed_oauth_state(db, state: str, verifier: str = "test-verifier") -> None:
    from common.time import utc_now
    from domain.identity import OAuthState
    db.add(OAuthState(
        state=state,
        code_verifier=verifier,
        provider="google",
        expires_at=utc_now() + timedelta(minutes=10),
    ))
    db.commit()


def test_oauth_start_returns_redirect_url(client):
    resp = client.get("/api/auth/oauth/google/start")
    assert resp.status_code == 200
    body = resp.json()
    assert "redirect_url" in body
    assert "accounts.google.com" in body["redirect_url"]
    assert "state" in body


def test_oauth_callback_creates_user_and_session(client, db):

    from config import SECRET_KEY
    from services.oauth import generate_state_token
    valid_state = generate_state_token(SECRET_KEY)
    _seed_oauth_state(db, valid_state)
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
    assert "workspace" in body
    assert body["workspace"]["plan_tier"] == "starter"
    assert body["user"]["email"] == "creator@gmail.com"


def test_oauth_callback_reuses_existing_user(client, db, workspace_a):
    ws_id, token = workspace_a
    fake_user_info = {
        "sub": "google-uid-999",
        "email": "ws-a@test.local",  # matches seeded user email
        "name": "Workspace A",
        "picture": None,
    }

    from config import SECRET_KEY
    from services.oauth import generate_state_token
    state1 = generate_state_token(SECRET_KEY, workspace_id="ws-1")
    state2 = generate_state_token(SECRET_KEY, workspace_id="ws-2")
    _seed_oauth_state(db, state1, "v1")
    _seed_oauth_state(db, state2, "v2")
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


def test_token_roundtrip_encryption():
    from services.token_crypto import decrypt_token, encrypt_token
    key = b"0" * 32  # 32-byte test key
    plaintext = "ya29.access_token_here"
    ciphertext = encrypt_token(plaintext, key)
    assert ciphertext != plaintext.encode()
    assert decrypt_token(ciphertext, key) == plaintext


def test_token_refresh_skips_non_expiring(db, workspace_a):
    from datetime import timedelta

    from common.time import utc_now
    from domain.platforms import PlatformAuth
    from services.token_crypto import encrypt_token
    ws_id, _ = workspace_a
    # Token expires in 1 hour — should NOT be refreshed (window is 5 minutes)
    pa = PlatformAuth(
        workspace_id=ws_id, platform="youtube",
        access_token_enc=encrypt_token("tok"),
        token_expires_at=utc_now() + timedelta(hours=1),
        status="active",
    )
    db.add(pa)
    db.commit()
    from services.token_refresh import get_tokens_needing_refresh
    tokens = get_tokens_needing_refresh(db, refresh_window_minutes=5)
    assert all(str(t.id) != str(pa.id) for t in tokens)
