"""Websocket with heartbeat, session re-validation, and schema-validated messages."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from common.time import ensure_utc, utc_now
from config import SESSION_COOKIE_NAME
from database import SessionLocal
from domain.identity import AuthSession
from domain.projects import Project

logger = logging.getLogger(__name__)
router = APIRouter()

_connections: dict[str, set[WebSocket]] = {}

# Heartbeat / auth-refresh timings
RECV_TIMEOUT_S = 25.0  # any client activity expected within this window
PING_TIMEOUT_S = 10.0  # grace after server ping before we disconnect
AUTH_REVALIDATE_S = 60.0  # re-check session validity every minute


class ClientMessage(BaseModel):
    """Schema for inbound websocket messages. Unknown shapes are rejected."""

    type: str
    data: dict | None = None


def _validate_session(token: str, project_id: str) -> bool:
    db: Session = SessionLocal()
    try:
        session = db.query(AuthSession).filter(AuthSession.token == token).first()
        if not session:
            return False
        if session.expires_at and ensure_utc(session.expires_at) < utc_now():
            return False
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project or project.workspace_id != session.workspace_id:
            return False
        return True
    finally:
        db.close()


@router.websocket("/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    token = websocket.cookies.get(SESSION_COOKIE_NAME) or websocket.query_params.get("token")
    if not token or not _validate_session(token, project_id):
        await websocket.close(code=4401)
        return

    await websocket.accept()
    _connections.setdefault(project_id, set()).add(websocket)

    async def reauth_loop():
        while True:
            await asyncio.sleep(AUTH_REVALIDATE_S)
            if not _validate_session(token, project_id):
                logger.info("ws session expired for project=%s; closing", project_id)
                try:
                    await websocket.close(code=4401)
                except Exception:
                    pass
                return

    reauth_task = asyncio.create_task(reauth_loop())

    try:
        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=RECV_TIMEOUT_S)
            except TimeoutError:
                # No client activity — probe with a ping. If the client
                # doesn't respond within PING_TIMEOUT_S, assume dead.
                try:
                    await websocket.send_json({"type": "ping"})
                    await asyncio.wait_for(websocket.receive_text(), timeout=PING_TIMEOUT_S)
                except (TimeoutError, Exception):
                    logger.debug("ws heartbeat timeout for project=%s; closing", project_id)
                    break
                continue

            # Malformed messages get an error response but don't kill the connection.
            try:
                _ = ClientMessage.model_validate_json(raw)
            except (ValidationError, ValueError):
                try:
                    await websocket.send_json({"type": "error", "detail": "invalid_message_envelope"})
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("ws unexpected error on project=%s: %s", project_id, exc)
    finally:
        reauth_task.cancel()
        _connections.get(project_id, set()).discard(websocket)
        try:
            await reauth_task
        except (asyncio.CancelledError, Exception):
            pass


async def broadcast(project_id: str, event: str, data: dict):
    message = {"event": event, "data": data}
    dead = []
    for ws in _connections.get(project_id, set()):
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _connections.get(project_id, set()).discard(ws)
