"""Celery task definitions.

Skeleton task surface. Existing long-running work (render, publish, transcription)
still flows through services/background_jobs.py; migration to celery is ongoing.
New job types should be added here directly.
"""

from __future__ import annotations

import asyncio
import logging

from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="flowcut.render.kick",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def kick_render(self, project_id: str, output_path: str) -> dict:
    """Kick off a render for `project_id`.

    Wraps services.renderer.render_timeline (async) with retry/backoff and
    durable celery result storage.
    """
    logger.info("kick_render project_id=%s attempt=%s", project_id, self.request.retries + 1)
    from services.renderer import render_timeline

    result = asyncio.run(render_timeline(project_id, output_path))
    return {"project_id": project_id, "status": "ok", "output": result}


@celery_app.task(
    name="flowcut.noop",
    bind=True,
)
def noop(self, payload: dict | None = None) -> dict:
    """Sanity task — used by tests and deploy health-checks to verify broker/worker."""
    return {"ok": True, "payload": payload or {}}
