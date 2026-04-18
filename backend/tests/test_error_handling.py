"""Unhandled exceptions get scrubbed — no stack traces in response body.

In development, type+message is acceptable. In production (APP_ENV=production),
the client sees only "internal_server_error" + request_id.
"""

from fastapi import APIRouter


def _register_boom_route():
    """Attach a route that raises an unhandled exception."""
    from main import app

    router = APIRouter()

    @router.get("/__test_boom__")
    def boom():
        raise RuntimeError("SECRET_INTERNAL_PATH_/etc/passwd_LEAK_ATTEMPT")

    app.include_router(router)


def test_production_error_response_is_scrubbed(monkeypatch, client):
    _register_boom_route()
    # Switch APP_ENV to production for this test
    import middleware.errors as errors_mod
    monkeypatch.setattr(errors_mod, "_is_production", lambda: True)

    resp = client.get("/__test_boom__")
    assert resp.status_code == 500
    body = resp.json()
    assert body["detail"] == "internal_server_error"
    assert "SECRET_INTERNAL_PATH" not in str(body)
    assert "RuntimeError" not in str(body)
    # Request correlation id should be included for debugging
    assert "request_id" in body


def test_development_error_includes_type(monkeypatch, client):
    _register_boom_route()
    import middleware.errors as errors_mod
    monkeypatch.setattr(errors_mod, "_is_production", lambda: False)

    resp = client.get("/__test_boom__")
    assert resp.status_code == 500
    body = resp.json()
    assert "RuntimeError" in body["detail"]
    # Even in dev the path/secret content is in the detail (we trust developers),
    # but a traceback is NOT (only type: message).
    assert "\n" not in body["detail"]
