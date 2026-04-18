# Secrets & Config Hardening Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans.

**Goal:** Eliminate the dev-shortcut patterns in config and auth: kill the hardcoded `SECRET_KEY`, fail-fast on missing production secrets, tighten CORS off wildcards, gate `ENABLE_DEV_LOGIN` by environment, and standardize timezone-aware UTC everywhere so session/invite/calendar expiry is not ±1hr randomly.

**Architecture:** One `config.py` boot-time validator that checks `APP_ENV == "production"` and refuses to start if critical secrets are missing or set to known dev values. A new `common/time.py` with `utc_now()` returning a timezone-aware `datetime`. Every `datetime.utcnow()` call site migrated. CORS narrowed to the configured origin list with explicit methods/headers.

**Tech Stack:** FastAPI, Pydantic, Python stdlib `datetime`.

---

## File Structure

**Created:**
- `backend/common/__init__.py`
- `backend/common/time.py` — `utc_now()`, `ensure_utc()`
- `backend/tests/test_config_validation.py`
- `backend/tests/test_time_helpers.py`

**Modified:**
- `backend/config.py` — add `APP_ENV`, `SECRET_KEY`, `ENABLE_DEV_LOGIN`, `STRIPE_WEBHOOK_SECRET` gating; add `validate_production_config()` called from bootstrap
- `backend/bootstrap.py` — call validator at startup
- `backend/main.py` — tighten CORS: explicit methods, specific headers (include `X-Request-ID`, `X-Flowcut-Token`, `Authorization`, `Content-Type`)
- `backend/routes/auth.py` — remove hardcoded `dev-secret-key-change-in-prod`; import `SECRET_KEY` + `ENABLE_DEV_LOGIN` from config
- `backend/dependencies.py` — use `utc_now()` for expiry comparison
- `backend/services/token_refresh.py` — three `datetime.utcnow()` → `utc_now()`
- `backend/services/sie/performance.py` — one `datetime.utcnow()` → `utc_now()`
- `backend/routes/calendar.py` — one `datetime.utcnow()` → `utc_now()`
- `backend/tests/test_auth_oauth.py` — one `datetime.utcnow()` → `utc_now()` (in test fixture)

---

## Task 1: Time helpers module (TDD)

- [ ] Write `backend/tests/test_time_helpers.py`:

```python
from datetime import datetime, timezone

from common.time import ensure_utc, utc_now


def test_utc_now_is_timezone_aware():
    now = utc_now()
    assert now.tzinfo is not None
    assert now.utcoffset().total_seconds() == 0


def test_ensure_utc_on_naive_datetime():
    naive = datetime(2026, 4, 18, 12, 0, 0)
    aware = ensure_utc(naive)
    assert aware.tzinfo is timezone.utc


def test_ensure_utc_on_aware_datetime_passthrough():
    aware = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
    assert ensure_utc(aware) is aware


def test_ensure_utc_none_returns_none():
    assert ensure_utc(None) is None
```

- [ ] Run — expect failure (module missing).
- [ ] Create `backend/common/__init__.py` (empty).
- [ ] Create `backend/common/time.py`:

```python
from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
```

- [ ] Run tests → green. Commit.

## Task 2: Config validation (TDD)

- [ ] Write `backend/tests/test_config_validation.py`:

```python
import os

import pytest

from config import validate_production_config


def _set_env(monkeypatch, **kwargs):
    for k, v in kwargs.items():
        if v is None:
            monkeypatch.delenv(k, raising=False)
        else:
            monkeypatch.setenv(k, v)


def test_development_env_allows_defaults(monkeypatch):
    _set_env(monkeypatch, APP_ENV="development", SECRET_KEY=None)
    # Should not raise in development
    validate_production_config()


def test_production_requires_secret_key(monkeypatch):
    _set_env(monkeypatch, APP_ENV="production", SECRET_KEY="")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        validate_production_config()


def test_production_rejects_dev_secret_key(monkeypatch):
    _set_env(monkeypatch, APP_ENV="production", SECRET_KEY="dev-secret-key-change-in-prod")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        validate_production_config()


def test_production_rejects_dev_login_enabled(monkeypatch):
    _set_env(
        monkeypatch,
        APP_ENV="production",
        SECRET_KEY="a" * 32,
        ENABLE_DEV_LOGIN="true",
    )
    with pytest.raises(RuntimeError, match="ENABLE_DEV_LOGIN"):
        validate_production_config()


def test_production_ok_with_strong_config(monkeypatch):
    _set_env(
        monkeypatch,
        APP_ENV="production",
        SECRET_KEY="a" * 32,
        ENABLE_DEV_LOGIN="false",
        DATABASE_URL="postgresql://user:pw@host/db",
    )
    validate_production_config()
```

- [ ] Run — expect failure.
- [ ] Modify `backend/config.py`: add `APP_ENV`, move `SECRET_KEY`/`ENABLE_DEV_LOGIN` into config, add `validate_production_config()`:

```python
APP_ENV = os.environ.get("APP_ENV", "development").strip().lower()
SECRET_KEY = os.environ.get("SECRET_KEY", "")
ENABLE_DEV_LOGIN = _bool_env("ENABLE_DEV_LOGIN", False)
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

_DEV_SECRETS = {"dev-secret-key-change-in-prod", "change-me-before-starting", ""}


def validate_production_config() -> None:
    if APP_ENV != "production":
        return
    errors: list[str] = []
    if SECRET_KEY in _DEV_SECRETS or len(SECRET_KEY) < 32:
        errors.append("SECRET_KEY must be set to a 32+ char secret in production")
    if ENABLE_DEV_LOGIN:
        errors.append("ENABLE_DEV_LOGIN must be false in production")
    if DATABASE_URL.startswith("sqlite:"):
        errors.append("DATABASE_URL must not be SQLite in production")
    if errors:
        raise RuntimeError("Invalid production config:\n  - " + "\n  - ".join(errors))
```

- [ ] Run tests → green.
- [ ] Call `validate_production_config()` from `backend/bootstrap.py` at lifespan start (fail-fast).
- [ ] Update `backend/routes/auth.py` to import `SECRET_KEY` and `ENABLE_DEV_LOGIN` from `config` instead of reading env directly; remove the `"dev-secret-key-change-in-prod"` literal.
- [ ] Run full test suite. Commit.

## Task 3: CORS tightening

- [ ] Modify `backend/main.py` `CORSMiddleware` block:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Flowcut-Token",
        "X-Request-ID",
        "X-CSRF-Token",
    ],
    expose_headers=["X-Request-ID"],
    max_age=600,
)
```

- [ ] Confirm backend tests still green (they send from TestClient which doesn't CORS).
- [ ] Commit.

## Task 4: Replace `datetime.utcnow()` in app code

- [ ] `backend/dependencies.py:35` — replace `< datetime.utcnow()` with `< utc_now()`. Import `from common.time import utc_now`. If `session.expires_at` is naive, apply `ensure_utc()` to it before comparison.
- [ ] `backend/services/token_refresh.py` — three call sites → `utc_now()`.
- [ ] `backend/services/sie/performance.py` — one call site → `utc_now()`.
- [ ] `backend/routes/calendar.py:27` — one call site → `utc_now()`.
- [ ] `backend/tests/test_auth_oauth.py:88` — one call site → `utc_now()`.
- [ ] `backend/routes/auth.py:_utc_now` — replace its body to call `utc_now()` (keep the helper name locally or drop it and use `utc_now` directly). Ensure `expires_at` comparisons don't mix naive+aware.
- [ ] Run full test suite. Commit.

## Task 5: Final verification

- [ ] `ruff check .` clean
- [ ] `pytest -q` all pass (baseline + 4 new config tests + 4 time tests = baseline + 8)
- [ ] Commit any residuals.
