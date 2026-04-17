try:
    from ..routes import ai, calendar, platforms
except ImportError:
    from routes import ai, calendar, platforms

from .types import RouterModule

INTEGRATION_MODULES = [
    RouterModule(prefix="/api/ai", tags=["ai"], router=ai.router),
    RouterModule(prefix="/api/platforms", tags=["platforms"], router=platforms.router),
    RouterModule(prefix="/api", tags=["calendar"], router=calendar.router),
]
