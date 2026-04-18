# Ops Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the operational baseline this product needs before any further production-hardening work — CI gates, container images, health probes, structured logging with request correlation, Sentry error reporting, and disciplined migration rollback — so every subsequent fix is verifiable and deployable.

**Architecture:** Add GitHub Actions workflows that block merges on typecheck/lint/test failures for both backend and frontend. Introduce a Dockerfile per service plus a docker-compose.yml for reproducible local runs on a bare VM. Wire a request-id middleware that threads a correlation ID through structured logs and Sentry scopes on both FastAPI and Next.js. Backfill a `downgrade()` for the existing monolithic Alembic migration and codify the "every new migration has a downgrade" rule in a repo doc. No existing routes change semantics in this plan — we are adding rails, not refactoring.

**Tech Stack:** FastAPI, Next.js, Alembic, GitHub Actions, Docker, ruff, mypy, pytest, vitest, ESLint, Sentry SDK (Python + Next.js), structlog.

---

## File Structure

**Created:**
- `.github/workflows/backend.yml` — backend CI (ruff, mypy, pytest)
- `.github/workflows/frontend.yml` — frontend CI (tsc, eslint, vitest)
- `backend/pyproject.toml` — ruff + mypy + pytest config (tool-only, not a build)
- `backend/middleware/__init__.py`
- `backend/middleware/request_context.py` — request-id middleware + structlog wiring
- `backend/middleware/sentry.py` — Sentry init (no-op when DSN unset)
- `backend/routes/health.py` — `/healthz` and `/readyz`
- `backend/tests/test_health.py`
- `backend/tests/test_request_context.py`
- `backend/Dockerfile`
- `frontend/Dockerfile`
- `frontend/sentry.client.config.ts`
- `frontend/sentry.server.config.ts`
- `docker-compose.yml` (repo root)
- `docs/ops/DEPLOYMENT.md` — bare-VM deploy runbook
- `docs/ops/MIGRATIONS.md` — alembic discipline doc
- `.dockerignore` (repo root)

**Modified:**
- `backend/main.py` — register health router, request-context middleware, Sentry init
- `backend/requirements.txt` — add `structlog`, `sentry-sdk[fastapi]`
- `backend/alembic/versions/14a7b9398bb7_phase1_8_full_coverage.py` — implement `downgrade()`
- `backend/modules/core.py` — include health router
- `frontend/package.json` — add `typecheck` script, `@sentry/nextjs`
- `frontend/next.config.js` — wrap with Sentry
- `frontend/pages/_app.tsx` — propagate request-id header on fetch

---

## Task 1: Backend tool config (ruff, mypy, pytest)

**Files:**
- Create: `backend/pyproject.toml`

- [ ] **Step 1: Write `backend/pyproject.toml`**

```toml
[tool.ruff]
line-length = 120
target-version = "py311"
extend-exclude = ["alembic/versions", "__pycache__"]

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP", "S", "ASYNC"]
ignore = ["E501", "B008", "S101"]

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["S", "B"]

[tool.mypy]
python_version = "3.11"
strict_optional = true
warn_unused_ignores = true
warn_redundant_casts = true
ignore_missing_imports = true
exclude = ["alembic/versions", "tests/fixtures"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = "-ra --strict-markers"
```

- [ ] **Step 2: Verify ruff passes (or surface existing violations as a baseline)**

Run: `cd backend && pip install ruff mypy && ruff check .`
Expected: either clean, or a finite list of violations — capture the count. Do not fix app code in this task.

- [ ] **Step 3: Commit**

```bash
git add backend/pyproject.toml
git commit -m "chore(backend): add ruff/mypy/pytest tool config"
```

---

## Task 2: Backend CI workflow

**Files:**
- Create: `.github/workflows/backend.yml`

- [ ] **Step 1: Write workflow**

```yaml
name: backend

on:
  pull_request:
    paths: ["backend/**", ".github/workflows/backend.yml"]
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: backend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
          cache-dependency-path: backend/requirements.txt
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install ruff mypy
      - name: Ruff
        run: ruff check .
      - name: Mypy
        run: mypy . || true  # warn-only for now; flip to required after debt pass
      - name: Pytest
        env:
          DATABASE_URL: "sqlite:///./ci.db"
          SECRET_KEY: "ci-test-key-not-for-prod"
          REQUIRE_DB_MIGRATIONS: "false"
        run: pytest -q
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/backend.yml
git commit -m "ci(backend): add ruff + mypy + pytest workflow"
```

Note: `mypy` is `|| true` intentionally for this plan — flipping to required is part of plan #4 (API contracts) after DTOs are typed properly.

---

## Task 3: Frontend CI workflow + typecheck script

**Files:**
- Create: `.github/workflows/frontend.yml`
- Modify: `frontend/package.json`

- [ ] **Step 1: Add typecheck script to `frontend/package.json`**

In the `scripts` block, add:

```json
"typecheck": "tsc --noEmit"
```

So the scripts block becomes:

```json
"scripts": {
  "dev": "next dev",
  "build": "next build",
  "start": "next start",
  "lint": "next lint",
  "typecheck": "tsc --noEmit",
  "test": "vitest",
  "test:run": "vitest run"
}
```

- [ ] **Step 2: Write `.github/workflows/frontend.yml`**

```yaml
name: frontend

on:
  pull_request:
    paths: ["frontend/**", ".github/workflows/frontend.yml"]
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - name: Install dependencies
        run: npm ci
      - name: Typecheck
        run: npm run typecheck
      - name: Lint
        run: npm run lint
      - name: Test
        run: npm run test:run
```

- [ ] **Step 3: Verify typecheck locally**

Run: `cd frontend && npm run typecheck`
Expected: either clean, or a captured list of errors. If errors exist that are not trivial to fix in this task, add `--strict false` is NOT acceptable — instead, add a follow-up task note to plan #4. For this plan, if `tsc --noEmit` fails, commit the script and let CI mark it red so the debt is visible.

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json .github/workflows/frontend.yml
git commit -m "ci(frontend): add tsc + eslint + vitest workflow"
```

---

## Task 4: Health endpoint tests (TDD)

**Files:**
- Create: `backend/tests/test_health.py`

- [ ] **Step 1: Write failing test**

```python
from fastapi.testclient import TestClient


def test_healthz_returns_ok(client: TestClient):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_readyz_returns_ok_when_db_reachable(client: TestClient):
    resp = client.get("/readyz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"] == "ok"
```

Note: `client` fixture already exists in `backend/tests/conftest.py` (confirmed during audit). If the fixture name differs, grep for the existing pattern and match it rather than inventing a new fixture.

- [ ] **Step 2: Run tests, confirm they fail**

Run: `cd backend && pytest tests/test_health.py -v`
Expected: FAIL with 404 for `/healthz` and `/readyz`.

- [ ] **Step 3: Commit failing tests**

```bash
git add backend/tests/test_health.py
git commit -m "test(health): add failing health/ready endpoint tests"
```

---

## Task 5: Implement health router

**Files:**
- Create: `backend/routes/health.py`
- Modify: `backend/modules/core.py` (or wherever `register_routers` is defined — confirm via grep)

- [ ] **Step 1: Write `backend/routes/health.py`**

```python
import os

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

try:
    from ..dependencies import get_db
except ImportError:
    from dependencies import get_db

router = APIRouter(tags=["health"])

APP_VERSION = os.environ.get("APP_VERSION", "dev")


@router.get("/healthz")
def healthz():
    return {"status": "ok", "version": APP_VERSION}


@router.get("/readyz")
def readyz(db: Session = Depends(get_db)):
    checks = {}
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001 — we want any failure to degrade readiness
        checks["database"] = f"error: {type(exc).__name__}"
        return {"status": "degraded", "checks": checks}, 503
    return {"status": "ready", "checks": checks}
```

- [ ] **Step 2: Register router in `backend/modules/core.py`**

Grep to find the existing `register_routers` function:

Run: `grep -n "register_routers" backend/modules/core.py`

Add the health router import at the top and include it in the registration list. Match the existing pattern (likely `app.include_router(health_router, prefix="")`). If the file uses a list-based registration, append `(health.router, "")` to that list.

- [ ] **Step 3: Run tests, confirm they pass**

Run: `cd backend && pytest tests/test_health.py -v`
Expected: PASS — both tests green.

- [ ] **Step 4: Commit**

```bash
git add backend/routes/health.py backend/modules/core.py
git commit -m "feat(health): add /healthz and /readyz endpoints"
```

---

## Task 6: Add structlog + sentry-sdk to backend requirements

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Append dependencies**

Add these two lines to `backend/requirements.txt`:

```
structlog>=24.1.0
sentry-sdk[fastapi]>=2.14.0
```

- [ ] **Step 2: Install and verify**

Run: `cd backend && pip install -r requirements.txt`
Expected: clean install, no resolver conflicts.

- [ ] **Step 3: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore(backend): add structlog and sentry-sdk"
```

---

## Task 7: Request-context middleware tests (TDD)

**Files:**
- Create: `backend/tests/test_request_context.py`

- [ ] **Step 1: Write failing tests**

```python
import uuid

from fastapi.testclient import TestClient


def test_request_id_echoed_when_provided(client: TestClient):
    rid = "test-request-id-123"
    resp = client.get("/healthz", headers={"X-Request-ID": rid})
    assert resp.headers.get("x-request-id") == rid


def test_request_id_generated_when_absent(client: TestClient):
    resp = client.get("/healthz")
    got = resp.headers.get("x-request-id")
    assert got is not None
    # Must be a uuid4 string
    uuid.UUID(got, version=4)
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `cd backend && pytest tests/test_request_context.py -v`
Expected: FAIL — header missing.

- [ ] **Step 3: Commit failing tests**

```bash
git add backend/tests/test_request_context.py
git commit -m "test(middleware): add failing request-id tests"
```

---

## Task 8: Implement request-context middleware + structlog

**Files:**
- Create: `backend/middleware/__init__.py` (empty)
- Create: `backend/middleware/request_context.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Write `backend/middleware/request_context.py`**

```python
import logging
import sys
import uuid
from contextvars import ContextVar

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"

_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


def current_request_id() -> str | None:
    return _request_id_ctx.get()


def configure_logging() -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming if incoming else str(uuid.uuid4())
        token = _request_id_ctx.set(request_id)
        structlog.contextvars.bind_contextvars(request_id=request_id, path=request.url.path)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()
            _request_id_ctx.reset(token)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
```

- [ ] **Step 2: Wire into `backend/main.py`**

Edit `backend/main.py` so it reads:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

try:
    from .bootstrap import lifespan
    from .config import CORS_ORIGINS, PROCESSED_DIR
    from .middleware.request_context import RequestContextMiddleware, configure_logging
    from .modules import register_routers
except ImportError:
    from bootstrap import lifespan
    from config import CORS_ORIGINS, PROCESSED_DIR
    from middleware.request_context import RequestContextMiddleware, configure_logging
    from modules import register_routers


configure_logging()

app = FastAPI(title="Flowcut", lifespan=lifespan)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(PROCESSED_DIR.parent)), name="static")

register_routers(app)
```

Note: CORS is intentionally left wildcard here — tightening is part of plan #2 (secrets/config).

- [ ] **Step 3: Run tests, confirm they pass**

Run: `cd backend && pytest tests/test_request_context.py tests/test_health.py -v`
Expected: PASS — 4 tests.

- [ ] **Step 4: Commit**

```bash
git add backend/middleware/__init__.py backend/middleware/request_context.py backend/main.py
git commit -m "feat(middleware): add request-id middleware and structlog wiring"
```

---

## Task 9: Sentry backend init (no-op when DSN unset)

**Files:**
- Create: `backend/middleware/sentry.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Write `backend/middleware/sentry.py`**

```python
import os

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration


def init_sentry() -> bool:
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        return False
    env = os.environ.get("APP_ENV", "development")
    release = os.environ.get("APP_VERSION", "dev")
    sample_rate = float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1"))
    sentry_sdk.init(
        dsn=dsn,
        environment=env,
        release=release,
        traces_sample_rate=sample_rate,
        integrations=[StarletteIntegration(), FastApiIntegration()],
        send_default_pii=False,
    )
    return True
```

- [ ] **Step 2: Call `init_sentry()` from `backend/main.py`**

Update `backend/main.py` to call Sentry init before the app is created. Edit imports and add the call:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

try:
    from .bootstrap import lifespan
    from .config import CORS_ORIGINS, PROCESSED_DIR
    from .middleware.request_context import RequestContextMiddleware, configure_logging
    from .middleware.sentry import init_sentry
    from .modules import register_routers
except ImportError:
    from bootstrap import lifespan
    from config import CORS_ORIGINS, PROCESSED_DIR
    from middleware.request_context import RequestContextMiddleware, configure_logging
    from middleware.sentry import init_sentry
    from modules import register_routers


configure_logging()
init_sentry()

app = FastAPI(title="Flowcut", lifespan=lifespan)
# ... rest unchanged
```

- [ ] **Step 3: Bind request-id to Sentry scope**

Edit `backend/middleware/request_context.py` — inside `RequestContextMiddleware.dispatch`, after `bind_contextvars`, add:

```python
        try:
            import sentry_sdk
            sentry_sdk.set_tag("request_id", request_id)
        except ImportError:
            pass
```

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_request_context.py tests/test_health.py -v`
Expected: PASS — Sentry init is a no-op without DSN, tests unchanged.

- [ ] **Step 5: Commit**

```bash
git add backend/middleware/sentry.py backend/main.py backend/middleware/request_context.py
git commit -m "feat(observability): initialize sentry with request-id tag"
```

---

## Task 10: Frontend Sentry wire-up

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/sentry.client.config.ts`
- Create: `frontend/sentry.server.config.ts`
- Create: `frontend/sentry.edge.config.ts`
- Modify: `frontend/next.config.js`

- [ ] **Step 1: Install `@sentry/nextjs`**

Run: `cd frontend && npm install @sentry/nextjs`
Expected: clean install; `package.json` gains the dep.

- [ ] **Step 2: Create `frontend/sentry.client.config.ts`**

```ts
import * as Sentry from "@sentry/nextjs";

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;

if (dsn) {
  Sentry.init({
    dsn,
    environment: process.env.NEXT_PUBLIC_APP_ENV ?? "development",
    release: process.env.NEXT_PUBLIC_APP_VERSION ?? "dev",
    tracesSampleRate: Number(process.env.NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE ?? "0.1"),
    sendDefaultPii: false,
  });
}
```

- [ ] **Step 3: Create `frontend/sentry.server.config.ts` and `frontend/sentry.edge.config.ts`**

`sentry.server.config.ts`:

```ts
import * as Sentry from "@sentry/nextjs";

const dsn = process.env.SENTRY_DSN;

if (dsn) {
  Sentry.init({
    dsn,
    environment: process.env.APP_ENV ?? "development",
    release: process.env.APP_VERSION ?? "dev",
    tracesSampleRate: Number(process.env.SENTRY_TRACES_SAMPLE_RATE ?? "0.1"),
    sendDefaultPii: false,
  });
}
```

`sentry.edge.config.ts`:

```ts
import * as Sentry from "@sentry/nextjs";

const dsn = process.env.SENTRY_DSN;

if (dsn) {
  Sentry.init({
    dsn,
    environment: process.env.APP_ENV ?? "development",
    release: process.env.APP_VERSION ?? "dev",
    tracesSampleRate: Number(process.env.SENTRY_TRACES_SAMPLE_RATE ?? "0.1"),
    sendDefaultPii: false,
  });
}
```

- [ ] **Step 4: Wrap `next.config.js` with Sentry**

Read the current `next.config.js`, then modify to wrap the exported config:

```js
const { withSentryConfig } = require("@sentry/nextjs");

const nextConfig = {
  // ... keep existing config exactly as-is ...
};

module.exports = withSentryConfig(nextConfig, {
  silent: true,
  disableLogger: true,
  // Sentry will upload source maps only when SENTRY_AUTH_TOKEN is present
});
```

- [ ] **Step 5: Propagate request-id header on fetch in `frontend/src/lib/api.ts`**

Grep current fetch call: `grep -n "fetch(" frontend/src/lib/api.ts`

Add an `X-Request-ID` header generation per-request. At the top of `api.ts` add:

```ts
function newRequestId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `rid-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
```

In the fetch wrapper (around line 60-84 per audit), add header:

```ts
const headers = {
  "Content-Type": "application/json",
  "X-Request-ID": newRequestId(),
  ...(init?.headers ?? {}),
};
```

- [ ] **Step 6: Verify build**

Run: `cd frontend && npm run build`
Expected: build succeeds. Sentry emits a warning if auth token absent; that's fine.

- [ ] **Step 7: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/sentry.*.config.ts frontend/next.config.js frontend/src/lib/api.ts
git commit -m "feat(frontend): wire sentry and propagate request-id header"
```

---

## Task 11: Backfill `downgrade()` on existing migration

**Files:**
- Modify: `backend/alembic/versions/14a7b9398bb7_phase1_8_full_coverage.py`

- [ ] **Step 1: Read the upgrade block**

Run: `wc -l backend/alembic/versions/14a7b9398bb7_phase1_8_full_coverage.py` and open the file.

- [ ] **Step 2: Catalog every `op.create_table(...)` and `op.create_index(...)` call**

For each `create_table("foo", ...)`, the inverse is `op.drop_table("foo")`. For each `create_index("ix_foo_bar", ...)`, inverse is `op.drop_index("ix_foo_bar", table_name="foo")`. Order matters: drop indexes before tables, drop tables in reverse-dependency order (FK children before parents).

- [ ] **Step 3: Write `downgrade()`**

At the bottom of the file, replace the empty `def downgrade():` with a concrete implementation. Example shape (fill with the real table names from Step 2):

```python
def downgrade() -> None:
    # Drop indexes first
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_index("ix_memberships_workspace_id", table_name="memberships")
    # ... every index created in upgrade ...

    # Drop tables in reverse FK order (children first)
    op.drop_table("invitations")
    op.drop_table("memberships")
    op.drop_table("sessions")
    op.drop_table("projects")
    op.drop_table("workspaces")
    op.drop_table("users")
    # ... every table created in upgrade ...
```

The task author must read the actual `upgrade()` body to produce the exhaustive, correctly-ordered list — do not guess table names. If the `upgrade()` contains `op.execute(...)` data-migration SQL, add compensating `op.execute(...)` statements or a comment explaining irreversibility.

- [ ] **Step 4: Test the round-trip locally**

Run:

```bash
cd backend
export DATABASE_URL="sqlite:///./_migration_test.db"
rm -f _migration_test.db
alembic upgrade head
alembic downgrade base
alembic upgrade head
rm -f _migration_test.db
```

Expected: no errors at any step.

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/14a7b9398bb7_phase1_8_full_coverage.py
git commit -m "fix(alembic): implement downgrade for phase1_8 migration"
```

---

## Task 12: Alembic discipline doc + CI check

**Files:**
- Create: `docs/ops/MIGRATIONS.md`
- Create: `.github/workflows/migrations.yml`

- [ ] **Step 1: Write `docs/ops/MIGRATIONS.md`**

```markdown
# Database Migrations

## Rules

1. **Every migration must implement `downgrade()`.** If a change is genuinely irreversible (dropping data, one-way schema transforms), `downgrade()` must `raise NotImplementedError("Irreversible: <reason>")` with justification — silence is not allowed.
2. **One logical change per migration.** Do not bundle unrelated schema changes.
3. **Never edit a merged migration.** Create a new one that patches forward.
4. **Destructive operations (DROP COLUMN / DROP TABLE / ALTER TYPE with data loss) require an explicit comment** naming the approver and the rollback plan.
5. **Test round-trip locally before committing:**
   ```bash
   alembic upgrade head && alembic downgrade -1 && alembic upgrade head
   ```

## Creating a new migration

```bash
cd backend
alembic revision --autogenerate -m "short_slug"
# Edit the generated file: verify upgrade() and write downgrade()
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

## Deploy order

1. Merge migration PR (migration runs on deploy; app code must tolerate both old and new schema).
2. Merge app-code PR that depends on the migration.

Never ship an app change and its migration in the same PR unless the code is backward-compatible with the old schema.
```

- [ ] **Step 2: Write `.github/workflows/migrations.yml`**

```yaml
name: migrations

on:
  pull_request:
    paths: ["backend/alembic/versions/**"]

jobs:
  roundtrip:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: backend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
          cache-dependency-path: backend/requirements.txt
      - run: pip install -r requirements.txt
      - name: Round-trip migrations on SQLite
        env:
          DATABASE_URL: "sqlite:///./_ci_migration.db"
        run: |
          alembic upgrade head
          alembic downgrade base
          alembic upgrade head
```

- [ ] **Step 3: Commit**

```bash
git add docs/ops/MIGRATIONS.md .github/workflows/migrations.yml
git commit -m "docs+ci: alembic discipline doc and migration round-trip check"
```

---

## Task 13: `.dockerignore` at repo root

**Files:**
- Create: `.dockerignore`

- [ ] **Step 1: Write `.dockerignore`**

```
**/.git
**/.github
**/node_modules
**/__pycache__
**/*.pyc
**/.venv
**/venv
**/.env
**/.env.*
!**/.env.example
**/.next
**/dist
**/build
**/.DS_Store
**/data
**/tmp
**/*.log
**/coverage
**/.pytest_cache
**/.mypy_cache
**/.ruff_cache
frontend/.next
backend/static/processed
backend/data
docs
```

- [ ] **Step 2: Commit**

```bash
git add .dockerignore
git commit -m "chore(docker): add .dockerignore"
```

---

## Task 14: Backend Dockerfile

**Files:**
- Create: `backend/Dockerfile`

- [ ] **Step 1: Write `backend/Dockerfile`**

```dockerfile
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps: ffmpeg for video, libpq for Postgres, build tools for some wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libpq5 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY backend /app/backend
COPY backend/alembic.ini /app/alembic.ini

# Non-root user
RUN useradd --create-home --uid 1001 app && chown -R app:app /app
USER app

ENV PORT=8000 \
    APP_VERSION=dev
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT}/healthz" || exit 1

WORKDIR /app/backend
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
```

- [ ] **Step 2: Build locally to verify**

Run from repo root: `docker build -f backend/Dockerfile -t flowcut-backend:local .`
Expected: successful build.

- [ ] **Step 3: Commit**

```bash
git add backend/Dockerfile
git commit -m "feat(docker): add backend Dockerfile with healthcheck"
```

---

## Task 15: Frontend Dockerfile

**Files:**
- Create: `frontend/Dockerfile`

- [ ] **Step 1: Write `frontend/Dockerfile`**

```dockerfile
FROM node:20-alpine AS deps
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

FROM node:20-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY frontend ./
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000

RUN addgroup --system --gid 1001 app && adduser --system --uid 1001 --ingroup app app

COPY --from=build --chown=app:app /app/.next ./.next
COPY --from=build --chown=app:app /app/public ./public
COPY --from=build --chown=app:app /app/package.json ./package.json
COPY --from=build --chown=app:app /app/node_modules ./node_modules
COPY --from=build --chown=app:app /app/next.config.js ./next.config.js

USER app
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD wget -qO- "http://127.0.0.1:${PORT}/" >/dev/null 2>&1 || exit 1

CMD ["npm", "run", "start"]
```

- [ ] **Step 2: Build locally**

Run from repo root: `docker build -f frontend/Dockerfile -t flowcut-frontend:local .`
Expected: successful build.

- [ ] **Step 3: Commit**

```bash
git add frontend/Dockerfile
git commit -m "feat(docker): add frontend Dockerfile (multi-stage build)"
```

---

## Task 16: docker-compose for local + bare-VM

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example` (repo root, if one doesn't exist; otherwise extend)

- [ ] **Step 1: Write `docker-compose.yml`**

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: flowcut
      POSTGRES_PASSWORD: flowcut
      POSTGRES_DB: flowcut
    volumes:
      - db_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U flowcut"]
      interval: 10s
      timeout: 5s
      retries: 5
    ports:
      - "127.0.0.1:5432:5432"

  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    env_file: .env
    environment:
      DATABASE_URL: postgresql+psycopg2://flowcut:flowcut@db:5432/flowcut
      APP_ENV: ${APP_ENV:-development}
      APP_VERSION: ${APP_VERSION:-dev}
    depends_on:
      db:
        condition: service_healthy
    ports:
      - "8000:8000"
    volumes:
      - backend_storage:/app/backend/data

  frontend:
    build:
      context: .
      dockerfile: frontend/Dockerfile
    env_file: .env
    environment:
      NEXT_PUBLIC_APP_ENV: ${APP_ENV:-development}
      NEXT_PUBLIC_APP_VERSION: ${APP_VERSION:-dev}
    depends_on:
      - backend
    ports:
      - "3000:3000"

volumes:
  db_data:
  backend_storage:
```

- [ ] **Step 2: Write `.env.example`**

```bash
# Core
APP_ENV=development
APP_VERSION=dev

# Backend
SECRET_KEY=change-me-generate-with-openssl-rand-hex-32
DATABASE_URL=postgresql+psycopg2://flowcut:flowcut@localhost:5432/flowcut
CORS_ORIGINS=http://localhost:3000
FRONTEND_URL=http://localhost:3000
API_BASE_URL=http://localhost:8000

# Observability
SENTRY_DSN=
SENTRY_TRACES_SAMPLE_RATE=0.1

# Frontend
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_SENTRY_DSN=
NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE=0.1

# Providers (leave blank unless used)
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
DEEPGRAM_API_KEY=
STRIPE_API_KEY=
STRIPE_WEBHOOK_SECRET=
YOUTUBE_CLIENT_ID=
YOUTUBE_CLIENT_SECRET=
```

- [ ] **Step 3: Smoke-test compose**

Run from repo root:

```bash
cp .env.example .env
docker compose up -d --build
sleep 10
curl -fsS http://127.0.0.1:8000/healthz
curl -fsS http://127.0.0.1:8000/readyz
docker compose down -v
```

Expected: both health endpoints return `status: ok/ready`.

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml .env.example
git commit -m "feat(docker): add docker-compose and .env.example for bare-vm deploy"
```

---

## Task 17: Bare-VM deployment runbook

**Files:**
- Create: `docs/ops/DEPLOYMENT.md`

- [ ] **Step 1: Write `docs/ops/DEPLOYMENT.md`**

```markdown
# Flowcut Bare-VM Deployment

Target: a single Ubuntu 22.04+ VM with Docker and docker-compose-plugin installed.

## One-time VM setup

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin git
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"   # log out and back in after this
```

## First deploy

```bash
git clone <repo-url> /opt/flowcut
cd /opt/flowcut
cp .env.example .env
# Edit .env — set SECRET_KEY (openssl rand -hex 32), real DB URL, Sentry DSN, provider keys
docker compose pull || true
docker compose up -d --build
curl -fsS http://127.0.0.1:8000/healthz
curl -fsS http://127.0.0.1:8000/readyz
```

Put a reverse proxy (Caddy or nginx) in front for TLS.

### Caddy example

```
flowcut.example.com {
    reverse_proxy /api/* 127.0.0.1:8000
    reverse_proxy /healthz 127.0.0.1:8000
    reverse_proxy /readyz 127.0.0.1:8000
    reverse_proxy 127.0.0.1:3000
}
```

## Rolling an update

```bash
cd /opt/flowcut
git pull
docker compose build
docker compose up -d
docker compose exec backend sh -c "curl -fsS http://127.0.0.1:8000/readyz"
```

Rollback:

```bash
git checkout <previous-sha>
docker compose build
docker compose up -d
# If the previous version expected an older schema:
docker compose exec backend alembic downgrade -1
```

## Health probes

- `GET /healthz` — liveness. Process is up. Always 200 unless Python is on fire.
- `GET /readyz` — readiness. Process can reach the database. Returns 503 if DB is unreachable.

Configure your load balancer / monitor to:
- Use `/healthz` for liveness (restart if fails 3x).
- Use `/readyz` for traffic cutover (do not route until 200).

## Backups

- `docker compose exec db pg_dump -U flowcut flowcut > backup-$(date +%F).sql` — daily cron.
- Snapshot the `backend_storage` volume for uploaded media.

## Log collection

Logs are JSON on stdout. Ship to Loki/ELK/CloudWatch via the Docker log driver of your choice.

## Secrets

All secrets live in `/opt/flowcut/.env`. Permissions:

```bash
sudo chown root:docker /opt/flowcut/.env
sudo chmod 640 /opt/flowcut/.env
```

Never check `.env` into git. The repo contains only `.env.example`.
```

- [ ] **Step 2: Commit**

```bash
git add docs/ops/DEPLOYMENT.md
git commit -m "docs(ops): add bare-vm deployment runbook"
```

---

## Task 18: Final verification

- [ ] **Step 1: Run full backend test suite**

Run: `cd backend && pytest -q`
Expected: all tests pass (or same baseline as before this plan — no regressions).

- [ ] **Step 2: Run frontend tests**

Run: `cd frontend && npm run test:run`
Expected: green.

- [ ] **Step 3: Run typecheck**

Run: `cd frontend && npm run typecheck`
Expected: whatever baseline it hits — capture output for plan #4.

- [ ] **Step 4: Compose smoke test**

Run from repo root:

```bash
docker compose up -d --build
sleep 15
curl -fsS http://127.0.0.1:8000/healthz | grep '"status":"ok"'
curl -fsS http://127.0.0.1:8000/readyz | grep '"status":"ready"'
curl -fsS -I http://127.0.0.1:3000/ | head -1
docker compose down -v
```

Expected: all four probes succeed.

- [ ] **Step 5: Open PR**

Branch: `ops/foundation`. PR title: `chore(ops): CI, Docker, healthchecks, structured logging, Sentry, migration rollback`. Link to this plan document in the description.

---

## Out of scope for this plan (covered by later plans)

- Tightening CORS, killing the dev `SECRET_KEY`, fail-fast config — plan #2 (Secrets & config hardening).
- OAuth PKCE, CSRF, invitation race, session expiry fix — plan #3 (Auth & invitations).
- DTO cleanup, frontend typed client, N+1 — plan #4 (API contracts).
- Celery + websocket heartbeat + webhook idempotency — plan #5 (Realtime & jobs).
- IA consolidation, autosave, a11y, Playwright E2E — plan #6 (Frontend completion).
