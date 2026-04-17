try:
    from ..routes import auth, enterprise, settings, ws, workspaces
except ImportError:
    from routes import auth, enterprise, settings, ws, workspaces

from .types import RouterModule

CORE_MODULES = [
    RouterModule(prefix="/api/auth", tags=["auth"], router=auth.router),
    RouterModule(prefix="/api/workspaces", tags=["workspaces"], router=workspaces.router),
    RouterModule(prefix="/api/enterprise", tags=["enterprise"], router=enterprise.router),
    RouterModule(prefix="/api/settings", tags=["settings"], router=settings.router),
    RouterModule(prefix="/ws", tags=["websocket"], router=ws.router),
]
