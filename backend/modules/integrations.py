try:
    from ..routes import ai, platforms
except ImportError:
    from routes import ai, platforms

from .types import RouterModule

INTEGRATION_MODULES = [
    RouterModule(prefix="/api/ai", tags=["ai"], router=ai.router),
    RouterModule(prefix="/api/platforms", tags=["platforms"], router=platforms.router),
]
