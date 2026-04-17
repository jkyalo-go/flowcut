try:
    from ..routes import autonomy, generate
except ImportError:
    from routes import autonomy, generate

from .types import RouterModule

AUTOMATION_MODULES = [
    RouterModule(prefix="/api/projects", tags=["generate"], router=generate.router),
    RouterModule(prefix="/api/autonomy", tags=["autonomy"], router=autonomy.router),
]
