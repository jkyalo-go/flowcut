try:
    from ..routes import (
        assets,
        captions,
        clips,
        filesystem,
        music,
        projects,
        remixes,
        render,
        sfx,
        subscribes,
        timeline,
        timestamps,
        titles,
        trackers,
        uploads,
    )
except ImportError:
    from routes import (
        assets,
        captions,
        clips,
        filesystem,
        music,
        projects,
        remixes,
        render,
        sfx,
        subscribes,
        timeline,
        timestamps,
        titles,
        trackers,
        uploads,
    )

from .types import RouterModule

MEDIA_MODULES = [
    RouterModule(prefix="/api/projects", tags=["projects"], router=projects.router),
    RouterModule(prefix="/api/clips", tags=["clips"], router=clips.router),
    RouterModule(prefix="/api/timeline", tags=["timeline"], router=timeline.router),
    RouterModule(prefix="/api/render", tags=["render"], router=render.router),
    RouterModule(prefix="/api/fs", tags=["filesystem"], router=filesystem.router),
    RouterModule(prefix="/api/uploads", tags=["uploads"], router=uploads.router),
    RouterModule(prefix="/api/assets", tags=["assets"], router=assets.router),
    RouterModule(prefix="/api/music", tags=["music"], router=music.router),
    RouterModule(prefix="/api/titles", tags=["titles"], router=titles.router),
    RouterModule(prefix="/api/captions", tags=["captions"], router=captions.router),
    RouterModule(prefix="/api/timestamps", tags=["timestamps"], router=timestamps.router),
    RouterModule(prefix="/api/sfx", tags=["sfx"], router=sfx.router),
    RouterModule(prefix="/api/trackers", tags=["trackers"], router=trackers.router),
    RouterModule(prefix="/api/subscribes", tags=["subscribes"], router=subscribes.router),
    RouterModule(prefix="/api/remixes", tags=["remixes"], router=remixes.router),
]
