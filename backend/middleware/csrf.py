"""Double-submit cookie CSRF protection.

For authenticated, state-changing requests (POST/PUT/PATCH/DELETE), the
client must send `X-CSRF-Token` matching the `flowcut_csrf` cookie. The
cookie is set on session creation and on every response that doesn't
already have one.

Exempt paths: public auth endpoints (login, register, oauth callback),
Stripe webhook (has its own HMAC), websocket upgrade, health endpoints.
"""

from __future__ import annotations

import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

CSRF_COOKIE = "flowcut_csrf"
CSRF_HEADER = "X-CSRF-Token"

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# Paths that must bypass CSRF checks.
EXEMPT_PREFIXES: tuple[str, ...] = (
    "/healthz",
    "/readyz",
    "/ws",
    "/static",
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/dev-login",
    "/api/auth/oauth/google/callback",
    "/billing/webhook",   # Stripe webhook is HMAC-authenticated
    "/billing/webhooks",
)


def _is_exempt(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") or path.startswith(p + "?") for p in EXEMPT_PREFIXES)


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        method = request.method.upper()
        path = request.url.path

        # Only check CSRF when the request authenticates via cookie. Requests
        # authenticating with X-Flowcut-Token or Authorization: Bearer cannot
        # be cross-site forgeries (the attacker origin cannot set custom
        # headers), so they skip the check.
        uses_header_auth = bool(
            request.headers.get("X-Flowcut-Token")
            or (request.headers.get("Authorization") or "").lower().startswith("bearer ")
        )
        needs_check = (
            method not in SAFE_METHODS
            and not _is_exempt(path)
            and not uses_header_auth
        )

        if needs_check:
            cookie_value = request.cookies.get(CSRF_COOKIE)
            header_value = request.headers.get(CSRF_HEADER)
            if not cookie_value or not header_value or not secrets.compare_digest(cookie_value, header_value):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF token missing or invalid"},
                )

        response = await call_next(request)

        # Mint a CSRF cookie if one is not present yet — lets the SPA read it
        # (non-httpOnly) and echo it on mutating requests.
        if not request.cookies.get(CSRF_COOKIE):
            response.set_cookie(
                CSRF_COOKIE,
                secrets.token_urlsafe(32),
                httponly=False,
                samesite="strict",
                path="/",
                secure=False,  # upgrade to True in prod via reverse proxy
            )
        return response
