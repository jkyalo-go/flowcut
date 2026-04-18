# Realtime & Jobs Plan

**Goal:** Close audit C3 (Stripe webhook bypass + no idempotency), H3 (websocket zombies), H8 (background job retry storm), H10 (path traversal).

## Changes

1. **Stripe webhook hardening**
   - `construct_webhook_event` refuses to run if `STRIPE_WEBHOOK_SECRET` is empty (hard-fail, not warning).
   - New `stripe_events` table for idempotency (`event.id PRIMARY KEY`).
   - Webhook handler checks event.id → early 200 if already processed.

2. **Websocket robustness** (`routes/ws.py`)
   - `receive_text` with `asyncio.wait_for` timeout; on timeout send ping; on second timeout close.
   - Background task re-validates the session every 60s and boots the client if it expired (covers rotate/logout).
   - Incoming messages validated against a Pydantic envelope; malformed → client receives error, connection stays up.

3. **Celery skeleton**
   - `celery[redis]` dep, `celery_app.py`, `workers/` package.
   - `docker-compose.yml` adds `redis` + `worker` services.
   - Port the renderer-kickoff job to a celery task (`workers.render.kick_render`); the DB-polling scheduler in `bootstrap.py` becomes a thin legacy path.

4. **Path traversal hardening** (`routes/filesystem.py`)
   - Disallow symlinks under STORAGE_DIR; use `os.path.commonpath` against the resolved workspace root, not `.resolve().is_relative_to()`.

5. **Signed URL TTL**: default reduced from 3600s to 600s.

## Migrations

- `add_stripe_events` — `stripe_events(event_id PK, event_type, received_at, processed_at)`.

## Tests

- `test_stripe_webhook_idempotency.py` — same event.id twice → processed once.
- `test_ws_heartbeat.py` — `receive_text` timeout triggers ping/close path.
- `test_filesystem_traversal.py` — symlink escape blocked.
