try:
    from ..routes import auth, billing, enterprise, invitations, overview, settings, style_profiles, workspaces, ws
except ImportError:
    from routes import auth, billing, enterprise, invitations, overview, settings, style_profiles, workspaces, ws

from .types import RouterModule

CORE_MODULES = [
    RouterModule(prefix="/api/auth", tags=["auth"], router=auth.router),
    RouterModule(prefix="/api/workspaces", tags=["workspaces"], router=workspaces.router),
    RouterModule(prefix="/api/overview", tags=["overview"], router=overview.router),
    RouterModule(prefix="/api/enterprise", tags=["enterprise"], router=enterprise.router),
    RouterModule(prefix="/api/settings", tags=["settings"], router=settings.router),
    RouterModule(prefix="/ws", tags=["websocket"], router=ws.router),
    RouterModule(prefix="/api", tags=["style-profiles"], router=style_profiles.router),
    RouterModule(prefix="", tags=["billing"], router=billing.router),
    RouterModule(prefix="", tags=["invitations"], router=invitations.router),
]
