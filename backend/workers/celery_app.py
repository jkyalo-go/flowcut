"""Celery application factory.

The broker + result backend default to Redis on localhost. In docker-compose
and bare-VM deploys, set CELERY_BROKER_URL / CELERY_RESULT_BACKEND env vars
to point at the redis service.

Tasks registered here:
- workers.tasks.kick_render (see workers/tasks.py)

This is additive — the existing DB-polling scheduler in bootstrap.py remains
for backward compat during the transition. New job types should go straight
to celery.
"""

from __future__ import annotations

import os

from celery import Celery

BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", BROKER_URL)

celery_app = Celery(
    "flowcut",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
    include=["workers.tasks"],
)

celery_app.conf.update(
    task_default_queue="flowcut.default",
    task_acks_late=True,  # tasks are re-queued if the worker dies mid-execution
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    task_time_limit=600,  # 10min hard limit
    task_soft_time_limit=540,
    result_expires=3600,
    # Retry policy
    task_annotations={
        "*": {
            "max_retries": 3,
            "default_retry_delay": 30,
            "retry_backoff": True,
            "retry_backoff_max": 600,
            "retry_jitter": True,
        }
    },
)
