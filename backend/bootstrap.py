import asyncio
import logging
from contextlib import asynccontextmanager
from uuid import uuid4

try:
    from .database import Base, engine
    from .database import SessionLocal
    from .config import ASSETS_DIR, DATA_DIR, PROCESSED_DIR, REMIX_DIR, STORAGE_DIR, UPLOAD_TMP_DIR
    from . import domain  # noqa: F401
    from .services.background_jobs import ensure_due_publish_jobs, process_available_jobs
    from .services.watcher import set_queue
    from .workers.queue import process_worker, processing_queue
except ImportError:
    from database import Base, engine
    from database import SessionLocal
    from config import ASSETS_DIR, DATA_DIR, PROCESSED_DIR, REMIX_DIR, STORAGE_DIR, UPLOAD_TMP_DIR
    import domain  # noqa: F401
    from services.background_jobs import ensure_due_publish_jobs, process_available_jobs
    from services.watcher import set_queue
    from workers.queue import process_worker, processing_queue

logging.basicConfig(level=logging.INFO)


def _new_uuid() -> str:
    return str(uuid4())


def _ensure_columns(conn, table: str, specs: list[tuple[str, str, str | None]]):
    import sqlalchemy

    table_exists = conn.execute(
        sqlalchemy.text("SELECT name FROM sqlite_master WHERE type='table' AND name = :table"),
        {"table": table},
    ).fetchone()
    if table_exists is None:
        return
    existing = {row[1] for row in conn.execute(sqlalchemy.text(f"PRAGMA table_info({table})"))}
    for col, col_type, default in specs:
        if col not in existing:
            dflt = f" DEFAULT {default}" if default is not None else ""
            conn.execute(sqlalchemy.text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}{dflt}"))


def _bootstrap_database():
    with engine.connect() as conn:
        import sqlalchemy

        if engine.dialect.name == "sqlite":
            workspace_info = conn.execute(sqlalchemy.text("PRAGMA table_info(workspaces)")).fetchall()
            if workspace_info:
                id_row = next((row for row in workspace_info if row[1] == "id"), None)
                if id_row and str(id_row[2]).upper().startswith("INTEGER"):
                    logging.warning("Legacy integer-ID SQLite schema detected. Resetting dev database for UUID IDs.")
                    Base.metadata.drop_all(bind=engine)
                    Base.metadata.create_all(bind=engine)

        _ensure_columns(conn, "projects", [
            ("workspace_id", "VARCHAR(36)", None),
            ("watch_directory", "VARCHAR", None),
            ("intake_mode", "VARCHAR", "'watch'"),
            ("source_type", "VARCHAR", None),
            ("storage_prefix", "VARCHAR", None),
            ("autonomy_mode", "VARCHAR", None),
            ("autonomy_policy", "VARCHAR", None),
            ("selected_title", "VARCHAR", None),
            ("video_description", "VARCHAR", None),
            ("video_tags", "VARCHAR", None),
            ("video_category", "VARCHAR", "'22'"),
            ("video_visibility", "VARCHAR", "'private'"),
            ("selected_thumbnail_idx", "INTEGER", None),
            ("desc_system_prompt", "VARCHAR", None),
            ("thumbnail_urls", "VARCHAR", None),
            ("locked_thumbnail_indices", "VARCHAR", None),
            ("thumbnail_text", "VARCHAR", None),
            ("render_path", "VARCHAR", None),
        ])
        _ensure_columns(conn, "clips", [
            ("workspace_id", "VARCHAR(36)", None),
            ("recorded_at", "DATETIME", None),
            ("review_status", "VARCHAR", "'pending_review'"),
            ("confidence_score", "FLOAT", None),
        ])
        for table in ["timeline_items", "assets", "music_items", "title_items", "caption_items", "timestamp_items", "tracker_items", "subscribe_items"]:
            _ensure_columns(conn, table, [("workspace_id", "VARCHAR(36)", None)])
        _ensure_columns(conn, "app_settings", [("workspace_id", "VARCHAR(36)", None)])
        _ensure_columns(conn, "users", [
            ("user_type", "VARCHAR", "'user'"),
            ("oauth_provider", "VARCHAR", None),
            ("oauth_id", "VARCHAR", None),
            ("avatar_url", "VARCHAR", None),
        ])
        _ensure_columns(conn, "auth_sessions", [("expires_at", "DATETIME", None)])
        _ensure_columns(conn, "workspaces", [("lifecycle_status", "VARCHAR", "'trial'")])
        _ensure_columns(conn, "calendar_slots", [
            ("render_variant", "VARCHAR", None),
            ("correlation_id", "VARCHAR", None),
        ])
        _ensure_columns(conn, "style_profiles", [
            ("genre", "VARCHAR", None),
            ("style_doc", "VARCHAR", None),
            ("confidence_scores", "VARCHAR", "'{}'"),
            ("dimension_locks", "VARCHAR", "'{}'"),
            ("version", "INTEGER", "1"),
            ("mem0_user_id", "VARCHAR", None),
        ])
        conn.commit()
        _seed_defaults(conn)


def _seed_defaults(conn):
    import sqlalchemy

    workspace = conn.execute(sqlalchemy.text("SELECT id FROM workspaces WHERE slug = 'default-workspace'")).fetchone()
    if workspace is None:
        workspace_id = _new_uuid()
        conn.execute(sqlalchemy.text(
            "INSERT INTO workspaces (id, name, slug, plan_tier, lifecycle_status, storage_quota_mb, raw_retention_days, autonomy_mode, autonomy_confidence_threshold) "
            "VALUES (:id, 'Default Workspace', 'default-workspace', 'starter', 'trial', 10240, 30, 'supervised', 0.8)"
        ), {"id": workspace_id})
    user = conn.execute(sqlalchemy.text("SELECT id FROM users WHERE email = 'demo@flowcut.local'")).fetchone()
    if user is None:
        user_id = _new_uuid()
        conn.execute(sqlalchemy.text(
            "INSERT INTO users (id, email, name, user_type) VALUES (:id, 'demo@flowcut.local', 'Flowcut Demo', 'admin')"
        ), {"id": user_id})
    else:
        conn.execute(sqlalchemy.text("UPDATE users SET user_type = 'admin' WHERE email = 'demo@flowcut.local'"))

    workspace_id = conn.execute(sqlalchemy.text("SELECT id FROM workspaces WHERE slug = 'default-workspace'")).fetchone()[0]
    user_id = conn.execute(sqlalchemy.text("SELECT id FROM users WHERE email = 'demo@flowcut.local'")).fetchone()[0]

    membership = conn.execute(sqlalchemy.text(
        "SELECT id FROM memberships WHERE workspace_id = :workspace_id AND user_id = :user_id"
    ), {"workspace_id": workspace_id, "user_id": user_id}).fetchone()
    if membership is None:
        conn.execute(sqlalchemy.text(
            "INSERT INTO memberships (id, workspace_id, user_id, role) VALUES (:id, :workspace_id, :user_id, 'owner')"
        ), {"id": _new_uuid(), "workspace_id": workspace_id, "user_id": user_id})

    provider_count = conn.execute(sqlalchemy.text("SELECT COUNT(*) FROM ai_provider_configs")).fetchone()[0]
    if provider_count == 0:
        seed_rows = [
            ("anthropic", "claude-sonnet-4-20250514", "Claude Sonnet 4", '["titles","description","tags","planning"]', '{"text": true}', 1, None, None, '{}'),
            ("vertex", "gemini-2.5-flash", "Gemini 2.5 Flash", '["analysis","thumbnail","captions"]', '{"multimodal": true}', 1, None, None, '{}'),
            ("vertex", "gemini-2.5-pro", "Gemini 2.5 Pro", '["analysis","planning"]', '{"multimodal": true}', 1, None, None, '{}'),
            ("vertex", "veo-3.1-generate-001", "Veo 3.1 Generate", '["video_generation"]', '{"image_to_video": true}', 1, None, None, '{}'),
            ("deepgram", "nova-3", "Deepgram Nova-3", '["transcription"]', '{"speech_to_text": true}', 1, None, None, '{}'),
            ("dashscope", "wan2.7-videoedit", "Wan 2.7 Video Edit", '["video_edit"]', '{"video_to_video": true}', 1, None, "https://dashscope-intl.aliyuncs.com", '{}'),
            ("dashscope", "wan2.7-i2v-turbo", "Wan 2.7 Image to Video", '["video_generation"]', '{"image_to_video": true}', 1, None, "https://dashscope-intl.aliyuncs.com", '{}'),
            ("dashscope", "wan2.7-t2v-turbo", "Wan 2.7 Text to Video", '["video_generation"]', '{"text_to_video": true}', 1, None, "https://dashscope-intl.aliyuncs.com", '{}'),
        ]
        for provider, model_key, display_name, task_types, capabilities_json, enabled, api_key, base_url, config_json in seed_rows:
            conn.execute(sqlalchemy.text(
                "INSERT INTO ai_provider_configs (id, provider, model_key, display_name, task_types, capabilities_json, enabled, api_key, base_url, config_json) "
                "VALUES (:id, :provider, :model_key, :display_name, :task_types, :capabilities_json, :enabled, :api_key, :base_url, :config_json)"
            ), {
                "id": _new_uuid(),
                "provider": provider,
                "model_key": model_key,
                "display_name": display_name,
                "task_types": task_types,
                "capabilities_json": capabilities_json,
                "enabled": enabled,
                "api_key": api_key,
                "base_url": base_url,
                "config_json": config_json,
            })

    plan_rows = [
        (
            "starter",
            "Starter",
            0.0,
            '{"storage_quota_mb":10240,"ai_spend_cap_usd":25,"render_minutes_quota":300,"connected_platforms_quota":2,"team_seats_quota":1,"retained_footage_days":30,"automation_max_mode":"supervised"}',
            '{"calendar":"basic","support":"community"}',
        ),
        (
            "creator",
            "Creator",
            29.0,
            '{"storage_quota_mb":51200,"ai_spend_cap_usd":150,"render_minutes_quota":1500,"connected_platforms_quota":5,"team_seats_quota":3,"retained_footage_days":90,"automation_max_mode":"review_then_publish"}',
            '{"calendar":"full","support":"email"}',
        ),
        (
            "enterprise",
            "Enterprise",
            299.0,
            '{"storage_quota_mb":512000,"ai_spend_cap_usd":2500,"render_minutes_quota":20000,"connected_platforms_quota":5,"team_seats_quota":50,"retained_footage_days":365,"automation_max_mode":"auto_publish"}',
            '{"calendar":"ai_strategy","support":"priority","agency":"true"}',
        ),
    ]
    for key, name, monthly_price_usd, quotas_json, features_json in plan_rows:
        existing = conn.execute(sqlalchemy.text("SELECT id FROM subscription_plans WHERE key = :key"), {"key": key}).fetchone()
        if existing is None:
            conn.execute(sqlalchemy.text(
                "INSERT INTO subscription_plans (id, key, name, monthly_price_usd, quotas_json, features_json, is_active) "
                "VALUES (:id, :key, :name, :monthly_price_usd, :quotas_json, :features_json, 1)"
            ), {
                "id": _new_uuid(),
                "key": key,
                "name": name,
                "monthly_price_usd": monthly_price_usd,
                "quotas_json": quotas_json,
                "features_json": features_json,
            })

    starter_plan_id = conn.execute(sqlalchemy.text("SELECT id FROM subscription_plans WHERE key = 'starter'")).fetchone()[0]
    existing_sub = conn.execute(sqlalchemy.text(
        "SELECT id FROM workspace_subscriptions WHERE workspace_id = :workspace_id"
    ), {"workspace_id": workspace_id}).fetchone()
    if existing_sub is None:
        conn.execute(sqlalchemy.text(
            "INSERT INTO workspace_subscriptions (id, workspace_id, plan_id, status, billing_email, current_period_start, current_period_end, metadata_json) "
            "VALUES (:id, :workspace_id, :plan_id, 'trial', 'demo@flowcut.local', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, '{}')"
        ), {"id": _new_uuid(), "workspace_id": workspace_id, "plan_id": starter_plan_id})

    quota = conn.execute(sqlalchemy.text("SELECT id FROM quota_policies WHERE workspace_id = :workspace_id"), {"workspace_id": workspace_id}).fetchone()
    if quota is None:
        conn.execute(sqlalchemy.text(
            "INSERT INTO quota_policies (id, workspace_id, storage_quota_mb, ai_spend_cap_usd, render_minutes_quota, connected_platforms_quota, team_seats_quota, retained_footage_days, automation_max_mode, hard_enforcement) "
            "VALUES (:id, :workspace_id, 10240, 25, 300, 2, 1, 30, 'supervised', 0)"
        ), {"id": _new_uuid(), "workspace_id": workspace_id})

    onboarding = conn.execute(sqlalchemy.text("SELECT id FROM onboarding_states WHERE workspace_id = :workspace_id"), {"workspace_id": workspace_id}).fetchone()
    if onboarding is None:
        conn.execute(sqlalchemy.text(
            "INSERT INTO onboarding_states (id, workspace_id, checklist_json) VALUES (:id, :workspace_id, :checklist_json)"
        ), {
            "id": _new_uuid(),
            "workspace_id": workspace_id,
            "checklist_json": '{"workspace_created":true,"brand_setup":false,"provider_policy_configured":false,"platform_connected":false,"first_upload":false,"style_profile_created":false,"first_publish_ready":false}',
        })
    conn.commit()


async def _performance_feedback_loop():
    while True:
        await asyncio.sleep(3600)  # run every hour
        try:
            from services.sie.performance import run_performance_feedback_sweep
            await asyncio.get_event_loop().run_in_executor(None, run_performance_feedback_sweep)
        except Exception as e:
            logging.warning("Performance feedback loop error: %s", e)


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
    Base.metadata.create_all(bind=engine)
    _bootstrap_database()
    set_queue(processing_queue)
    task = asyncio.create_task(process_worker())
    scheduler_task = asyncio.create_task(_platform_scheduler())
    perf_task = asyncio.create_task(_performance_feedback_loop())
    yield
    task.cancel()
    scheduler_task.cancel()
    perf_task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass
    try:
        await perf_task
    except asyncio.CancelledError:
        pass
