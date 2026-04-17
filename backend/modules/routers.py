from fastapi import FastAPI

from .automation import AUTOMATION_MODULES
from .core import CORE_MODULES
from .integrations import INTEGRATION_MODULES
from .media import MEDIA_MODULES

ALL_MODULES = [
    ("core", CORE_MODULES),
    ("media", MEDIA_MODULES),
    ("automation", AUTOMATION_MODULES),
    ("integrations", INTEGRATION_MODULES),
]


def register_routers(app: FastAPI) -> None:
    for _group_name, modules in ALL_MODULES:
        for module in modules:
            app.include_router(module.router, prefix=module.prefix, tags=module.tags)
