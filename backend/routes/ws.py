from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

_connections: dict[int, set[WebSocket]] = {}


@router.websocket("/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: int):
    await websocket.accept()
    _connections.setdefault(project_id, set()).add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _connections[project_id].discard(websocket)


async def broadcast(project_id: int, event: str, data: dict):
    message = {"event": event, "data": data}
    dead = []
    for ws in _connections.get(project_id, set()):
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _connections.get(project_id, set()).discard(ws)
