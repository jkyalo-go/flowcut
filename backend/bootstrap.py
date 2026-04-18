import asyncio
import logging
from contextlib import asynccontextmanager
from sqlalchemy import inspect

try:
    from .database import Base
    from .database import SessionLocal
    from .config import ASSETS_DIR, DATA_DIR, PROCESSED_DIR, REMIX_DIR, REQUIRE_DB_MIGRATIONS, STORAGE_DIR, UPLOAD_TMP_DIR
    from . import domain  # noqa: F401
    from .services.background_jobs import ensure_due_publish_jobs, process_available_jobs
    from .database import engine
except ImportError:
    from database import Base
    from database import SessionLocal
    from config import ASSETS_DIR, DATA_DIR, PROCESSED_DIR, REMIX_DIR, REQUIRE_DB_MIGRATIONS, STORAGE_DIR, UPLOAD_TMP_DIR
    import domain  # noqa: F401
    from services.background_jobs import ensure_due_publish_jobs, process_available_jobs
    from database import engine

logging.basicConfig(level=logging.INFO)


def _validate_database_schema() -> None:
    if not REQUIRE_DB_MIGRATIONS:
        return
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    expected = set(Base.metadata.tables.keys())
    missing = sorted(expected - existing)
    if missing:
        raise RuntimeError(
            "Database schema is not initialized. Run Alembic migrations before starting the application. "
            f"Missing tables: {', '.join(missing)}"
        )


async def _performance_feedback_loop():
    while True:
        await asyncio.sleep(3600)  # run every hour
        try:
            from services.sie.performance import run_performance_feedback_sweep
            await asyncio.to_thread(run_performance_feedback_sweep)
        except Exception as e:
            logging.warning("Performance feedback loop error: %s", e)


async def _token_refresh_loop():
    while True:
        await asyncio.sleep(300)  # every 5 minutes
        def _run_token_refresh():
            import os
            import asyncio as _asyncio
            db = SessionLocal()
            try:
                from services.token_refresh import get_tokens_needing_refresh, refresh_token_sync
                tokens = get_tokens_needing_refresh(db)
                for pa in tokens:
                    try:
                        refresh_token_sync(
                            pa, db,
                            client_id=os.getenv(f"{pa.platform.upper()}_CLIENT_ID", ""),
                            client_secret=os.getenv(f"{pa.platform.upper()}_CLIENT_SECRET", ""),
                        )
                    except Exception as e:
                        logging.warning("Token refresh failed for %s: %s", pa.platform, e)
            finally:
                db.close()
        try:
            await asyncio.to_thread(_run_token_refresh)
        except Exception as e:
            logging.warning("Token refresh loop error: %s", e)


async def _platform_scheduler():
    while True:
        def _run_cycle():
            db = SessionLocal()
            try:
                ensure_due_publish_jobs(db, None)
                process_available_jobs(db, limit=25)
            finally:
                db.close()

        try:
            await asyncio.to_thread(_run_cycle)
        except Exception as exc:
            logging.warning("Platform scheduler cycle failed: %s", exc)
        await asyncio.sleep(15)


@asynccontextmanager
async def lifespan(_app):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    REMIX_DIR.mkdir(parents=True, exist_ok=True)
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_TMP_DIR.mkdir(parents=True, exist_ok=True)
    _validate_database_schema()
    scheduler_task = asyncio.create_task(_platform_scheduler())
    perf_task = asyncio.create_task(_performance_feedback_loop())
    refresh_task = asyncio.create_task(_token_refresh_loop())
    yield
    scheduler_task.cancel()
    perf_task.cancel()
    refresh_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass
    try:
        await perf_task
    except asyncio.CancelledError:
        pass
    try:
        await refresh_task
    except asyncio.CancelledError:
        pass
