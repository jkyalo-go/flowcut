"""CSRF double-submit cookie behavior.

CSRF check fires only when:
- request uses state-changing method (POST/PUT/PATCH/DELETE)
- request authenticates via cookie (not X-Flowcut-Token or Bearer)
- path is not exempt (auth, webhook, health, websocket)
"""


def test_csrf_exempt_health_get(client):
    r = client.get("/healthz")
    assert r.status_code == 200


def test_csrf_required_for_cookie_auth_post(client):
    # Set only the session cookie (no CSRF token cookie, no CSRF header)
    client.cookies.set("flowcut_session", "dummy-token")
    r = client.post("/api/auth/logout", json={})
    assert r.status_code == 403
    assert "CSRF" in r.json()["detail"]


def test_csrf_passes_when_cookie_and_header_match(client):
    client.cookies.set("flowcut_session", "dummy-token")
    client.cookies.set("flowcut_csrf", "abc123")
    # Even with matching CSRF, /api/auth/logout will 401 on the bad session
    # token — but it will have PASSED the CSRF check.
    r = client.post("/api/auth/logout", headers={"X-CSRF-Token": "abc123"})
    assert r.status_code != 403


def test_csrf_skipped_with_header_auth(client, workspace_a):
    _, token = workspace_a
    # Header-auth POSTs skip CSRF entirely.
    r = client.post(
        "/api/auth/logout",
        headers={"X-Flowcut-Token": token},
    )
    assert r.status_code != 403


def test_csrf_cookie_minted_on_first_response(client):
    # Any unauthenticated GET should result in a flowcut_csrf cookie being set.
    r = client.get("/healthz")
    # Look for the cookie either directly on response or via the client jar
    cookies = r.cookies
    assert "flowcut_csrf" in cookies or client.cookies.get("flowcut_csrf") is not None
