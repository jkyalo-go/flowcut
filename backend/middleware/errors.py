"""Global exception handler that scrubs internal error messages in production.

In development (APP_ENV != production), full tracebacks go to clients for
DX. In production, clients get a generic message and a request_id they can
reference when reporting the bug; the full exception goes to the server log
and Sentry.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

try:
    from ..config import APP_ENV
    from ..middleware.request_context import current_request_id
except ImportError:
    from config import APP_ENV
    from middleware.request_context import current_request_id

logger = logging.getLogger(__name__)


def _is_production() -> bool:
    return APP_ENV == "production"


def _response(status: int, detail: str, request: Request) -> JSONResponse:
    body = {"detail": detail}
    rid = getattr(request.state, "request_id", None) or current_request_id()
    if rid:
        body["request_id"] = rid
    return JSONResponse(status_code=status, content=body)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def _http_exc(request: Request, exc: StarletteHTTPException):
        # Known HTTP errors keep their detail — they're intentional messages.
        return _response(exc.status_code, str(exc.detail), request)

    @app.exception_handler(RequestValidationError)
    async def _validation_exc(request: Request, exc: RequestValidationError):
        # Validation errors are client-fault; returning the field list is safe.
        return JSONResponse(
            status_code=422,
            content={"detail": "validation_error", "errors": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def _catchall(request: Request, exc: Exception):
        rid = current_request_id()
        logger.exception("Unhandled exception on %s %s (request_id=%s)", request.method, request.url.path, rid)
        if _is_production():
            return _response(500, "internal_server_error", request)
        # Dev: surface the type + message for fast iteration, but never the full traceback.
        return _response(500, f"{type(exc).__name__}: {exc}", request)
