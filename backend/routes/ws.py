import os

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from database import SessionLocal
from domain.identity import AuthSession
from domain.projects import Project

router = APIRouter()

_connections: dict[str, set[WebSocket]] = {}
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "flowcut_session")


@router.websocket("/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    token = websocket.cookies.get(SESSION_COOKIE_NAME) or websocket.query_params.get("token")
    db: Session = SessionLocal()
    try:
        session = db.query(AuthSession).filter(AuthSession.token == token).first()
        project = db.query(Project).filter(Project.id == project_id).first()
        if not token or not session or not project or project.workspace_id != session.workspace_id:
            await websocket.close(code=4401)
            return
    finally:
        db.close()
    await websocket.accept()
    _connections.setdefault(project_id, set()).add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _connections[project_id].discard(websocket)


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
