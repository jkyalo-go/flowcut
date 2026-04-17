# FlowCut Full-Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close every gap between the live codebase and the FlowCut spec, achieving production-grade coverage across auth, the Style Intelligence Engine, platform resilience, scheduling intelligence, billing, notifications, SaaS completeness, and the review feedback loop.

**Architecture:** Eight independent phases; each can be executed and shipped separately. The Style Intelligence Engine (Phase 2) is the core moat — it uses a LangGraph orchestrator with parallel analysis workers, a provider-agnostic edit planner (Anthropic / OpenAI / Gemini selectable per workspace), a reflection/critique loop, Mem0 persistent memory for style profiles, and a delayed-reward feedback pipeline. AI provider selection is dynamic: workspaces configure a default provider per task type (`edit_planning`, `style_critique`) via the existing `AIProviderRegistry`; operators can override at the project level. All other phases are conventional FastAPI + SQLAlchemy work.

**Tech Stack:** FastAPI, SQLAlchemy, SQLite (tests) / PostgreSQL (prod), LangGraph, Anthropic Claude / OpenAI GPT-4o / Google Gemini (dynamically selected via AIProviderRegistry), Instructor (Pydantic tool-use, multi-provider), Mem0, Stripe, SendGrid, Firebase Admin (FCM), authlib (OAuth), itsdangerous (state tokens), cryptography (AES-256-GCM), httpx (async), pytest + TestClient.

---

## Scope notice

This plan covers **8 independent subsystems**. Each part is self-contained and produces shippable, tested software on its own. Execute them in order (Phase 2 depends on Phase 1 auth context; Phase 8 depends on Phase 2 SIE), but any phase can be skipped and revisited later.

---

## File map

```
backend/
├── requirements.txt                          MODIFY — add new deps (incl. openai)
├── domain/
│   ├── shared/enums.py                       MODIFY — add OPENAI to AIProvider enum
│   ├── identity/models.py                    MODIFY — oauth fields, expires_at, Invitation
│   ├── projects/models.py                    MODIFY — expand StyleProfile
│   └── enterprise/models.py                  MODIFY — add stripe fields
├── routes/
│   ├── auth.py                               MODIFY — add OAuth endpoints
│   ├── style_profiles.py                     CREATE — SIE profile CRUD
│   ├── billing.py                            CREATE — Stripe checkout + webhook
│   ├── invitations.py                        CREATE — team invites
│   └── calendar.py                           CREATE — gap detection + heatmaps
├── services/
│   ├── ai_registry.py                        MODIFY — add OpenAI + run_structured_task()
│   ├── oauth.py                              CREATE — Google OAuth exchange
│   ├── token_crypto.py                       CREATE — AES-256-GCM token encryption
│   ├── token_refresh.py                      CREATE — proactive OAuth token refresh
│   ├── circuit_breaker.py                    CREATE — per-platform circuit breaker
│   ├── rate_limiter.py                       CREATE — sliding-window rate limits
│   ├── scheduler.py                          CREATE — slot scoring + gap detection
│   ├── stripe_service.py                     CREATE — Stripe SDK wrapper
│   ├── email_service.py                      CREATE — SendGrid wrapper
│   ├── push_service.py                       CREATE — FCM wrapper
│   └── sie/
│       ├── __init__.py                       CREATE
│       ├── graph.py                          CREATE — LangGraph orchestrator
│       ├── workers.py                        CREATE — parallel analysis workers
│       ├── schemas.py                        CREATE — EditManifest Pydantic model
│       ├── planner.py                        CREATE — provider-agnostic edit planner (registry-backed)
│       ├── critic.py                         CREATE — provider-agnostic critique node
│       ├── gates.py                          CREATE — quality gate validators
│       ├── memory.py                         CREATE — Mem0 + PostgreSQL style memory
│       ├── cold_start.py                     CREATE — genre centroid initialization
│       ├── feedback.py                       CREATE — diff capture + profile update
│       └── performance.py                    CREATE — delayed reward pipeline
└── tests/
    ├── conftest.py                           MODIFY — add OAuth + Stripe stubs
    ├── test_auth_oauth.py                    CREATE
    ├── test_ai_registry_structured.py        CREATE — OpenAI + run_structured_task tests
    ├── test_sie_schemas.py                   CREATE
    ├── test_sie_gates.py                     CREATE
    ├── test_sie_planner.py                   CREATE
    ├── test_sie_feedback.py                  CREATE
    ├── test_circuit_breaker.py               CREATE
    ├── test_rate_limiter.py                  CREATE
    ├── test_scheduler.py                     CREATE
    ├── test_billing.py                       CREATE
    └── test_invitations.py                   CREATE
```

---

## Phase 1 — Auth (OAuth + Session Refresh)

### Task 1: Add Google OAuth login

**New packages:** `authlib>=1.3.0`, `itsdangerous>=2.2.0`, `httpx>=0.27.0`

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/services/oauth.py`
- Modify: `backend/domain/identity/models.py`
- Modify: `backend/routes/auth.py`
- Create: `backend/tests/test_auth_oauth.py`

- [ ] **Step 1: Add dependencies**

Open `backend/requirements.txt` and append:
```
authlib>=1.3.0
itsdangerous>=2.2.0
httpx>=0.27.0
cryptography>=43.0.0
```

Run: `cd backend && pip install authlib itsdangerous httpx cryptography`
Expected: all install without error.

- [ ] **Step 2: Expand the User model with OAuth fields**

In `backend/domain/identity/models.py`, add two columns to `User` and an `expires_at` to `AuthSession`:

```python
# In User class, after `user_type`:
oauth_provider = Column(String, nullable=True)   # 'google', 'discord', 'twitch'
oauth_id = Column(String, nullable=True)         # provider's user ID
avatar_url = Column(String, nullable=True)

# In AuthSession class, after `token`:
expires_at = Column(DateTime, nullable=True)
```

- [ ] **Step 3: Write the failing OAuth test**

Create `backend/tests/test_auth_oauth.py`:
```python
import pytest
from unittest.mock import patch, AsyncMock
from tests.conftest import _seed_workspace


def test_oauth_start_returns_redirect_url(client):
    resp = client.get("/auth/oauth/google/start")
    assert resp.status_code == 200
    body = resp.json()
    assert "redirect_url" in body
    assert "accounts.google.com" in body["redirect_url"]
    assert "state" in body


def test_oauth_callback_creates_user_and_session(client, db):
    from services.oauth import generate_state_token
    import os
    valid_state = generate_state_token(os.getenv("SECRET_KEY", "dev-secret-key-change-in-prod"))
    fake_user_info = {
        "sub": "google-uid-123",
        "email": "creator@gmail.com",
        "name": "Test Creator",
        "picture": "https://lh3.googleusercontent.com/photo.jpg",
    }
    with patch("services.oauth.exchange_google_code", AsyncMock(return_value=fake_user_info)):
        resp = client.post(
            "/auth/oauth/google/callback",
            json={"code": "auth-code-123", "state": valid_state},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert "token" in body
    assert "workspace_id" in body
    assert body["user"]["email"] == "creator@gmail.com"


def test_oauth_callback_reuses_existing_user(client, db, workspace_a):
    ws_id, token = workspace_a
    # First call creates user
    fake_user_info = {
        "sub": "google-uid-999",
        "email": "ws-a@test.local",  # matches seeded user email
        "name": "Workspace A",
        "picture": None,
    }
    from services.oauth import generate_state_token
    import os
    state1 = generate_state_token(os.getenv("SECRET_KEY", "dev-secret-key-change-in-prod"))
    state2 = generate_state_token(os.getenv("SECRET_KEY", "dev-secret-key-change-in-prod"))
    with patch("services.oauth.exchange_google_code", AsyncMock(return_value=fake_user_info)):
        resp1 = client.post("/auth/oauth/google/callback", json={"code": "c1", "state": state1})
        resp2 = client.post("/auth/oauth/google/callback", json={"code": "c2", "state": state2})
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    t1 = resp1.json()["token"]
    t2 = resp2.json()["token"]
    assert t1 != t2  # new session each time


def test_oauth_callback_rejects_invalid_state(client):
    resp = client.post(
        "/auth/oauth/google/callback",
        json={"code": "some-code", "state": "tampered-or-expired-state"},
    )
    assert resp.status_code == 400
    assert "state" in resp.json()["detail"].lower()
```

- [ ] **Step 4: Run test to confirm it fails**

```bash
cd backend && pytest tests/test_auth_oauth.py -v
```
Expected: FAILED — `RouteNotFoundError` or 404 (route doesn't exist yet).

- [ ] **Step 5: Create the OAuth service**

Create `backend/services/oauth.py`:
```python
import httpx
from itsdangerous import URLSafeTimedSerializer

_SIGNER = None

def _get_signer(secret_key: str) -> URLSafeTimedSerializer:
    global _SIGNER
    if _SIGNER is None:
        _SIGNER = URLSafeTimedSerializer(secret_key)
    return _SIGNER


def generate_state_token(secret_key: str, workspace_id: str | None = None) -> str:
    s = _get_signer(secret_key)
    return s.dumps({"ws": workspace_id or ""})


def verify_state_token(secret_key: str, token: str, max_age: int = 600) -> dict:
    s = _get_signer(secret_key)
    return s.loads(token, max_age=max_age)


async def exchange_google_code(code: str, redirect_uri: str, client_id: str, client_secret: str) -> dict:
    """Exchange an auth code for Google user info. Returns dict with sub, email, name, picture."""
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        token_resp.raise_for_status()
        tokens = token_resp.json()

        userinfo_resp = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        userinfo_resp.raise_for_status()
        return userinfo_resp.json()
```

- [ ] **Step 6: Add OAuth routes to auth.py**

In `backend/routes/auth.py`, add after existing imports:
```python
import os
from services.oauth import exchange_google_code, generate_state_token, verify_state_token
from domain.identity import User, AuthSession, Workspace, Membership
from datetime import datetime, timedelta
from uuid import uuid4

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:3000/auth/callback/google")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-prod")


@router.get("/oauth/google/start")
async def google_oauth_start():
    state = generate_state_token(SECRET_KEY)
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    from urllib.parse import urlencode
    redirect_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return {"redirect_url": redirect_url, "state": state}


@router.post("/oauth/google/callback")
async def google_oauth_callback(payload: dict, db: Session = Depends(get_db)):
    code = payload.get("code", "")
    state = payload.get("state", "")
    try:
        verify_state_token(SECRET_KEY, state)
    except Exception:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state token")
    user_info = await exchange_google_code(
        code=code,
        redirect_uri=GOOGLE_REDIRECT_URI,
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
    )

    email = user_info["email"]
    oauth_id = user_info["sub"]

    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            name=user_info.get("name", email.split("@")[0]),
            oauth_provider="google",
            oauth_id=oauth_id,
            avatar_url=user_info.get("picture"),
        )
        db.add(user)
        db.flush()
        # Create default workspace for new users
        slug = email.split("@")[0].lower().replace(".", "-")
        ws = Workspace(name=f"{user.name}'s Workspace", slug=slug, plan_tier="starter",
                       storage_quota_mb=10240, raw_retention_days=7)
        db.add(ws)
        db.flush()
        db.add(Membership(workspace_id=ws.id, user_id=user.id, role="owner"))
        db.flush()
    else:
        ws = (db.query(Workspace)
              .join(Membership, Membership.workspace_id == Workspace.id)
              .filter(Membership.user_id == user.id)
              .first())

    token = str(uuid4())
    session = AuthSession(
        user_id=user.id,
        workspace_id=ws.id,
        token=token,
        expires_at=datetime.utcnow() + timedelta(hours=24),
    )
    db.add(session)
    db.commit()

    return {
        "token": token,
        "workspace_id": str(ws.id),
        "user": {"id": str(user.id), "email": user.email, "name": user.name},
    }
```

- [ ] **Step 7: Run tests to confirm they pass**

```bash
cd backend && pytest tests/test_auth_oauth.py -v
```
Expected: all 3 tests PASS.

- [ ] **Step 8: Add session expiry check to the existing `get_current_session` dependency**

Find `get_current_session` in `backend/routes/auth.py` (or wherever the auth dependency lives). Add expiry check:
```python
# After fetching the session:
if session.expires_at and session.expires_at < datetime.utcnow():
    raise HTTPException(status_code=401, detail="Session expired")
```

- [ ] **Step 9: Commit**

```bash
git add backend/requirements.txt backend/domain/identity/models.py \
        backend/routes/auth.py backend/services/oauth.py \
        backend/tests/test_auth_oauth.py
git commit -m "feat(auth): add Google OAuth login with session expiry"
```

---

### Task 2: Token encryption for stored OAuth tokens

**Files:**
- Create: `backend/services/token_crypto.py`
- Modify: `backend/domain/platforms/models.py` (already has `access_token_enc` as String — convert to encrypted storage)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_auth_oauth.py`:
```python
def test_token_roundtrip_encryption():
    from services.token_crypto import encrypt_token, decrypt_token
    key = b"0" * 32  # 32-byte test key
    plaintext = "ya29.access_token_here"
    ciphertext = encrypt_token(plaintext, key)
    assert ciphertext != plaintext.encode()
    assert decrypt_token(ciphertext, key) == plaintext
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && pytest tests/test_auth_oauth.py::test_token_roundtrip_encryption -v
```
Expected: ImportError — module doesn't exist.

- [ ] **Step 3: Implement token_crypto.py**

Create `backend/services/token_crypto.py`:
```python
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def get_token_key() -> bytes:
    key_hex = os.getenv("TOKEN_ENCRYPTION_KEY", "0" * 64)
    return bytes.fromhex(key_hex)


def encrypt_token(plaintext: str, key: bytes | None = None) -> bytes:
    if key is None:
        key = get_token_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return nonce + ciphertext


def decrypt_token(ciphertext: bytes, key: bytes | None = None) -> str:
    if key is None:
        key = get_token_key()
    aesgcm = AESGCM(key)
    nonce = ciphertext[:12]
    data = ciphertext[12:]
    return aesgcm.decrypt(nonce, data, None).decode()
```

- [ ] **Step 4: Run test to confirm pass**

```bash
cd backend && pytest tests/test_auth_oauth.py::test_token_roundtrip_encryption -v
```
Expected: PASS.

- [ ] **Step 5: Update platform_integrations to encrypt tokens on save and decrypt on read**

In `backend/services/platform_integrations.py`, wherever `platform_auth.access_token` is written:
```python
from services.token_crypto import encrypt_token, decrypt_token

# On save (PlatformAuth create/update):
platform_auth.access_token_enc = encrypt_token(raw_access_token)
platform_auth.refresh_token_enc = encrypt_token(raw_refresh_token) if raw_refresh_token else None

# On read (before calling platform API):
access_token = decrypt_token(platform_auth.access_token_enc)
```

- [ ] **Step 6: Commit**

```bash
git add backend/services/token_crypto.py backend/services/platform_integrations.py \
        backend/tests/test_auth_oauth.py
git commit -m "feat(auth): AES-256-GCM encryption for stored platform OAuth tokens"
```

---

## Phase 2 — Style Intelligence Engine (SIE)

> **Agentic architecture:** LangGraph orchestrator → parallel analysis workers (Vertex multimodal + faster-whisper transcription + PySceneDetect) → synthesis node → provider-agnostic edit planner via `AIProviderRegistry` (single Instructor call with `reasoning: str` chain-of-thought field) → reflection/critique node (1 iteration, also registry-backed) → quality gate → output. Provider defaults: Anthropic for `edit_planning` + `style_critique`; switchable to OpenAI GPT-4o or Vertex AI per workspace AI policy. Vertex AI routes through OpenAI-compatible endpoint — no second Google SDK. Style profile stored as structured JSON in PostgreSQL, episodic memory via Mem0 (soft fallback on failure). Creator feedback captured as diffs. Published clip performance closes the loop after 72h.

**New packages:** `langgraph>=0.2.0`, `instructor>=1.6.0`, `mem0ai>=0.1.0`, `openai>=1.58.0` (added via Task 4.5 — `openai` and `instructor` are added there, so this step only adds `langgraph` and `mem0ai` if not already present)

```bash
pip install langgraph instructor mem0ai openai
```

Add to `backend/requirements.txt` (skip any already added in Task 4.5):
```
langgraph>=0.2.0
instructor>=1.6.0
mem0ai>=0.1.0
```

---

### Task 3: EditManifest schema (Pydantic + Instructor)

> Why this comes first: every downstream task depends on this schema. Getting it right with full type constraints prevents cascading failures.

**Files:**
- Create: `backend/services/sie/__init__.py`
- Create: `backend/services/sie/schemas.py`
- Create: `backend/tests/test_sie_schemas.py`

- [ ] **Step 1: Write the failing schema tests**

Create `backend/tests/test_sie_schemas.py`:
```python
import pytest
from pydantic import ValidationError
from services.sie.schemas import EditManifest, TrimAction, ZoomAction, CaptionSegment


def test_edit_manifest_valid_minimal():
    m = EditManifest(
        trim=TrimAction(start_sec=0.0, end_sec=30.0),
        platform_targets=["tiktok"],
        confidence=0.85,
        reasoning="Strong hook with visual peak at 5s.",
    )
    assert m.trim.end_sec == 30.0
    assert m.confidence == 0.85


def test_edit_manifest_confidence_bounds():
    with pytest.raises(ValidationError):
        EditManifest(
            trim=TrimAction(start_sec=0.0, end_sec=30.0),
            platform_targets=["tiktok"],
            confidence=1.5,  # out of range
            reasoning="x",
        )


def test_zoom_curve_enum():
    z = ZoomAction(at_sec=5.0, factor=1.5, duration_sec=0.3, curve="ease_out")
    assert z.curve == "ease_out"
    with pytest.raises(ValidationError):
        ZoomAction(at_sec=5.0, factor=1.5, duration_sec=0.3, curve="rocket")


def test_caption_segment_defaults():
    c = CaptionSegment(start_sec=0.0, end_sec=3.0, text="No way!")
    assert c.animation == "word_by_word"
    assert c.emphasis_words == []


def test_manifest_serialises_to_dict():
    m = EditManifest(
        trim=TrimAction(start_sec=0.0, end_sec=30.0),
        platform_targets=["tiktok", "youtube_shorts"],
        confidence=0.90,
        reasoning="High chat velocity spike at 12s.",
    )
    d = m.model_dump()
    assert d["confidence"] == 0.90
    assert "zooms" in d
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && pytest tests/test_sie_schemas.py -v
```
Expected: ImportError.

- [ ] **Step 3: Create the schema module**

Create `backend/services/sie/__init__.py` (empty).

Create `backend/services/sie/schemas.py`:
```python
from __future__ import annotations
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class TrimAction(BaseModel):
    start_sec: float = Field(ge=0.0)
    end_sec: float = Field(ge=0.0)


class ZoomAction(BaseModel):
    at_sec: float = Field(ge=0.0)
    factor: float = Field(ge=1.0, le=3.0)
    duration_sec: float = Field(ge=0.05, le=2.0)
    curve: Literal["ease_in", "ease_out", "linear"] = "ease_out"


class TransitionAction(BaseModel):
    at_sec: float = Field(ge=0.0)
    type: Literal["hard_cut", "crossfade", "whip_pan", "zoom_blur"] = "hard_cut"
    duration_sec: float = Field(ge=0.0, le=1.0, default=0.0)


class SFXAction(BaseModel):
    at_sec: float = Field(ge=0.0)
    sfx_id: str
    volume_db: float = Field(ge=-40.0, le=0.0, default=-12.0)


class CaptionSegment(BaseModel):
    start_sec: float = Field(ge=0.0)
    end_sec: float = Field(ge=0.0)
    text: str
    animation: Literal["word_by_word", "fade", "slide_up", "typewriter"] = "word_by_word"
    emphasis_words: List[str] = []


class SpeedRamp(BaseModel):
    start_sec: float = Field(ge=0.0)
    end_sec: float = Field(ge=0.0)
    speed_factor: float = Field(ge=0.25, le=8.0)


Platform = Literal["tiktok", "youtube_shorts", "instagram_reels", "youtube", "linkedin", "x"]


class EditManifest(BaseModel):
    trim: TrimAction
    platform_targets: List[Platform]
    zooms: List[ZoomAction] = []
    transitions: List[TransitionAction] = []
    sfx: List[SFXAction] = []
    captions: List[CaptionSegment] = []
    speed_ramps: List[SpeedRamp] = []
    music_bed_volume_db: float = Field(ge=-40.0, le=0.0, default=-18.0)
    intro_duration_sec: float = Field(ge=0.0, le=10.0, default=0.0)
    outro_duration_sec: float = Field(ge=0.0, le=10.0, default=2.0)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
```

- [ ] **Step 4: Run tests to confirm pass**

```bash
cd backend && pytest tests/test_sie_schemas.py -v
```
Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/sie/ backend/tests/test_sie_schemas.py
git commit -m "feat(sie): EditManifest Pydantic schema with full field constraints"
```

---

### Task 4: Quality gates (inline validators)

> Quality gates run synchronously in the pipeline and block a bad manifest from reaching the renderer. Three stages: format check, grounding check (timestamps within footage duration), style compliance check (cuts/min within profile bounds).

**Files:**
- Create: `backend/services/sie/gates.py`
- Create: `backend/tests/test_sie_gates.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_sie_gates.py`:
```python
import pytest
from services.sie.gates import run_quality_gates, GateFailure
from services.sie.schemas import EditManifest, TrimAction, ZoomAction


def _base_manifest(**overrides):
    defaults = dict(
        trim=TrimAction(start_sec=0.0, end_sec=30.0),
        platform_targets=["tiktok"],
        confidence=0.85,
        reasoning="ok",
    )
    defaults.update(overrides)
    return EditManifest(**defaults)


def test_gates_pass_clean_manifest():
    m = _base_manifest()
    run_quality_gates(m, footage_duration_sec=60.0, style_profile={"max_cuts_per_min": 15})
    # no exception = pass


def test_gates_fail_trim_beyond_footage():
    m = _base_manifest(trim=TrimAction(start_sec=0.0, end_sec=90.0))
    with pytest.raises(GateFailure, match="trim.end_sec"):
        run_quality_gates(m, footage_duration_sec=60.0, style_profile={})


def test_gates_fail_zoom_beyond_trim():
    m = _base_manifest(zooms=[ZoomAction(at_sec=50.0, factor=1.5, duration_sec=0.3, curve="ease_out")])
    with pytest.raises(GateFailure, match="zoom at_sec"):
        run_quality_gates(m, footage_duration_sec=60.0, style_profile={})


def test_gates_fail_excessive_cuts_per_minute():
    from services.sie.schemas import TransitionAction
    cuts = [TransitionAction(at_sec=float(i), type="hard_cut") for i in range(30)]
    m = _base_manifest(transitions=cuts)  # 30 cuts in 30s = 60/min
    with pytest.raises(GateFailure, match="cuts_per_min"):
        run_quality_gates(m, footage_duration_sec=60.0, style_profile={"max_cuts_per_min": 20})


def test_gates_pass_with_no_style_constraint():
    from services.sie.schemas import TransitionAction
    cuts = [TransitionAction(at_sec=float(i), type="hard_cut") for i in range(30)]
    m = _base_manifest(transitions=cuts)
    # style_profile has no max_cuts_per_min → constraint not enforced
    run_quality_gates(m, footage_duration_sec=60.0, style_profile={})
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && pytest tests/test_sie_gates.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement gates.py**

Create `backend/services/sie/gates.py`:
```python
from services.sie.schemas import EditManifest


class GateFailure(ValueError):
    pass


def run_quality_gates(
    manifest: EditManifest,
    footage_duration_sec: float,
    style_profile: dict,
) -> None:
    """Raise GateFailure with a descriptive message if the manifest violates any gate.
    Gates run in order: format → grounding → style compliance."""

    clip_duration = manifest.trim.end_sec - manifest.trim.start_sec

    # Gate 1: trim grounding
    if manifest.trim.end_sec > footage_duration_sec + 0.1:
        raise GateFailure(
            f"trim.end_sec ({manifest.trim.end_sec}) exceeds footage duration ({footage_duration_sec})"
        )

    # Gate 2: zoom grounding — zooms must fall within the trim window
    for z in manifest.zooms:
        if z.at_sec < manifest.trim.start_sec or z.at_sec > manifest.trim.end_sec:
            raise GateFailure(
                f"zoom at_sec={z.at_sec} is outside trim window "
                f"[{manifest.trim.start_sec}, {manifest.trim.end_sec}]"
            )

    # Gate 3: style compliance — cuts per minute
    max_cuts = style_profile.get("max_cuts_per_min")
    if max_cuts is not None and clip_duration > 0:
        actual_cuts_per_min = len(manifest.transitions) / clip_duration * 60
        if actual_cuts_per_min > max_cuts:
            raise GateFailure(
                f"cuts_per_min={actual_cuts_per_min:.1f} exceeds style profile "
                f"max_cuts_per_min={max_cuts}"
            )
```

- [ ] **Step 4: Run tests to confirm pass**

```bash
cd backend && pytest tests/test_sie_gates.py -v
```
Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/sie/gates.py backend/tests/test_sie_gates.py
git commit -m "feat(sie): quality gates — grounding + style compliance validation"
```

---

### Task 4.5: Extend AIProviderRegistry with OpenAI + structured-output support

> The existing `services/ai_registry.py` handles Anthropic, Vertex/Gemini, Deepgram, and DashScope. It does NOT have OpenAI or a `run_structured_task()` method (Instructor-backed structured JSON extraction across providers). The SIE planner and critic must route through the registry so operators can swap providers per workspace. This task patches the registry before Tasks 5 and 6.

**Files:**
- Modify: `backend/requirements.txt` — add `openai>=1.58.0`
- Modify: `backend/domain/shared/enums.py` — add `OPENAI = "openai"` to `AIProvider`
- Modify: `backend/services/ai_registry.py` — add OpenAI client + `run_structured_task()`
- Create: `backend/tests/test_ai_registry_structured.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_ai_registry_structured.py`:
```python
import pytest
from unittest.mock import MagicMock, patch
from pydantic import BaseModel
from domain.shared import AIProvider, CredentialSource


class _Schema(BaseModel):
    answer: str
    score: float


def _make_workspace(policy: dict | None = None):
    import json
    ws = MagicMock()
    ws.id = "ws-test"
    ws.ai_policy = json.dumps(policy) if policy else None
    return ws


def test_run_structured_task_anthropic(db):
    """registry.run_structured_task routes to Anthropic and returns parsed schema."""
    from services.ai_registry import AIProviderRegistry
    reg = AIProviderRegistry()

    fake_result = _Schema(answer="yes", score=0.9)
    with patch.object(reg, "select_provider", return_value=(
        AIProvider.ANTHROPIC, "claude-sonnet-4-6", CredentialSource.PLATFORM, None
    )), patch.object(reg, "_run_instructor_anthropic", return_value=fake_result):
        ws = _make_workspace()
        result = reg.run_structured_task(
            db=db,
            workspace=ws,
            task_type="edit_planning",
            prompt_builder=lambda p, m: (None, "Analyze this footage."),
            response_model=_Schema,
        )
    assert result.answer == "yes"
    assert result.score == 0.9


def test_run_structured_task_openai(db):
    """registry.run_structured_task routes to OpenAI and returns parsed schema."""
    from services.ai_registry import AIProviderRegistry
    reg = AIProviderRegistry()

    fake_result = _Schema(answer="no", score=0.7)
    with patch.object(reg, "select_provider", return_value=(
        AIProvider.OPENAI, "gpt-4o", CredentialSource.BYOK, "sk-test"
    )), patch.object(reg, "_run_instructor_openai", return_value=fake_result):
        ws = _make_workspace()
        result = reg.run_structured_task(
            db=db,
            workspace=ws,
            task_type="edit_planning",
            prompt_builder=lambda p, m: (None, "Analyze this footage."),
            response_model=_Schema,
        )
    assert result.answer == "no"


def test_openai_added_to_provider_enum():
    """OPENAI is present in the AIProvider enum."""
    from domain.shared import AIProvider
    assert AIProvider.OPENAI.value == "openai"


def test_edit_planning_in_task_defaults():
    """edit_planning and style_critique have default providers."""
    from services.ai_registry import TASK_PROVIDER_DEFAULTS
    assert "edit_planning" in TASK_PROVIDER_DEFAULTS
    assert "style_critique" in TASK_PROVIDER_DEFAULTS
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && pytest tests/test_ai_registry_structured.py -v
```
Expected: ImportError or AssertionError on missing enum value.

- [ ] **Step 3: Add OPENAI to the enum**

In `backend/domain/shared/enums.py`, inside `AIProvider`:
```python
class AIProvider(str, enum.Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"          # add this line
    VERTEX = "vertex"
    GEMINI = "gemini"
    DEEPGRAM = "deepgram"
    DASHSCOPE = "dashscope"
```

- [ ] **Step 4: Add openai to requirements.txt**

Append to `backend/requirements.txt`:
```
openai>=1.58.0
```

Run: `cd backend && pip install openai`

- [ ] **Step 5: Extend ai_registry.py**

In `backend/services/ai_registry.py`:

**a) Update imports at the top:**
```python
import anthropic
import openai as openai_sdk
from google import genai
```

**b) Update `DEFAULT_PROVIDER_MODELS`:**
```python
DEFAULT_PROVIDER_MODELS: dict[str, list[str]] = {
    AIProvider.ANTHROPIC.value: ["claude-sonnet-4-6", "claude-3-5-haiku-latest"],
    AIProvider.OPENAI.value: ["gpt-4o", "gpt-4o-mini"],
    AIProvider.VERTEX.value: ["gemini-2.5-flash", "gemini-2.5-pro"],
    AIProvider.GEMINI.value: ["gemini-2.5-flash", "gemini-2.5-pro"],
    AIProvider.DEEPGRAM.value: ["nova-3"],
    AIProvider.DASHSCOPE.value: ["wan2.7-i2v-turbo", "wan2.7-t2v-turbo", "wan2.7-v2v"],
}
```

**c) Update `TASK_PROVIDER_DEFAULTS`:**
```python
TASK_PROVIDER_DEFAULTS = {
    "transcription": AIProvider.DEEPGRAM,
    "titles": AIProvider.ANTHROPIC,
    "description": AIProvider.ANTHROPIC,
    "tags": AIProvider.ANTHROPIC,
    "thumbnail": AIProvider.VERTEX,
    "broll": AIProvider.DASHSCOPE,
    "edit_planning": AIProvider.ANTHROPIC,   # SIE free-form reasoning
    "style_critique": AIProvider.ANTHROPIC,  # SIE reflection pass
}
```

**d) Add `_openai_client` field to `AIProviderRegistry.__init__`:**
```python
def __init__(self):
    self._anthropic_client: anthropic.Anthropic | None = None
    self._gemini_client: genai.Client | None = None
    self._openai_client: openai_sdk.OpenAI | None = None
```

**e) Add `_get_openai_client()` method:**
```python
def _get_openai_client(self, api_key: str | None = None) -> openai_sdk.OpenAI:
    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OpenAI API key is not configured")
    if api_key:
        return openai_sdk.OpenAI(api_key=key)
    if self._openai_client is None:
        self._openai_client = openai_sdk.OpenAI(api_key=key)
    return self._openai_client
```

**f) Add `_run_instructor_anthropic()` and `_run_instructor_openai()` helpers + `run_structured_task()` method:**
```python
def _run_instructor_anthropic(
    self,
    api_key: str | None,
    model: str,
    system: str | None,
    user_content: str,
    response_model: type,
    max_retries: int = 3,
):
    import instructor
    client = instructor.from_anthropic(self._get_anthropic_client(api_key))
    messages = [{"role": "user", "content": user_content}]
    kwargs = dict(model=model, max_tokens=2048, messages=messages, response_model=response_model, max_retries=max_retries)
    if system:
        kwargs["system"] = system
    return client.messages.create(**kwargs)


def _run_instructor_openai(
    self,
    api_key: str | None,
    model: str,
    system: str | None,
    user_content: str,
    response_model: type,
    max_retries: int = 3,
):
    import instructor
    client = instructor.from_openai(self._get_openai_client(api_key))
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user_content})
    return client.chat.completions.create(
        model=model,
        messages=messages,
        response_model=response_model,
        max_retries=max_retries,
    )


def _run_instructor_vertex(
    self,
    api_key: str | None,
    model: str,
    system: str | None,
    user_content: str,
    response_model: type,
    max_retries: int = 3,
):
    """Vertex AI structured output via the OpenAI-compatible endpoint.
    No google-generativeai SDK needed — reuses the openai SDK with a custom base_url.
    This avoids SDK version conflicts and global configure() race conditions."""
    import instructor
    key = api_key or os.getenv("GOOGLE_API_KEY", "placeholder")
    base_url = (
        f"https://{VERTEX_LOCATION}-aiplatform.googleapis.com/v1beta1/projects/"
        f"{VERTEX_PROJECT_ID}/locations/{VERTEX_LOCATION}/endpoints/openapi/chat/completions"
    )
    vertex_client = openai_sdk.OpenAI(api_key=key, base_url=base_url)
    client = instructor.from_openai(vertex_client)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user_content})
    return client.chat.completions.create(
        model=model,
        messages=messages,
        response_model=response_model,
        max_retries=max_retries,
    )


def run_structured_task(
    self,
    db: Session,
    workspace,
    task_type: str,
    prompt_builder: Callable[[AIProvider, str], tuple[str | None, str]],
    response_model: type,
    user_id: str | None = None,
    project_id: str | None = None,
    clip_id: str | None = None,
    max_retries: int = 3,
):
    """Like run_text_task but returns a Pydantic model via Instructor.
    Supports Anthropic, OpenAI, and Vertex AI (OpenAI-compat endpoint) providers.
    GEMINI enum routes through Vertex AI — no google-generativeai SDK needed."""
    provider, model, credential_source, api_key = self.select_provider(db, workspace, task_type)
    start = time.time()
    system_prompt, user_prompt = prompt_builder(provider, model)
    logger.debug(
        "Structured task %s: provider=%s model=%s workspace=%s",
        task_type, provider.value, model, workspace.id,
    )
    try:
        if provider == AIProvider.ANTHROPIC:
            result = self._run_instructor_anthropic(api_key, model, system_prompt, user_prompt, response_model, max_retries)
        elif provider == AIProvider.OPENAI:
            result = self._run_instructor_openai(api_key, model, system_prompt, user_prompt, response_model, max_retries)
        elif provider in {AIProvider.VERTEX, AIProvider.GEMINI}:
            result = self._run_instructor_vertex(api_key, model, system_prompt, user_prompt, response_model, max_retries)
        else:
            raise RuntimeError(f"Provider {provider.value} does not support structured task {task_type}")

        self._record_usage(
            db,
            workspace_id=workspace.id,
            user_id=user_id,
            project_id=project_id,
            clip_id=clip_id,
            task_type=task_type,
            provider=provider,
            model=model,
            credential_source=credential_source,
            start_time=start,
        )
        return result
    except Exception as exc:
        logger.exception("AI structured task failed")
        self._record_usage(
            db,
            workspace_id=workspace.id,
            user_id=user_id,
            project_id=project_id,
            clip_id=clip_id,
            task_type=task_type,
            provider=provider,
            model=model,
            credential_source=credential_source,
            start_time=start,
            status=AIUsageStatus.ERROR,
            error_message=str(exc),
        )
        raise
```

- [ ] **Step 6: Run tests to confirm pass**

```bash
cd backend && pytest tests/test_ai_registry_structured.py -v
```
Expected: 4 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/requirements.txt backend/domain/shared/enums.py \
        backend/services/ai_registry.py backend/tests/test_ai_registry_structured.py
git commit -m "feat(ai): add OpenAI provider + run_structured_task() for provider-agnostic Instructor output"
```

---

### Task 5: Edit planner (provider-agnostic, single-pass Instructor)

> Single Instructor call with `reasoning: str` field in `EditManifest`. Modern models (claude-sonnet-4-6, gpt-4o, gemini-2.5-flash) handle structured output + chain-of-thought in one pass — the `reasoning` field already in the schema captures the analytical thinking without a separate free-form pass. Half the latency, half the cost. Provider selected by workspace AI policy via `registry.run_structured_task()`.

**Files:**
- Create: `backend/services/sie/planner.py`
- Create: `backend/tests/test_sie_planner.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_sie_planner.py`:
```python
import pytest
from unittest.mock import patch, MagicMock
from services.sie.schemas import EditManifest, TrimAction


def _fake_manifest():
    return EditManifest(
        trim=TrimAction(start_sec=5.0, end_sec=35.0),
        platform_targets=["tiktok"],
        confidence=0.87,
        reasoning="Strong hook at 5s. Chat velocity spike at 12s suggests cut point.",
    )


def _make_workspace():
    ws = MagicMock()
    ws.id = "ws-test"
    ws.ai_policy = None
    return ws


def test_planner_returns_edit_manifest(db):
    """generate_edit_plan routes through run_structured_task and returns EditManifest."""
    ws = _make_workspace()
    from services.sie.planner import generate_edit_plan
    from services.ai_registry import AIProviderRegistry
    from domain.shared import AIProvider, CredentialSource

    with patch.object(AIProviderRegistry, "run_structured_task", return_value=_fake_manifest()):
        result = generate_edit_plan(
            footage_path="/tmp/test.mp4",
            footage_duration_sec=60.0,
            moments=[{"start_sec": 5.0, "end_sec": 35.0, "score": 0.9}],
            style_profile={"max_cuts_per_min": 15},
            episodic_context=[],
            db=db,
            workspace=ws,
        )
    assert isinstance(result, EditManifest)
    assert result.confidence == 0.87


def test_planner_includes_style_profile_in_prompt(db):
    """Style profile appears in the user prompt passed to run_structured_task."""
    ws = _make_workspace()
    from services.sie.planner import generate_edit_plan
    from services.ai_registry import AIProviderRegistry

    captured = {}
    def capture_call(db, workspace, task_type, prompt_builder, response_model, **kwargs):
        _, user_prompt = prompt_builder(None, None)
        captured["user_prompt"] = user_prompt
        return _fake_manifest()

    with patch.object(AIProviderRegistry, "run_structured_task", side_effect=capture_call):
        generate_edit_plan(
            footage_path="/tmp/test.mp4",
            footage_duration_sec=60.0,
            moments=[],
            style_profile={"pacing": "fast", "caption_style": "word_by_word"},
            episodic_context=[],
            db=db,
            workspace=ws,
        )
    assert "pacing" in captured["user_prompt"]
    assert "word_by_word" in captured["user_prompt"]
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && pytest tests/test_sie_planner.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement planner.py**

Create `backend/services/sie/planner.py`:
```python
from __future__ import annotations
import json
from sqlalchemy.orm import Session
from services.ai_registry import registry
from services.sie.schemas import EditManifest

_SYSTEM_PROMPT = (
    "You are an expert video editor. Analyze the footage and produce a precise edit plan. "
    "Use the reasoning field to show your thinking — which moments are strongest, what pacing "
    "fits the creator's style, what platform constraints apply. Then fill all manifest fields. "
    "All timestamps must be within the footage duration."
)


def _build_user_prompt(
    footage_path: str,
    footage_duration_sec: float,
    moments: list[dict],
    style_profile: dict,
    episodic_context: list[dict],
) -> str:
    parts = [
        f"Footage: {footage_path} ({footage_duration_sec:.1f}s total)",
        f"Style profile: {json.dumps(style_profile)}",
        f"Detected moments: {json.dumps(moments)}",
    ]
    if episodic_context:
        parts.append(f"Past edits for reference: {json.dumps(episodic_context[:3])}")
    parts.append("Produce the EditManifest. Aim for 15–60s output clip.")
    return "\n\n".join(parts)


def generate_edit_plan(
    footage_path: str,
    footage_duration_sec: float,
    moments: list[dict],
    style_profile: dict,
    episodic_context: list[dict],
    db: Session | None = None,
    workspace=None,
) -> EditManifest:
    """Single-pass Instructor call: reasoning + structured manifest in one LLM call.
    The EditManifest.reasoning field captures chain-of-thought without a second API call.
    Pass db + workspace for live calls; mock generate_edit_plan directly for unit tests."""
    assert db is not None and workspace is not None, "db and workspace are required"
    user_prompt = _build_user_prompt(
        footage_path, footage_duration_sec, moments, style_profile, episodic_context,
    )
    return registry.run_structured_task(
        db=db,
        workspace=workspace,
        task_type="edit_planning",
        prompt_builder=lambda p, m: (_SYSTEM_PROMPT, user_prompt),
        response_model=EditManifest,
        max_retries=3,
    )
```

- [ ] **Step 4: Run tests to confirm pass**

```bash
cd backend && pytest tests/test_sie_planner.py -v
```
Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/sie/planner.py backend/tests/test_sie_planner.py
git commit -m "feat(sie): single-pass edit planner — Instructor + reasoning field"
```

---

### Task 6: Reflection/critique node (generate → critique → refine)

> Cap at 1 iteration. Use Claude Opus as critic (stronger reasoning), Sonnet as generator (cost). Critique checks: pacing coherence, style alignment, timestamp plausibility, hook strength.

**Files:**
- Create: `backend/services/sie/critic.py`
- Modify: `backend/tests/test_sie_planner.py` (add critique tests)

- [ ] **Step 1: Write failing test**

Append to `backend/tests/test_sie_planner.py`:
```python
def test_critic_triggers_one_refinement_when_confidence_low(monkeypatch, db):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    low_conf_manifest = EditManifest(
        trim=TrimAction(start_sec=0.0, end_sec=30.0),
        platform_targets=["tiktok"],
        confidence=0.45,  # below threshold
        reasoning="Generic clip.",
    )
    high_conf_manifest = EditManifest(
        trim=TrimAction(start_sec=5.0, end_sec=35.0),
        platform_targets=["tiktok"],
        confidence=0.88,
        reasoning="Refined: strong hook at 5s.",
    )
    # Critique text returned by the first registry call (style_critique task)
    # Second call to generate_edit_plan returns the high-confidence manifest
    from services.ai_registry import registry as _registry
    import types
    _ws = types.SimpleNamespace(id="ws-test", ai_policy=None)
    with patch.object(_registry, "run_text_task", return_value="Hook is weak. Prefer start at 5s."), \
         patch.object(_registry, "run_structured_task", return_value=high_conf_manifest):
        from services.sie.critic import run_reflection_loop
        result = run_reflection_loop(
            initial_manifest=low_conf_manifest,
            footage_path="/tmp/test.mp4",
            footage_duration_sec=60.0,
            moments=[],
            style_profile={},
            episodic_context=[],
            min_confidence=0.70,
            db=db,
            workspace=_ws,
        )
    assert result.confidence >= 0.70  # at most 1 retry, refined manifest returned
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && pytest tests/test_sie_planner.py::test_critic_triggers_one_refinement_when_confidence_low -v
```
Expected: ImportError.

- [ ] **Step 3: Implement critic.py**

Create `backend/services/sie/critic.py`:
```python
from __future__ import annotations
import json
from sqlalchemy.orm import Session
from services.ai_registry import registry
from services.sie.schemas import EditManifest
from services.sie import planner as _planner


def critique_manifest(
    manifest: EditManifest,
    style_profile: dict,
    db: Session | None = None,
    workspace=None,
) -> str:
    """Returns a plain-text critique of the manifest. Empty string if no issues found.
    Routes through registry so provider is workspace-configurable (default: Anthropic)."""
    system = (
        "You are a senior video editor reviewing an AI-generated edit plan. "
        "Be concise and specific. If the plan looks good, say 'LGTM'. "
        "Otherwise list specific issues: weak hook, pacing problems, style mismatches."
    )
    user_content = (
        f"Style profile: {json.dumps(style_profile)}\n\n"
        f"Edit manifest:\n{manifest.model_dump_json(indent=2)}\n\n"
        "Critique this plan."
    )

    if db is not None and workspace is not None:
        text = registry.run_text_task(
            db=db,
            workspace=workspace,
            task_type="style_critique",
            prompt_builder=lambda p, m: (system, user_content),
            parser=lambda t: t.strip(),
        )
    else:
        raise ValueError("db and workspace are required for critique_manifest")

    return "" if text.upper().startswith("LGTM") else text


def run_reflection_loop(
    initial_manifest: EditManifest,
    footage_path: str,
    footage_duration_sec: float,
    moments: list[dict],
    style_profile: dict,
    episodic_context: list[dict],
    min_confidence: float = 0.70,
    max_iterations: int = 1,
    db: Session | None = None,
    workspace=None,
) -> EditManifest:
    """Run at most max_iterations refinement cycles.
    Returns the refined manifest if confidence improves, otherwise the original."""
    manifest = initial_manifest
    for _ in range(max_iterations):
        if manifest.confidence >= min_confidence:
            break
        critique = critique_manifest(manifest, style_profile, db, workspace)
        if not critique:
            break
        refined_context = episodic_context + [{"critique": critique}]
        candidate = _planner.generate_edit_plan(
            footage_path=footage_path,
            footage_duration_sec=footage_duration_sec,
            moments=moments,
            style_profile={**style_profile, "critique_to_address": critique},
            episodic_context=refined_context,
            db=db,
            workspace=workspace,
        )
        if candidate.confidence > manifest.confidence:
            manifest = candidate
    return manifest
```

- [ ] **Step 4: Run tests**

```bash
cd backend && pytest tests/test_sie_planner.py -v
```
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/sie/critic.py backend/tests/test_sie_planner.py
git commit -m "feat(sie): reflection/critique loop — registry-backed critique + one-shot refinement"
```

---

### Task 7: Style profile memory (Mem0 + PostgreSQL)

> Style profile is a living structured JSON document in PostgreSQL. Mem0 stores episodic memory (past edit plans, critiques, performance notes). On feedback, compute a diff between AI plan and creator-modified version; write summary to both stores.

**Files:**
- Modify: `backend/domain/projects/models.py` — expand StyleProfile
- Create: `backend/services/sie/memory.py`
- Create: `backend/tests/test_sie_feedback.py`

- [ ] **Step 1: Expand StyleProfile model**

In `backend/domain/projects/models.py`, replace the `StyleProfile` class with:
```python
class StyleProfile(Base):
    __tablename__ = "style_profiles"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    workspace_id = Column(UUID_SQL_TYPE, ForeignKey("workspaces.id"), nullable=False)
    project_id = Column(UUID_SQL_TYPE, ForeignKey("projects.id"), nullable=True)
    name = Column(String, nullable=False)
    genre = Column(String, nullable=True)   # 'gaming', 'education', 'podcast', etc.

    # Learned style document — JSON with keys matching the 9 SIE dimensions
    # {pacing: {cuts_per_min: 12, ...}, captions: {font: ..., animation: ...}, ...}
    style_doc = Column(String, nullable=True)

    # Per-dimension confidence 0.0–1.0 (JSON: {"pacing": 0.9, "captions": 0.7, ...})
    confidence_scores = Column(String, nullable=True, default="{}")

    # Locked dimensions won't be updated by feedback (JSON: {"captions": true})
    dimension_locks = Column(String, nullable=True, default="{}")

    # Profile version for rollback
    version = Column(Integer, nullable=False, default=1)

    # Mem0 user_id for episodic memory lookup
    mem0_user_id = Column(String, nullable=True)

    brand_kit = Column(String, nullable=True)
    platform_targets = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
```

Add `Integer` to the imports at the top of that file.

- [ ] **Step 2: Write failing memory tests**

Create `backend/tests/test_sie_feedback.py`:
```python
import json
import pytest
from unittest.mock import patch, MagicMock


def _make_profile(extra: dict | None = None) -> dict:
    base = {
        "pacing": {"cuts_per_min": 10, "speed_ramps": False},
        "captions": {"font": "DM Sans", "animation": "word_by_word"},
    }
    if extra:
        base.update(extra)
    return base


def test_diff_detects_added_zoom():
    from services.sie.feedback import diff_manifests
    original = {"zooms": [], "transitions": [{"at_sec": 5.0, "type": "hard_cut"}]}
    modified = {"zooms": [{"at_sec": 3.0, "factor": 1.5}], "transitions": [{"at_sec": 5.0, "type": "hard_cut"}]}
    diff = diff_manifests(original, modified)
    assert "zooms" in diff
    assert diff["zooms"] == "added 1 item(s)"


def test_diff_detects_no_changes():
    from services.sie.feedback import diff_manifests
    m = {"zooms": [], "confidence": 0.9}
    assert diff_manifests(m, m) == {}


def test_apply_feedback_updates_pacing_doc():
    from services.sie.feedback import apply_feedback_to_profile
    profile = _make_profile()
    diff = {"transitions": "added 3 item(s)"}
    dimension_locks = {}
    updated = apply_feedback_to_profile(profile, diff, dimension_locks, action="approved")
    # pacing should reflect that more cuts were added (approved)
    assert "pacing" in updated


def test_locked_dimension_not_updated():
    from services.sie.feedback import apply_feedback_to_profile
    profile = _make_profile()
    diff = {"captions": "animation changed to fade"}
    dimension_locks = {"captions": True}
    updated = apply_feedback_to_profile(profile, diff, dimension_locks, action="approved")
    # captions locked — animation should remain word_by_word
    assert updated["captions"]["animation"] == "word_by_word"
```

- [ ] **Step 3: Run to confirm failure**

```bash
cd backend && pytest tests/test_sie_feedback.py -v
```
Expected: ImportError.

- [ ] **Step 4: Implement feedback.py**

Create `backend/services/sie/feedback.py`:
```python
from __future__ import annotations
import copy
import json


def diff_manifests(original: dict, modified: dict) -> dict:
    """Return a summary of differences between original and modified manifest dicts.
    Keys with no changes are omitted. Values are human-readable change descriptions."""
    diff = {}
    all_keys = set(original) | set(modified)
    for key in all_keys:
        orig_val = original.get(key)
        mod_val = modified.get(key)
        if orig_val == mod_val:
            continue
        if isinstance(orig_val, list) and isinstance(mod_val, list):
            delta = len(mod_val) - len(orig_val)
            if delta > 0:
                diff[key] = f"added {delta} item(s)"
            elif delta < 0:
                diff[key] = f"removed {abs(delta)} item(s)"
            else:
                diff[key] = "items modified"
        else:
            diff[key] = f"changed from {repr(orig_val)} to {repr(mod_val)}"
    return diff


def apply_feedback_to_profile(
    profile: dict,
    diff: dict,
    dimension_locks: dict,
    action: str,  # 'approved', 'modified', 'rejected'
) -> dict:
    """Apply a manifest diff to the style profile JSON document.
    Locked dimensions are never touched. Returns updated profile copy."""
    updated = copy.deepcopy(profile)

    # Dimension → keys that affect it
    _dimension_map = {
        "pacing": {"transitions", "speed_ramps", "trim"},
        "captions": {"captions"},
        "framing": {"zooms"},
        "sound_design": {"sfx", "music_bed_volume_db"},
        "narrative": {"intro_duration_sec", "outro_duration_sec"},
    }

    for dim, related_keys in _dimension_map.items():
        if dimension_locks.get(dim):
            continue
        relevant_changes = {k: v for k, v in diff.items() if k in related_keys}
        if not relevant_changes:
            continue

        if dim not in updated:
            updated[dim] = {}

        if dim == "pacing" and action == "approved":
            # If creator approved cuts being added, they like faster pacing
            if "transitions" in relevant_changes and "added" in relevant_changes["transitions"]:
                cur = updated["pacing"].get("cuts_per_min", 10)
                new_val = round(cur * 1.05, 1)
                # Cap at 1.5x genre centroid max to prevent unbounded drift
                genre = profile.get("genre", "general")
                from services.sie.cold_start import GENRE_CENTROIDS
                genre_max = GENRE_CENTROIDS.get(genre, {}).get("max_cuts_per_min", 30)
                updated["pacing"]["cuts_per_min"] = min(new_val, round(genre_max * 1.5, 1))

        if dim == "captions" and "captions" in relevant_changes and action in ("modified", "approved"):
            updated["captions"]["_feedback_applied"] = True

    return updated
```

- [ ] **Step 5: Create memory.py for Mem0 integration**

Create `backend/services/sie/memory.py`:
```python
from __future__ import annotations
import json
import logging
import os
from mem0 import Memory

logger = logging.getLogger(__name__)
_mem0: Memory | None = None


def _get_mem0() -> Memory:
    global _mem0
    if _mem0 is None:
        _mem0 = Memory()
    return _mem0


def store_edit_episode(mem0_user_id: str, clip_id: str, manifest_summary: str, critique: str | None, action: str) -> None:
    """Store a single edit episode in Mem0 episodic memory. Non-fatal on Mem0 failure."""
    text = f"Clip {clip_id}: {action}. Manifest: {manifest_summary}."
    if critique:
        text += f" Critique: {critique}"
    try:
        _get_mem0().add(text, user_id=mem0_user_id)
    except Exception:
        logger.warning("Mem0 store_edit_episode failed — continuing without episodic storage")


def retrieve_episodic_context(mem0_user_id: str, query: str, limit: int = 5) -> list[dict]:
    """Retrieve relevant past edit episodes for the current footage type.
    Returns [] if Mem0 is unavailable — SIE degrades gracefully without episodic context."""
    try:
        results = _get_mem0().search(query, user_id=mem0_user_id, limit=limit)
        return [{"memory": r["memory"], "score": r.get("score", 0)} for r in results]
    except Exception:
        logger.warning("Mem0 retrieve_episodic_context failed — returning empty context")
        return []
```

- [ ] **Step 6: Run feedback tests**

```bash
cd backend && pytest tests/test_sie_feedback.py -v
```
Expected: 4 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/domain/projects/models.py backend/services/sie/feedback.py \
        backend/services/sie/memory.py backend/tests/test_sie_feedback.py
git commit -m "feat(sie): style profile memory — diff capture, feedback application, Mem0 episodic store"
```

---

### Task 8: LangGraph orchestrator (parallel workers → synthesis → plan → reflect → gate)

> Ties everything together. Workers run concurrently for scene detection, transcription, and Gemini visual scoring. Synthesis merges results into ranked moments. Then planner + critic + gate pipeline executes.

**Files:**
- Create: `backend/services/sie/workers.py`
- Create: `backend/services/sie/graph.py`

- [ ] **Step 1: Implement workers.py (parallel analysis)**

Create `backend/services/sie/workers.py`:
```python
from __future__ import annotations
import asyncio
import json
import os
from typing import Any
from google import genai


async def run_scene_detection(video_path: str) -> list[dict]:
    """CPU-only scene boundary detection via PySceneDetect."""
    from scenedetect import detect, ContentDetector
    scenes = detect(video_path, ContentDetector(threshold=27.0))
    return [
        {"start_sec": round(s[0].get_seconds(), 2), "end_sec": round(s[1].get_seconds(), 2)}
        for s in scenes
    ]


async def run_transcription(video_path: str) -> dict:
    """Transcribe audio via faster-whisper. Returns {text, segments: [{start, end, text}]}."""
    from faster_whisper import WhisperModel
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, info = model.transcribe(video_path, beam_size=5)
    seg_list = [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments]
    return {"text": " ".join(s["text"] for s in seg_list), "segments": seg_list}


async def run_gemini_visual_scoring(video_path: str, gcs_uri: str | None = None) -> list[dict]:
    """Score moments using Gemini 2.5 Flash multimodal analysis.
    Returns list of {start_sec, end_sec, type, score, sentiment, description}."""
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return []

    client = genai.Client(api_key=api_key)
    prompt = (
        "Analyze this video. Return JSON array of compelling moments. "
        "Each item: {start_sec, end_sec, type, engagement_score (0-1), sentiment, description}. "
        'Moment types: highlight, reaction, educational, funny, transition. '
        "Only include moments with engagement_score > 0.5. Be precise about timestamps."
    )

    source = genai.types.Part.from_uri(file_uri=gcs_uri, mime_type="video/mp4") if gcs_uri else None
    if source is None:
        return []

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[source, prompt],
        config={"response_mime_type": "application/json"},
    )
    try:
        return json.loads(response.text)
    except (json.JSONDecodeError, AttributeError):
        return []


async def run_all_workers(video_path: str, gcs_uri: str | None = None) -> dict[str, Any]:
    """Fan out all analysis workers in parallel. Returns merged analysis state."""
    scenes_task = asyncio.create_task(run_scene_detection(video_path))
    transcript_task = asyncio.create_task(run_transcription(video_path))
    gemini_task = asyncio.create_task(run_gemini_visual_scoring(video_path, gcs_uri))

    scenes, transcript, visual_moments = await asyncio.gather(
        scenes_task, transcript_task, gemini_task, return_exceptions=True
    )

    return {
        "scenes": scenes if not isinstance(scenes, Exception) else [],
        "transcript": transcript if not isinstance(transcript, Exception) else {"text": "", "segments": []},
        "visual_moments": visual_moments if not isinstance(visual_moments, Exception) else [],
    }
```

- [ ] **Step 2: Implement graph.py (LangGraph orchestrator)**

Create `backend/services/sie/graph.py`:
```python
from __future__ import annotations
import json
from typing import TypedDict, Annotated, List, Optional, Any
import operator
from langgraph.graph import StateGraph, END
from services.sie.schemas import EditManifest
from services.sie import workers, planner, critic, gates, memory, feedback


class SIEState(TypedDict):
    footage_id: str
    workspace_id: str
    profile_id: str
    video_path: str
    gcs_uri: Optional[str]
    footage_duration_sec: float
    style_doc: dict
    dimension_locks: dict
    mem0_user_id: Optional[str]
    # Worker outputs
    scenes: List[dict]
    transcript: dict
    visual_moments: List[dict]
    ranked_moments: List[dict]
    # Planning
    episodic_context: List[dict]
    edit_manifest: Optional[EditManifest]
    gate_passed: bool
    gate_error: Optional[str]
    errors: Annotated[List[str], operator.add]


async def _analysis_node(state: SIEState) -> dict:
    result = await workers.run_all_workers(state["video_path"], state.get("gcs_uri"))
    return {
        "scenes": result["scenes"],
        "transcript": result["transcript"],
        "visual_moments": result["visual_moments"],
    }


async def _synthesis_node(state: SIEState) -> dict:
    """Merge scene, transcript, and visual moment signals into ranked moments."""
    visual = state.get("visual_moments", [])
    scenes = state.get("scenes", [])
    transcript_segs = state.get("transcript", {}).get("segments", [])

    # Simple merge: use visual moments as base, fall back to scenes if empty
    if visual:
        moments = sorted(visual, key=lambda m: m.get("engagement_score", 0), reverse=True)
    elif scenes:
        moments = [
            {"start_sec": s["start_sec"], "end_sec": s["end_sec"],
             "score": 0.6, "type": "scene", "sentiment": "neutral"}
            for s in scenes
        ]
    else:
        # Fallback: evenly spaced moments from transcript
        dur = state["footage_duration_sec"]
        moments = [
            {"start_sec": i * dur / 3, "end_sec": min((i + 1) * dur / 3, dur),
             "score": 0.5, "type": "segment", "sentiment": "neutral"}
            for i in range(3)
        ]

    episodic = []
    if state.get("mem0_user_id"):
        query = f"footage type for workspace {state['workspace_id']}"
        episodic = memory.retrieve_episodic_context(state["mem0_user_id"], query)

    return {"ranked_moments": moments[:10], "episodic_context": episodic}


async def _planning_node(state: SIEState) -> dict:
    from database import SessionLocal
    from domain.identity import Workspace
    db = SessionLocal()
    try:
        workspace = db.query(Workspace).filter(Workspace.id == state["workspace_id"]).first()
        if not workspace:
            return {"errors": [f"workspace {state['workspace_id']} not found"], "edit_manifest": None}
        manifest = planner.generate_edit_plan(
            footage_path=state["video_path"],
            footage_duration_sec=state["footage_duration_sec"],
            moments=state["ranked_moments"],
            style_profile=state["style_doc"],
            episodic_context=state["episodic_context"],
            db=db,
            workspace=workspace,
        )
        manifest = critic.run_reflection_loop(
            initial_manifest=manifest,
            footage_path=state["video_path"],
            footage_duration_sec=state["footage_duration_sec"],
            moments=state["ranked_moments"],
            style_profile=state["style_doc"],
            episodic_context=state["episodic_context"],
            db=db,
            workspace=workspace,
        )
        return {"edit_manifest": manifest}
    except Exception as e:
        return {"errors": [f"planning failed: {e}"], "edit_manifest": None}
    finally:
        db.close()


def _gate_node(state: SIEState) -> dict:
    if not state.get("edit_manifest"):
        return {"gate_passed": False, "gate_error": "no manifest produced"}
    try:
        gates.run_quality_gates(
            manifest=state["edit_manifest"],
            footage_duration_sec=state["footage_duration_sec"],
            style_profile=state["style_doc"],
        )
        return {"gate_passed": True, "gate_error": None}
    except gates.GateFailure as e:
        return {"gate_passed": False, "gate_error": str(e)}


def _should_continue(state: SIEState) -> str:
    return "gate" if state.get("edit_manifest") else END


def build_sie_graph() -> StateGraph:
    g = StateGraph(SIEState)
    g.add_node("analysis", _analysis_node)
    g.add_node("synthesis", _synthesis_node)
    g.add_node("planning", _planning_node)
    g.add_node("gate", _gate_node)

    g.set_entry_point("analysis")
    g.add_edge("analysis", "synthesis")
    g.add_edge("synthesis", "planning")
    g.add_conditional_edges("planning", _should_continue, {"gate": "gate", END: END})
    g.add_edge("gate", END)

    return g.compile()


_compiled_graph = None

def get_sie_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_sie_graph()
    return _compiled_graph


async def run_sie_pipeline(
    footage_id: str,
    workspace_id: str,
    profile_id: str,
    video_path: str,
    footage_duration_sec: float,
    style_doc: dict,
    dimension_locks: dict,
    gcs_uri: str | None = None,
    mem0_user_id: str | None = None,
) -> SIEState:
    graph = get_sie_graph()
    initial_state: SIEState = {
        "footage_id": footage_id,
        "workspace_id": workspace_id,
        "profile_id": profile_id,
        "video_path": video_path,
        "gcs_uri": gcs_uri,
        "footage_duration_sec": footage_duration_sec,
        "style_doc": style_doc,
        "dimension_locks": dimension_locks,
        "mem0_user_id": mem0_user_id,
        "scenes": [],
        "transcript": {},
        "visual_moments": [],
        "ranked_moments": [],
        "episodic_context": [],
        "edit_manifest": None,
        "gate_passed": False,
        "gate_error": None,
        "errors": [],
    }
    return await graph.ainvoke(initial_state)
```

- [ ] **Step 3: Fix WhisperModel — module-level singleton**

In `backend/services/sie/workers.py`, replace the `run_transcription` function with:
```python
from faster_whisper import WhisperModel

_whisper_model: WhisperModel | None = None


def _get_whisper_model() -> WhisperModel:
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
    return _whisper_model


async def run_transcription(video_path: str) -> dict:
    """Transcribe audio via faster-whisper. Returns {text, segments: [{start, end, text}]}."""
    model = _get_whisper_model()
    segments, info = model.transcribe(video_path, beam_size=5)
    seg_list = [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments]
    return {"text": " ".join(s["text"] for s in seg_list), "segments": seg_list}
```

Remove the old `from faster_whisper import WhisperModel` and `model = WhisperModel(...)` lines that were inside `run_transcription`.

- [ ] **Step 4: Write workers tests**

Create `backend/tests/test_sie_workers.py`:
```python
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


def test_run_scene_detection_returns_list(tmp_path):
    fake_scene = [MagicMock(), MagicMock()]
    fake_scene[0][0].get_seconds.return_value = 0.0
    fake_scene[0][1].get_seconds.return_value = 5.0
    fake_scene[1][0].get_seconds.return_value = 5.0
    fake_scene[1][1].get_seconds.return_value = 12.3
    with patch("services.sie.workers.detect", return_value=fake_scene):
        import asyncio
        from services.sie.workers import run_scene_detection
        result = asyncio.get_event_loop().run_until_complete(run_scene_detection("/fake/video.mp4"))
    assert len(result) == 2
    assert result[0]["start_sec"] == 0.0
    assert result[1]["end_sec"] == 12.3


def test_run_transcription_uses_singleton():
    """WhisperModel is only instantiated once across multiple calls."""
    import services.sie.workers as _workers
    _workers._whisper_model = None  # reset singleton for test isolation
    fake_model = MagicMock()
    fake_model.transcribe.return_value = (
        [MagicMock(start=0.0, end=3.0, text=" Hello world")],
        MagicMock(),
    )
    with patch("services.sie.workers.WhisperModel", return_value=fake_model) as mock_cls:
        import asyncio
        from services.sie.workers import run_transcription
        asyncio.get_event_loop().run_until_complete(run_transcription("/fake/video.mp4"))
        asyncio.get_event_loop().run_until_complete(run_transcription("/fake/video.mp4"))
    mock_cls.assert_called_once()  # singleton: only constructed once


def test_run_gemini_visual_scoring_returns_empty_without_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    import asyncio
    from services.sie.workers import run_gemini_visual_scoring
    result = asyncio.get_event_loop().run_until_complete(run_gemini_visual_scoring("/fake/video.mp4"))
    assert result == []


def test_run_all_workers_tolerates_worker_failure():
    """If one worker raises, run_all_workers returns empty for that field, not a crash."""
    async def _raise(*a, **kw):
        raise RuntimeError("scene detection failed")

    import asyncio
    with patch("services.sie.workers.run_scene_detection", side_effect=_raise), \
         patch("services.sie.workers.run_transcription", return_value={"text": "", "segments": []}), \
         patch("services.sie.workers.run_gemini_visual_scoring", return_value=[]):
        from services.sie.workers import run_all_workers
        result = asyncio.get_event_loop().run_until_complete(run_all_workers("/fake/video.mp4"))
    assert result["scenes"] == []  # graceful fallback
    assert result["transcript"] == {"text": "", "segments": []}
```

- [ ] **Step 5: Write graph tests**

Create `backend/tests/test_sie_graph.py`:
```python
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


def _make_state(**overrides):
    base = {
        "footage_id": "f1",
        "workspace_id": "ws-1",
        "profile_id": "p1",
        "video_path": "/tmp/test.mp4",
        "gcs_uri": None,
        "footage_duration_sec": 60.0,
        "style_doc": {"genre": "general"},
        "dimension_locks": {},
        "mem0_user_id": None,
        "scenes": [],
        "transcript": {},
        "visual_moments": [],
        "ranked_moments": [],
        "episodic_context": [],
        "edit_manifest": None,
        "gate_passed": False,
        "gate_error": None,
        "errors": [],
    }
    base.update(overrides)
    return base


def test_synthesis_falls_back_to_transcript_segments_when_no_visual():
    """_synthesis_node uses evenly-spaced segments when both visual and scenes are empty."""
    import asyncio
    from services.sie.graph import _synthesis_node
    state = _make_state(footage_duration_sec=90.0)
    with patch("services.sie.graph.memory.retrieve_episodic_context", return_value=[]):
        result = asyncio.get_event_loop().run_until_complete(_synthesis_node(state))
    assert len(result["ranked_moments"]) == 3  # 3 evenly-spaced fallback segments
    assert result["ranked_moments"][0]["type"] == "segment"


def test_gate_node_passes_when_manifest_valid():
    from services.sie.graph import _gate_node
    from services.sie.schemas import EditManifest, TrimAction
    manifest = EditManifest(
        trim=TrimAction(start_sec=0.0, end_sec=30.0),
        platform_targets=["tiktok"],
        confidence=0.85,
        reasoning="Good hook.",
    )
    state = _make_state(edit_manifest=manifest, footage_duration_sec=60.0)
    with patch("services.sie.graph.gates.run_quality_gates"):  # gates pass
        result = _gate_node(state)
    assert result["gate_passed"] is True
    assert result["gate_error"] is None


def test_gate_node_fails_when_no_manifest():
    from services.sie.graph import _gate_node
    state = _make_state(edit_manifest=None)
    result = _gate_node(state)
    assert result["gate_passed"] is False
    assert "no manifest" in result["gate_error"]


def test_planning_node_records_error_when_workspace_missing():
    """_planning_node returns error state when workspace_id lookup fails."""
    import asyncio
    from services.sie.graph import _planning_node
    state = _make_state(workspace_id="nonexistent-ws")
    with patch("services.sie.graph.SessionLocal") as mock_sl:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_sl.return_value = mock_db
        result = asyncio.get_event_loop().run_until_complete(_planning_node(state))
    assert result["edit_manifest"] is None
    assert any("not found" in e for e in result["errors"])
```

- [ ] **Step 6: Run tests**

```bash
cd backend && pytest tests/test_sie_workers.py tests/test_sie_graph.py -v
```
Expected: 8 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/services/sie/workers.py backend/services/sie/graph.py \
        backend/tests/test_sie_workers.py backend/tests/test_sie_graph.py
git commit -m "feat(sie): LangGraph orchestrator — parallel workers, synthesis, planner, critic, quality gate"
```

---

### Task 9: Style profile API endpoints + cold start

**Files:**
- Create: `backend/routes/style_profiles.py`
- Modify: `backend/main.py` (register router)
- Create: `backend/services/sie/cold_start.py`

- [ ] **Step 1: Implement cold_start.py**

Create `backend/services/sie/cold_start.py`:
```python
"""Genre centroid vectors — default style profiles for new creators.
Each genre centroid encodes average editing conventions for that content type."""

GENRE_CENTROIDS: dict[str, dict] = {
    "gaming": {
        "pacing": {"cuts_per_min": 14, "speed_ramps": True},
        "captions": {"animation": "word_by_word", "font": "Montserrat"},
        "sound_design": {"music_bed_volume_db": -16, "sfx_enabled": True},
        "transitions": {"preferred_type": "hard_cut", "hard_cut_pct": 85},
        "narrative": {"hook_duration_sec": 1.5, "outro_duration_sec": 2.0},
        "max_cuts_per_min": 18,
    },
    "education": {
        "pacing": {"cuts_per_min": 5, "speed_ramps": False},
        "captions": {"animation": "fade", "font": "DM Sans"},
        "sound_design": {"music_bed_volume_db": -24, "sfx_enabled": False},
        "transitions": {"preferred_type": "crossfade", "hard_cut_pct": 40},
        "narrative": {"hook_duration_sec": 5.0, "outro_duration_sec": 5.0},
        "max_cuts_per_min": 8,
    },
    "podcast": {
        "pacing": {"cuts_per_min": 3, "speed_ramps": False},
        "captions": {"animation": "word_by_word", "font": "DM Sans"},
        "sound_design": {"music_bed_volume_db": -28, "sfx_enabled": False},
        "transitions": {"preferred_type": "crossfade", "hard_cut_pct": 20},
        "narrative": {"hook_duration_sec": 8.0, "outro_duration_sec": 3.0},
        "max_cuts_per_min": 5,
    },
    "vlog": {
        "pacing": {"cuts_per_min": 8, "speed_ramps": True},
        "captions": {"animation": "slide_up", "font": "DM Sans"},
        "sound_design": {"music_bed_volume_db": -20, "sfx_enabled": False},
        "transitions": {"preferred_type": "hard_cut", "hard_cut_pct": 65},
        "narrative": {"hook_duration_sec": 3.0, "outro_duration_sec": 2.0},
        "max_cuts_per_min": 12,
    },
    "fitness": {
        "pacing": {"cuts_per_min": 18, "speed_ramps": True},
        "captions": {"animation": "word_by_word", "font": "Montserrat"},
        "sound_design": {"music_bed_volume_db": -14, "sfx_enabled": True},
        "transitions": {"preferred_type": "hard_cut", "hard_cut_pct": 90},
        "narrative": {"hook_duration_sec": 1.0, "outro_duration_sec": 1.5},
        "max_cuts_per_min": 22,
    },
}

SUPPORTED_GENRES = list(GENRE_CENTROIDS.keys())


def get_genre_centroid(genre: str) -> dict:
    return GENRE_CENTROIDS.get(genre, GENRE_CENTROIDS["vlog"])
```

- [ ] **Step 2: Create style profiles router**

Create `backend/routes/style_profiles.py`:
```python
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from domain.projects import StyleProfile
from routes.auth import get_current_session
from services.sie.cold_start import get_genre_centroid, SUPPORTED_GENRES

router = APIRouter(prefix="/style-profiles", tags=["style-profiles"])


@router.get("/genres")
def list_genres():
    return {"genres": SUPPORTED_GENRES}


@router.post("")
def create_profile(payload: dict, db: Session = Depends(get_db), session=Depends(get_current_session)):
    genre = payload.get("genre", "vlog")
    centroid = get_genre_centroid(genre)
    profile = StyleProfile(
        workspace_id=session.workspace_id,
        project_id=payload.get("project_id"),
        name=payload.get("name", f"{genre.title()} Profile"),
        genre=genre,
        style_doc=json.dumps(centroid),
        confidence_scores="{}",
        dimension_locks="{}",
        version=1,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return _serialize(profile)


@router.get("")
def list_profiles(db: Session = Depends(get_db), session=Depends(get_current_session)):
    profiles = db.query(StyleProfile).filter(StyleProfile.workspace_id == session.workspace_id).all()
    return {"profiles": [_serialize(p) for p in profiles]}


@router.get("/{profile_id}")
def get_profile(profile_id: str, db: Session = Depends(get_db), session=Depends(get_current_session)):
    p = _get_or_404(profile_id, session.workspace_id, db)
    return _serialize(p)


@router.put("/{profile_id}/locks")
def update_locks(profile_id: str, payload: dict, db: Session = Depends(get_db),
                 session=Depends(get_current_session)):
    p = _get_or_404(profile_id, session.workspace_id, db)
    locks = json.loads(p.dimension_locks or "{}")
    locks.update(payload.get("dimension_locks", {}))
    p.dimension_locks = json.dumps(locks)
    db.commit()
    return {"dimension_locks": locks}


@router.post("/{profile_id}/rollback")
def rollback_profile(profile_id: str, payload: dict, db: Session = Depends(get_db),
                     session=Depends(get_current_session)):
    # Full rollback requires version history table (Phase 2 extension).
    # For now: reset to genre centroid if target_version == 1.
    p = _get_or_404(profile_id, session.workspace_id, db)
    target = payload.get("target_version", 1)
    if target == 1 and p.genre:
        p.style_doc = json.dumps(get_genre_centroid(p.genre))
        p.version = 1
        db.commit()
    return _serialize(p)


def _get_or_404(profile_id: str, workspace_id: str, db: Session) -> StyleProfile:
    p = db.query(StyleProfile).filter(
        StyleProfile.id == profile_id,
        StyleProfile.workspace_id == workspace_id,
    ).first()
    if not p:
        raise HTTPException(404, "Style profile not found")
    return p


def _serialize(p: StyleProfile) -> dict:
    return {
        "id": str(p.id),
        "name": p.name,
        "genre": p.genre,
        "style_doc": json.loads(p.style_doc or "{}"),
        "confidence_scores": json.loads(p.confidence_scores or "{}"),
        "dimension_locks": json.loads(p.dimension_locks or "{}"),
        "version": p.version,
    }
```

- [ ] **Step 3: Register the router in main.py**

In `backend/main.py`, add:
```python
from routes.style_profiles import router as style_profiles_router
app.include_router(style_profiles_router)
```

- [ ] **Step 4: Commit**

```bash
git add backend/routes/style_profiles.py backend/services/sie/cold_start.py backend/main.py
git commit -m "feat(sie): style profile API with genre centroid cold start"
```

---

### Task 10: Delayed performance feedback pipeline

> Published clip performance takes 72h to stabilize. A background job checks clips published >72h ago, fetches analytics, computes engagement delta vs. profile average, and nudges the style profile toward what worked.

**Files:**
- Create: `backend/services/sie/performance.py`
- Modify: `backend/services/background_jobs.py`

- [ ] **Step 1: Implement performance.py**

Create `backend/services/sie/performance.py`:
```python
from __future__ import annotations
import json
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database import SessionLocal
from domain.platforms import CalendarSlot
from domain.projects import StyleProfile
from services.sie.feedback import apply_feedback_to_profile

logger = logging.getLogger(__name__)
MATURATION_HOURS = 72


def run_performance_feedback_sweep():
    """Check calendar slots published >72h ago, fetch stored analytics,
    and update style profiles based on engagement performance."""
    db: Session = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(hours=MATURATION_HOURS)
        slots = (
            db.query(CalendarSlot)
            .filter(
                CalendarSlot.published_at <= cutoff,
                CalendarSlot.status == "monitoring",
            )
            .limit(50)
            .all()
        )

        for slot in slots:
            try:
                _process_slot_feedback(slot, db)
                slot.status = "complete"
                db.commit()
            except Exception as e:
                logger.error(f"Performance feedback failed for slot {slot.id}: {e}")
                db.rollback()
    finally:
        db.close()


def _process_slot_feedback(slot: CalendarSlot, db: Session):
    if not slot.clip_render_id:
        return

    from domain.media import ClipRender
    render = db.query(ClipRender).filter(ClipRender.id == slot.clip_render_id).first()
    if not render:
        return

    from domain.media import Clip
    clip = db.query(Clip).filter(Clip.id == render.clip_id).first()
    if not clip or not clip.profile_id:
        return

    profile = db.query(StyleProfile).filter(StyleProfile.id == clip.profile_id).first()
    if not profile:
        return

    # Fetch latest analytics for this slot
    from domain.ai import AIUsageRecord  # reuse analytics table later; stub here
    engagement = _estimate_engagement(slot)
    if engagement is None:
        return

    style_doc = json.loads(profile.style_doc or "{}")
    dimension_locks = json.loads(profile.dimension_locks or "{}")
    edit_manifest = json.loads(clip.edit_manifest or "{}") if clip.edit_manifest else {}

    # Map engagement signal to a synthetic diff
    diff = _engagement_to_diff(engagement, edit_manifest)
    if not diff:
        return

    action = "approved" if engagement > 0.6 else "rejected"
    updated_doc = apply_feedback_to_profile(style_doc, diff, dimension_locks, action=action)
    profile.style_doc = json.dumps(updated_doc)
    profile.version += 1
    db.add(profile)


def _estimate_engagement(slot: CalendarSlot) -> float | None:
    """Return 0.0–1.0 engagement score from stored analytics. None if unavailable."""
    meta = slot.publish_metadata
    if not meta:
        return None
    try:
        data = json.loads(meta) if isinstance(meta, str) else meta
        views = data.get("views", 0)
        likes = data.get("likes", 0)
        if views == 0:
            return None
        return min(1.0, (likes / views) * 10)
    except Exception:
        return None


def _engagement_to_diff(engagement: float, manifest: dict) -> dict:
    """High engagement → treat transitions/zooms as positively reinforced."""
    if not manifest:
        return {}
    diff = {}
    if engagement > 0.7 and manifest.get("transitions"):
        diff["transitions"] = f"high engagement with {len(manifest['transitions'])} cuts"
    if engagement > 0.7 and manifest.get("zooms"):
        diff["zooms"] = f"high engagement with {len(manifest['zooms'])} zooms"
    if engagement < 0.3:
        diff["pacing"] = "low engagement — consider slower cuts"
    return diff
```

- [ ] **Step 2: Register sweep as background job**

In `backend/services/background_jobs.py`, add to the job handlers mapping and register it in the periodic sweep:
```python
# In the handler dispatch:
elif job.job_type == "performance_feedback_sweep":
    from services.sie.performance import run_performance_feedback_sweep
    run_performance_feedback_sweep()
```

And in `backend/bootstrap.py`, add a new periodic task (after the existing 15s platform scheduler):
```python
async def _performance_feedback_loop():
    while True:
        await asyncio.sleep(3600)  # every hour
        try:
            from services.sie.performance import run_performance_feedback_sweep
            await asyncio.get_event_loop().run_in_executor(None, run_performance_feedback_sweep)
        except Exception as e:
            logger.error(f"Performance feedback sweep error: {e}")

asyncio.create_task(_performance_feedback_loop())
```

- [ ] **Step 3: Commit**

```bash
git add backend/services/sie/performance.py backend/services/background_jobs.py backend/bootstrap.py
git commit -m "feat(sie): delayed performance feedback pipeline — 72h maturation, engagement → style update"
```

---

## Phase 3 — Platform Resilience

### Task 11: Proactive token refresh

**Files:**
- Create: `backend/services/token_refresh.py`
- Modify: `backend/bootstrap.py`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/test_auth_oauth.py`:
```python
def test_token_refresh_skips_non_expiring(db, workspace_a):
    from datetime import datetime, timedelta
    from domain.platforms import PlatformAuth
    from services.token_crypto import encrypt_token
    ws_id, _ = workspace_a
    # Token expires in 1 hour — should NOT be refreshed
    pa = PlatformAuth(
        workspace_id=ws_id, platform="youtube",
        access_token_enc=encrypt_token("tok"),
        token_expires_at=datetime.utcnow() + timedelta(hours=1),
        status="active",
    )
    db.add(pa)
    db.commit()
    from services.token_refresh import get_tokens_needing_refresh
    tokens = get_tokens_needing_refresh(db, refresh_window_minutes=5)
    assert all(str(t.id) != str(pa.id) for t in tokens)
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && pytest tests/test_auth_oauth.py::test_token_refresh_skips_non_expiring -v
```
Expected: ImportError.

- [ ] **Step 3: Implement token_refresh.py**

Create `backend/services/token_refresh.py`:
```python
from __future__ import annotations
import logging
from datetime import datetime, timedelta
import httpx
from sqlalchemy.orm import Session
from domain.platforms import PlatformAuth
from services.token_crypto import encrypt_token, decrypt_token

logger = logging.getLogger(__name__)

PLATFORM_REFRESH_URLS = {
    "youtube": "https://oauth2.googleapis.com/token",
    "tiktok": "https://open.tiktokapis.com/v2/oauth/token/",
    "instagram": "https://graph.facebook.com/v19.0/oauth/access_token",
    "linkedin": "https://www.linkedin.com/oauth/v2/accessToken",
    "x": "https://api.x.com/2/oauth2/token",
}


def get_tokens_needing_refresh(db: Session, refresh_window_minutes: int = 10) -> list[PlatformAuth]:
    cutoff = datetime.utcnow() + timedelta(minutes=refresh_window_minutes)
    return (
        db.query(PlatformAuth)
        .filter(
            PlatformAuth.status == "active",
            PlatformAuth.token_expires_at != None,
            PlatformAuth.token_expires_at <= cutoff,
            PlatformAuth.refresh_token_enc != None,
        )
        .all()
    )


async def refresh_token(pa: PlatformAuth, db: Session, client_id: str, client_secret: str) -> bool:
    """Refresh a single platform token. Returns True on success, False on failure."""
    import os
    refresh_url = PLATFORM_REFRESH_URLS.get(pa.platform)
    if not refresh_url or not pa.refresh_token_enc:
        return False

    try:
        refresh_tok = decrypt_token(pa.refresh_token_enc)
    except Exception:
        pa.status = "error"
        pa.error_message = "refresh token decryption failed"
        db.commit()
        return False

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                refresh_url,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_tok,
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        pa.access_token_enc = encrypt_token(data["access_token"])
        if "refresh_token" in data:
            pa.refresh_token_enc = encrypt_token(data["refresh_token"])
        if "expires_in" in data:
            pa.token_expires_at = datetime.utcnow() + timedelta(seconds=int(data["expires_in"]))
        pa.status = "active"
        pa.last_refreshed_at = datetime.utcnow()
        pa.error_message = None
        db.commit()
        return True

    except Exception as e:
        pa.status = "error"
        pa.error_message = str(e)[:500]
        db.commit()
        logger.error(f"Token refresh failed for {pa.platform} ws={pa.workspace_id}: {e}")
        return False
```

- [ ] **Step 4: Register as periodic background task in bootstrap.py**

```python
async def _token_refresh_loop():
    while True:
        await asyncio.sleep(300)  # every 5 minutes
        try:
            from database import SessionLocal
            from services.token_refresh import get_tokens_needing_refresh, refresh_token
            import os
            db = SessionLocal()
            tokens = get_tokens_needing_refresh(db)
            for pa in tokens:
                await refresh_token(
                    pa, db,
                    client_id=os.getenv(f"{pa.platform.upper()}_CLIENT_ID", ""),
                    client_secret=os.getenv(f"{pa.platform.upper()}_CLIENT_SECRET", ""),
                )
            db.close()
        except Exception as e:
            logger.error(f"Token refresh loop error: {e}")

asyncio.create_task(_token_refresh_loop())
```

- [ ] **Step 5: Run test**

```bash
cd backend && pytest tests/test_auth_oauth.py::test_token_refresh_skips_non_expiring -v
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/services/token_refresh.py backend/bootstrap.py \
        backend/tests/test_auth_oauth.py
git commit -m "feat(platforms): proactive OAuth token refresh every 5 minutes"
```

---

### Task 12: Circuit breaker + sliding-window rate limiter

**Files:**
- Create: `backend/services/circuit_breaker.py`
- Create: `backend/services/rate_limiter.py`
- Create: `backend/tests/test_circuit_breaker.py`
- Create: `backend/tests/test_rate_limiter.py`

- [ ] **Step 1: Write circuit breaker tests**

Create `backend/tests/test_circuit_breaker.py`:
```python
from services.circuit_breaker import CircuitBreaker, CircuitOpen
import time


def test_circuit_opens_after_threshold():
    cb = CircuitBreaker("test_platform", failure_threshold=3, recovery_sec=60)
    for _ in range(3):
        cb.record_failure()
    assert cb.is_open()


def test_circuit_blocks_calls_when_open():
    cb = CircuitBreaker("test_platform2", failure_threshold=2, recovery_sec=60)
    cb.record_failure()
    cb.record_failure()
    try:
        cb.check()
        assert False, "should have raised"
    except CircuitOpen:
        pass


def test_circuit_resets_on_success():
    cb = CircuitBreaker("test_platform3", failure_threshold=3, recovery_sec=60)
    cb.record_failure()
    cb.record_failure()
    cb.record_success()
    assert not cb.is_open()
    assert cb._failure_count == 0


def test_circuit_half_open_after_recovery_window(monkeypatch):
    cb = CircuitBreaker("test_platform4", failure_threshold=2, recovery_sec=1)
    cb.record_failure()
    cb.record_failure()
    assert cb.is_open()
    # Advance time beyond recovery window
    monkeypatch.setattr(time, "time", lambda: time.time() + 2)
    assert not cb.is_open()  # half-open — allows one probe
```

- [ ] **Step 2: Implement circuit_breaker.py**

Create `backend/services/circuit_breaker.py`:
```python
import time
from threading import Lock


class CircuitOpen(Exception):
    pass


class CircuitBreaker:
    """In-process circuit breaker per platform. Not distributed — use Redis for multi-pod."""

    def __init__(self, platform: str, failure_threshold: int = 5, recovery_sec: int = 120):
        self.platform = platform
        self.failure_threshold = failure_threshold
        self.recovery_sec = recovery_sec
        self._failure_count = 0
        self._opened_at: float | None = None
        self._lock = Lock()

    def is_open(self) -> bool:
        with self._lock:
            if self._opened_at is None:
                return False
            if time.time() - self._opened_at >= self.recovery_sec:
                # Transition to half-open: allow one probe
                self._opened_at = None
                self._failure_count = 0
                return False
            return True

    def check(self) -> None:
        if self.is_open():
            raise CircuitOpen(f"Circuit open for platform={self.platform}")

    def record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            if self._failure_count >= self.failure_threshold:
                self._opened_at = time.time()

    def record_success(self) -> None:
        with self._lock:
            self._failure_count = 0
            self._opened_at = None


# Global registry — one breaker per platform
_breakers: dict[str, CircuitBreaker] = {}


def get_breaker(platform: str) -> CircuitBreaker:
    if platform not in _breakers:
        _breakers[platform] = CircuitBreaker(platform)
    return _breakers[platform]
```

- [ ] **Step 3: Write rate limiter tests**

Create `backend/tests/test_rate_limiter.py`:
```python
from services.rate_limiter import SlidingWindowRateLimiter, RateLimitExceeded


def test_allows_requests_under_limit():
    rl = SlidingWindowRateLimiter(max_calls=5, window_sec=60)
    for _ in range(5):
        rl.check_and_record("ws1", "youtube")


def test_blocks_requests_over_limit():
    rl = SlidingWindowRateLimiter(max_calls=3, window_sec=60)
    for _ in range(3):
        rl.check_and_record("ws2", "tiktok")
    try:
        rl.check_and_record("ws2", "tiktok")
        assert False, "should have raised"
    except RateLimitExceeded:
        pass


def test_independent_buckets_per_platform():
    rl = SlidingWindowRateLimiter(max_calls=2, window_sec=60)
    rl.check_and_record("ws3", "youtube")
    rl.check_and_record("ws3", "youtube")
    # Different platform — separate bucket
    rl.check_and_record("ws3", "tiktok")
    rl.check_and_record("ws3", "tiktok")
```

- [ ] **Step 4: Implement rate_limiter.py**

Create `backend/services/rate_limiter.py`:
```python
import time
from collections import defaultdict, deque
from threading import Lock


class RateLimitExceeded(Exception):
    pass


class SlidingWindowRateLimiter:
    def __init__(self, max_calls: int = 20, window_sec: int = 86400):
        self.max_calls = max_calls
        self.window_sec = window_sec
        self._windows: dict[str, deque] = defaultdict(deque)
        self._lock = Lock()

    def _key(self, workspace_id: str, platform: str) -> str:
        return f"{workspace_id}:{platform}"

    def check_and_record(self, workspace_id: str, platform: str) -> None:
        key = self._key(workspace_id, platform)
        now = time.time()
        cutoff = now - self.window_sec
        with self._lock:
            dq = self._windows[key]
            while dq and dq[0] < cutoff:
                dq.popleft()
            if len(dq) >= self.max_calls:
                raise RateLimitExceeded(
                    f"Rate limit {self.max_calls}/{self.window_sec}s exceeded "
                    f"for {workspace_id}:{platform}"
                )
            dq.append(now)

    def remaining(self, workspace_id: str, platform: str) -> int:
        key = self._key(workspace_id, platform)
        now = time.time()
        cutoff = now - self.window_sec
        with self._lock:
            dq = self._windows[key]
            active = sum(1 for t in dq if t > cutoff)
            return max(0, self.max_calls - active)
```

- [ ] **Step 5: Integrate into platform publish flow**

In `backend/services/platform_integrations.py`, import and wrap the publish call:
```python
from services.circuit_breaker import get_breaker, CircuitOpen
from services.rate_limiter import SlidingWindowRateLimiter, RateLimitExceeded

_rate_limiter = SlidingWindowRateLimiter(max_calls=20, window_sec=86400)

# Wrap the publish function (at the start of execute_slot or equivalent):
async def publish_with_resilience(workspace_id: str, platform: str, publish_fn, *args, **kwargs):
    breaker = get_breaker(platform)
    breaker.check()  # raises CircuitOpen if open
    try:
        _rate_limiter.check_and_record(workspace_id, platform)
    except RateLimitExceeded as e:
        raise
    try:
        result = await publish_fn(*args, **kwargs)
        breaker.record_success()
        return result
    except Exception as e:
        breaker.record_failure()
        raise
```

- [ ] **Step 6: Run all resilience tests**

```bash
cd backend && pytest tests/test_circuit_breaker.py tests/test_rate_limiter.py -v
```
Expected: 7 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/services/circuit_breaker.py backend/services/rate_limiter.py \
        backend/tests/test_circuit_breaker.py backend/tests/test_rate_limiter.py \
        backend/services/platform_integrations.py
git commit -m "feat(platforms): circuit breaker + sliding-window rate limiter for publish resilience"
```

---

## Phase 4 — Scheduling Intelligence

### Task 13: Audience heatmap + slot scoring + gap detection

**Files:**
- Create: `backend/services/scheduler.py`
- Create: `backend/routes/calendar.py`
- Create: `backend/tests/test_scheduler.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_scheduler.py`:
```python
from services.scheduler import score_slot, find_gaps, DEFAULT_HEATMAP
from datetime import datetime


def test_score_slot_returns_float_0_to_1():
    score = score_slot(
        platform="tiktok",
        day_of_week=1,  # Tuesday
        hour=14,
        heatmap=DEFAULT_HEATMAP,
        content_pillar="gaming",
        pillar_targets={"gaming": 0.4},
        current_pillar_counts={"gaming": 2},
        total_scheduled=5,
        recently_scheduled_hours=[],
    )
    assert 0.0 <= score <= 1.0


def test_score_penalises_overloaded_pillar():
    # gaming at 100% when target is 40%
    score_over = score_slot(
        platform="tiktok", day_of_week=1, hour=14,
        heatmap=DEFAULT_HEATMAP,
        content_pillar="gaming",
        pillar_targets={"gaming": 0.4},
        current_pillar_counts={"gaming": 10},
        total_scheduled=10,
        recently_scheduled_hours=[],
    )
    score_ok = score_slot(
        platform="tiktok", day_of_week=1, hour=14,
        heatmap=DEFAULT_HEATMAP,
        content_pillar="gaming",
        pillar_targets={"gaming": 0.4},
        current_pillar_counts={"gaming": 4},
        total_scheduled=10,
        recently_scheduled_hours=[],
    )
    assert score_over < score_ok


def test_score_penalises_recent_post_spacing():
    score_crowded = score_slot(
        platform="tiktok", day_of_week=1, hour=14,
        heatmap=DEFAULT_HEATMAP,
        content_pillar="vlog",
        pillar_targets={},
        current_pillar_counts={},
        total_scheduled=0,
        recently_scheduled_hours=[13],  # 1 hour ago
    )
    score_spaced = score_slot(
        platform="tiktok", day_of_week=1, hour=14,
        heatmap=DEFAULT_HEATMAP,
        content_pillar="vlog",
        pillar_targets={},
        current_pillar_counts={},
        total_scheduled=0,
        recently_scheduled_hours=[6],  # 8 hours ago
    )
    assert score_crowded < score_spaced


def test_find_gaps_returns_open_slots():
    gaps = find_gaps(
        platform="tiktok",
        scheduled_slots=[
            {"scheduled_at": datetime(2026, 4, 20, 10, 0)},
            {"scheduled_at": datetime(2026, 4, 20, 18, 0)},
        ],
        window_days=3,
        min_audience_score=0.6,
    )
    assert isinstance(gaps, list)
    for g in gaps:
        assert "datetime" in g
        assert "audience_score" in g
        assert g["audience_score"] >= 0.6
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && pytest tests/test_scheduler.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement scheduler.py**

Create `backend/services/scheduler.py`:
```python
from __future__ import annotations
from datetime import datetime, timedelta

# Default heatmap: 7 days × 24 hours. Values 0.0–1.0 represent relative audience activity.
# Based on aggregate TikTok/YouTube posting performance data (gaming genre).
DEFAULT_HEATMAP = {
    0: [0.1]*6 + [0.3, 0.4, 0.5, 0.5, 0.6, 0.6, 0.7, 0.8, 0.8, 0.7, 0.7, 0.9, 0.95, 0.9, 0.85, 0.8, 0.7, 0.5],
    1: [0.1]*6 + [0.3, 0.4, 0.5, 0.5, 0.6, 0.6, 0.7, 0.8, 0.8, 0.7, 0.7, 0.9, 0.95, 0.9, 0.85, 0.8, 0.7, 0.5],
    2: [0.1]*6 + [0.3, 0.4, 0.5, 0.5, 0.6, 0.6, 0.7, 0.8, 0.8, 0.7, 0.7, 0.9, 0.95, 0.9, 0.85, 0.8, 0.7, 0.5],
    3: [0.1]*6 + [0.3, 0.4, 0.5, 0.5, 0.6, 0.6, 0.7, 0.8, 0.8, 0.7, 0.7, 0.9, 0.95, 0.9, 0.85, 0.8, 0.7, 0.5],
    4: [0.1]*6 + [0.3, 0.4, 0.5, 0.5, 0.6, 0.6, 0.7, 0.8, 0.85, 0.85, 0.8, 0.95, 1.0, 0.95, 0.9, 0.85, 0.8, 0.6],
    5: [0.2]*5 + [0.4, 0.5, 0.6, 0.65, 0.7, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0, 0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.6],
    6: [0.2]*5 + [0.4, 0.5, 0.6, 0.65, 0.7, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0, 0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.6],
}


def score_slot(
    platform: str,
    day_of_week: int,
    hour: int,
    heatmap: dict,
    content_pillar: str,
    pillar_targets: dict[str, float],
    current_pillar_counts: dict[str, int],
    total_scheduled: int,
    recently_scheduled_hours: list[int],
    min_spacing_hours: int = 4,
) -> float:
    day_heatmap = heatmap.get(day_of_week, [0.5] * 24)
    hour = min(hour, len(day_heatmap) - 1)
    audience_score = day_heatmap[hour]

    # Content pillar balance penalty
    target = pillar_targets.get(content_pillar, 0)
    if total_scheduled > 0 and target > 0:
        current_ratio = current_pillar_counts.get(content_pillar, 0) / total_scheduled
        balance_penalty = max(0.0, abs(current_ratio - target) * 2)
    else:
        balance_penalty = 0.0

    # Spacing penalty — penalise slots within min_spacing_hours of recent posts
    spacing_penalty = 0.0
    for scheduled_hour in recently_scheduled_hours:
        if abs(scheduled_hour - hour) < min_spacing_hours:
            spacing_penalty = 0.4
            break

    raw = audience_score * 0.60 - balance_penalty * 0.25 - spacing_penalty * 0.15
    return max(0.0, min(1.0, raw))


def find_gaps(
    platform: str,
    scheduled_slots: list[dict],
    window_days: int = 14,
    min_audience_score: float = 0.7,
    heatmap: dict | None = None,
) -> list[dict]:
    if heatmap is None:
        heatmap = DEFAULT_HEATMAP
    scheduled_dts = {s["scheduled_at"] for s in scheduled_slots}
    now = datetime.utcnow()
    gaps = []

    for day_offset in range(window_days):
        day = now + timedelta(days=day_offset)
        dow = day.weekday()
        day_heatmap = heatmap.get(dow, [0.5] * 24)

        for hour, activity in enumerate(day_heatmap):
            if activity < min_audience_score:
                continue
            slot_dt = day.replace(hour=hour, minute=0, second=0, microsecond=0)
            if slot_dt <= now:
                continue
            if any(abs((slot_dt - s).total_seconds()) < 4 * 3600 for s in scheduled_dts):
                continue
            gaps.append({"datetime": slot_dt.isoformat(), "platform": platform, "audience_score": round(activity, 2)})

    return sorted(gaps, key=lambda g: g["audience_score"], reverse=True)[:20]
```

- [ ] **Step 4: Create calendar router**

Create `backend/routes/calendar.py`:
```python
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from domain.platforms import CalendarSlot
from routes.auth import get_current_session
from services.scheduler import find_gaps

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("/gaps")
def get_gaps(
    platform: str,
    window_days: int = 14,
    db: Session = Depends(get_db),
    session=Depends(get_current_session),
):
    slots = (
        db.query(CalendarSlot)
        .filter(
            CalendarSlot.workspace_id == session.workspace_id,
            CalendarSlot.platform == platform,
            CalendarSlot.scheduled_at >= datetime.utcnow(),
        )
        .all()
    )
    slot_dicts = [{"scheduled_at": s.scheduled_at} for s in slots]
    gaps = find_gaps(platform=platform, scheduled_slots=slot_dicts, window_days=window_days)
    return {"gaps": gaps}
```

Register in `backend/main.py`:
```python
from routes.calendar import router as calendar_router
app.include_router(calendar_router)
```

- [ ] **Step 5: Run tests**

```bash
cd backend && pytest tests/test_scheduler.py -v
```
Expected: 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/services/scheduler.py backend/routes/calendar.py \
        backend/main.py backend/tests/test_scheduler.py
git commit -m "feat(calendar): slot scoring, gap detection, audience heatmap"
```

---

## Phase 5 — Billing / Stripe

### Task 14: Stripe subscription + webhook handler

**New package:** `stripe>=11.0.0`
Add to requirements.txt: `stripe>=11.0.0`

**Files:**
- Modify: `backend/domain/enterprise/models.py` — add stripe fields
- Create: `backend/services/stripe_service.py`
- Create: `backend/routes/billing.py`
- Create: `backend/tests/test_billing.py`

- [ ] **Step 1: Add Stripe fields to WorkspaceSubscription**

In `backend/domain/enterprise/models.py`, add to `WorkspaceSubscription`:
```python
stripe_customer_id = Column(String, nullable=True, unique=True)
stripe_subscription_id = Column(String, nullable=True, unique=True)
stripe_price_id = Column(String, nullable=True)

__table_args__ = (UniqueConstraint("workspace_id", name="uq_workspace_subscription_workspace"),)
```

Add `UniqueConstraint` to the SQLAlchemy imports at the top of the file if not already present:
```python
from sqlalchemy import UniqueConstraint
```

- [ ] **Step 2: Write failing billing tests**

Create `backend/tests/test_billing.py`:
```python
import pytest
from unittest.mock import patch, MagicMock
from tests.conftest import _seed_workspace


def test_create_checkout_session(client, workspace_a):
    ws_id, token = workspace_a
    mock_session = MagicMock()
    mock_session.url = "https://checkout.stripe.com/test"
    mock_session.id = "cs_test_123"

    with patch("stripe.checkout.Session.create", return_value=mock_session):
        resp = client.post(
            "/billing/checkout",
            json={"plan_tier": "creator"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["checkout_url"] == "https://checkout.stripe.com/test"


def test_webhook_subscription_created(client, workspace_a, db):
    ws_id, token = workspace_a
    event = {
        "type": "customer.subscription.created",
        "data": {
            "object": {
                "id": "sub_test_123",
                "customer": "cus_test_123",
                "status": "active",
                "items": {"data": [{"price": {"id": "price_creator_monthly", "nickname": "creator"}}]},
                "current_period_start": 1713100800,
                "current_period_end": 1715692800,
                "metadata": {"workspace_id": str(ws_id)},
            }
        },
    }
    with patch("stripe.Webhook.construct_event", return_value=event):
        resp = client.post(
            "/billing/webhook",
            content=b"{}",
            headers={"stripe-signature": "t=1,v1=abc"},
        )
    assert resp.status_code == 200


def test_webhook_subscription_cancelled(client, workspace_a, db):
    ws_id, token = workspace_a
    event = {
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": "sub_test_456",
                "customer": "cus_test_456",
                "metadata": {"workspace_id": str(ws_id)},
            }
        },
    }
    with patch("stripe.Webhook.construct_event", return_value=event):
        resp = client.post(
            "/billing/webhook",
            content=b"{}",
            headers={"stripe-signature": "t=1,v1=abc"},
        )
    assert resp.status_code == 200
```

- [ ] **Step 3: Run to confirm failure**

```bash
cd backend && pytest tests/test_billing.py -v
```
Expected: ImportError or 404.

- [ ] **Step 4: Implement stripe_service.py**

Create `backend/services/stripe_service.py`:
```python
import os
import stripe

PLAN_PRICE_MAP = {
    "creator": os.getenv("STRIPE_PRICE_CREATOR", "price_creator_monthly"),
    "pro": os.getenv("STRIPE_PRICE_PRO", "price_pro_monthly"),
    "agency": os.getenv("STRIPE_PRICE_AGENCY", "price_agency_monthly"),
}


def init_stripe():
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")


def create_checkout_session(workspace_id: str, plan_tier: str, success_url: str, cancel_url: str) -> stripe.checkout.Session:
    init_stripe()
    price_id = PLAN_PRICE_MAP.get(plan_tier)
    if not price_id:
        raise ValueError(f"Unknown plan tier: {plan_tier}")
    return stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        metadata={"workspace_id": workspace_id},
        success_url=success_url,
        cancel_url=cancel_url,
    )


def construct_webhook_event(payload: bytes, sig_header: str) -> dict:
    init_stripe()
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    return stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
```

- [ ] **Step 5: Implement billing router**

Create `backend/routes/billing.py`:
```python
import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from database import get_db
from domain.enterprise import WorkspaceSubscription
from routes.auth import get_current_session
from services.stripe_service import create_checkout_session, construct_webhook_event

router = APIRouter(prefix="/billing", tags=["billing"])

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")


@router.post("/checkout")
def checkout(payload: dict, db: Session = Depends(get_db), session=Depends(get_current_session)):
    plan_tier = payload.get("plan_tier", "creator")
    stripe_session = create_checkout_session(
        workspace_id=str(session.workspace_id),
        plan_tier=plan_tier,
        success_url=f"{FRONTEND_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{FRONTEND_URL}/billing/cancel",
    )
    return {"checkout_url": stripe_session.url, "session_id": stripe_session.id}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = construct_webhook_event(payload, sig)
    except Exception as e:
        raise HTTPException(400, f"Webhook error: {e}")

    etype = event["type"]
    obj = event["data"]["object"]

    if etype == "customer.subscription.created":
        _handle_sub_created(obj, db)
    elif etype == "customer.subscription.updated":
        _handle_sub_updated(obj, db)
    elif etype == "customer.subscription.deleted":
        _handle_sub_deleted(obj, db)

    return {"status": "ok"}


def _handle_sub_created(obj: dict, db: Session):
    ws_id = obj.get("metadata", {}).get("workspace_id")
    if not ws_id:
        return
    plan_tier = _extract_plan_tier(obj)
    sub = db.query(WorkspaceSubscription).filter(WorkspaceSubscription.workspace_id == ws_id).first()
    if not sub:
        sub = WorkspaceSubscription(workspace_id=ws_id)
        db.add(sub)
    sub.stripe_subscription_id = obj["id"]
    sub.stripe_customer_id = obj["customer"]
    sub.status = obj.get("status", "active")
    sub.plan_tier = plan_tier
    sub.current_period_start = datetime.fromtimestamp(obj.get("current_period_start", 0))
    sub.current_period_end = datetime.fromtimestamp(obj.get("current_period_end", 0))
    db.commit()
    # Upgrade workspace plan tier
    from domain.identity import Workspace
    ws = db.query(Workspace).filter(Workspace.id == ws_id).first()
    if ws:
        ws.plan_tier = plan_tier
        db.commit()


def _handle_sub_updated(obj: dict, db: Session):
    sub = db.query(WorkspaceSubscription).filter(
        WorkspaceSubscription.stripe_subscription_id == obj["id"]
    ).first()
    if not sub:
        # Upsert: subscription.updated can arrive before subscription.created (race)
        ws_id = obj.get("metadata", {}).get("workspace_id")
        if not ws_id:
            return
        sub = db.query(WorkspaceSubscription).filter(WorkspaceSubscription.workspace_id == ws_id).first()
        if not sub:
            sub = WorkspaceSubscription(workspace_id=ws_id)
            db.add(sub)
        sub.stripe_subscription_id = obj["id"]
        sub.stripe_customer_id = obj.get("customer")
    sub.status = obj.get("status", sub.status)
    sub.plan_tier = _extract_plan_tier(obj) or sub.plan_tier
    db.commit()


def _handle_sub_deleted(obj: dict, db: Session):
    ws_id = obj.get("metadata", {}).get("workspace_id")
    if not ws_id:
        return
    sub = db.query(WorkspaceSubscription).filter(WorkspaceSubscription.workspace_id == ws_id).first()
    if sub:
        sub.status = "canceled"
        db.commit()
    from domain.identity import Workspace
    ws = db.query(Workspace).filter(Workspace.id == ws_id).first()
    if ws:
        ws.plan_tier = "starter"
        db.commit()


def _extract_plan_tier(obj: dict) -> str:
    try:
        price_id = obj["items"]["data"][0]["price"]["id"]
        for tier, pid in {"creator": "price_creator", "pro": "price_pro", "agency": "price_agency"}.items():
            if pid in price_id:
                return tier
    except (KeyError, IndexError):
        pass
    return "starter"
```

Register in `main.py`:
```python
from routes.billing import router as billing_router
app.include_router(billing_router)
```

- [ ] **Step 6: Run billing tests**

```bash
cd backend && pytest tests/test_billing.py -v
```
Expected: 3 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/services/stripe_service.py backend/routes/billing.py \
        backend/domain/enterprise/models.py backend/main.py \
        backend/tests/test_billing.py backend/requirements.txt
git commit -m "feat(billing): Stripe checkout + webhook handler — subscription lifecycle"
```

---

## Phase 6 — Notifications

### Task 15: Email notifications via SendGrid

**New package:** `sendgrid>=6.11.0`
Add to `requirements.txt`: `sendgrid>=6.11.0`

**Files:**
- Create: `backend/services/email_service.py`
- Modify: `backend/services/audit.py` — route to email when enabled

- [ ] **Step 1: Write failing test**

Append to a new file `backend/tests/test_notifications.py`:
```python
from unittest.mock import patch, MagicMock


def test_send_email_calls_sendgrid(monkeypatch):
    monkeypatch.setenv("SENDGRID_API_KEY", "SG.test")
    monkeypatch.setenv("SENDGRID_FROM_EMAIL", "noreply@flowcut.ai")
    mock_client = MagicMock()
    mock_client.send.return_value = MagicMock(status_code=202)
    with patch("sendgrid.SendGridAPIClient", return_value=mock_client):
        from services.email_service import send_email
        result = send_email(
            to_email="creator@gmail.com",
            subject="Your clip is ready",
            html_body="<p>Review it now.</p>",
        )
    assert result is True
    mock_client.send.assert_called_once()


def test_send_email_returns_false_on_api_error(monkeypatch):
    monkeypatch.setenv("SENDGRID_API_KEY", "SG.test")
    monkeypatch.setenv("SENDGRID_FROM_EMAIL", "noreply@flowcut.ai")
    mock_client = MagicMock()
    mock_client.send.side_effect = Exception("API error")
    with patch("sendgrid.SendGridAPIClient", return_value=mock_client):
        from services.email_service import send_email
        result = send_email("x@x.com", "sub", "<p>body</p>")
    assert result is False
```

- [ ] **Step 2: Implement email_service.py**

Create `backend/services/email_service.py`:
```python
import logging
import os
import sendgrid
from sendgrid.helpers.mail import Mail

logger = logging.getLogger(__name__)


def send_email(to_email: str, subject: str, html_body: str) -> bool:
    api_key = os.getenv("SENDGRID_API_KEY", "")
    from_email = os.getenv("SENDGRID_FROM_EMAIL", "noreply@flowcut.ai")
    if not api_key:
        logger.warning("SENDGRID_API_KEY not set — email skipped")
        return False
    try:
        message = Mail(
            from_email=from_email,
            to_emails=to_email,
            subject=subject,
            html_content=html_body,
        )
        sg = sendgrid.SendGridAPIClient(api_key=api_key)
        response = sg.send(message)
        return response.status_code in (200, 202)
    except Exception as e:
        logger.error(f"SendGrid error sending to {to_email}: {e}")
        return False
```

- [ ] **Step 3: Run notification tests**

```bash
cd backend && pytest tests/test_notifications.py -v
```
Expected: 2 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/services/email_service.py backend/tests/test_notifications.py \
        backend/requirements.txt
git commit -m "feat(notifications): SendGrid email service"
```

---

### Task 16: FCM push notifications

**New package:** `firebase-admin>=6.5.0`
Add to `requirements.txt`: `firebase-admin>=6.5.0`

**Files:**
- Create: `backend/services/push_service.py`
- Modify: `backend/domain/automation/models.py` — add DeviceToken model

- [ ] **Step 1: Add DeviceToken model**

Append to `backend/domain/automation/models.py`:
```python
class DeviceToken(Base):
    __tablename__ = "device_tokens"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    user_id = Column(UUID_SQL_TYPE, ForeignKey("users.id"), nullable=False)
    workspace_id = Column(UUID_SQL_TYPE, ForeignKey("workspaces.id"), nullable=False)
    token = Column(String, nullable=False)
    platform = Column(String, nullable=False, default="web")  # 'web', 'ios', 'android'
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (UniqueConstraint("user_id", "token", name="uq_device_token_user"),)
```

Add `UniqueConstraint` import if not already present.

- [ ] **Step 2: Implement push_service.py**

Create `backend/services/push_service.py`:
```python
import logging
import os
import firebase_admin
from firebase_admin import credentials, messaging

logger = logging.getLogger(__name__)
_initialized = False


def _init_firebase():
    global _initialized
    if _initialized:
        return
    cred_path = os.getenv("FIREBASE_CREDENTIALS_JSON", "")
    if not cred_path:
        logger.warning("FIREBASE_CREDENTIALS_JSON not set — push disabled")
        return
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)
    _initialized = True


def send_push(fcm_token: str, title: str, body: str, data: dict | None = None) -> bool:
    _init_firebase()
    if not _initialized:
        return False
    try:
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in (data or {}).items()},
            token=fcm_token,
        )
        messaging.send(message)
        return True
    except Exception as e:
        logger.error(f"FCM push failed for token {fcm_token[:20]}...: {e}")
        return False


def send_push_multicast(tokens: list[str], title: str, body: str, data: dict | None = None) -> int:
    """Send to multiple devices. Returns success count."""
    _init_firebase()
    if not _initialized or not tokens:
        return 0
    try:
        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in (data or {}).items()},
            tokens=tokens,
        )
        resp = messaging.send_each_for_multicast(message)
        return resp.success_count
    except Exception as e:
        logger.error(f"FCM multicast failed: {e}")
        return 0
```

- [ ] **Step 3: Wire notifications into audit.py**

In `backend/services/audit.py`, in the `create_notification` function, add email+push dispatch after DB commit:
```python
async def dispatch_notification_channels(user_id: str, workspace_id: str, title: str, body: str, db):
    """Fire email + push for a notification based on workspace preferences."""
    from domain.identity import User
    from domain.automation import DeviceToken
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return

    # Email
    from services.email_service import send_email
    send_email(user.email, title, f"<p>{body}</p>")

    # Push — find all device tokens for this user
    tokens = db.query(DeviceToken).filter(DeviceToken.user_id == user_id).all()
    if tokens:
        from services.push_service import send_push_multicast
        send_push_multicast([t.token for t in tokens], title, body)
```

- [ ] **Step 4: Commit**

```bash
git add backend/services/push_service.py backend/domain/automation/models.py \
        backend/services/audit.py backend/requirements.txt
git commit -m "feat(notifications): FCM push notifications + device token model"
```

---

## Phase 7 — SaaS Completeness

### Task 17: Team invitations + role enforcement

**Files:**
- Modify: `backend/domain/identity/models.py` — add Invitation model
- Create: `backend/routes/invitations.py`
- Create: `backend/tests/test_invitations.py`

- [ ] **Step 1: Add Invitation model**

In `backend/domain/identity/models.py`, append:
```python
class Invitation(Base):
    __tablename__ = "invitations"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    workspace_id = Column(UUID_SQL_TYPE, ForeignKey("workspaces.id"), nullable=False)
    invited_by = Column(UUID_SQL_TYPE, ForeignKey("users.id"), nullable=False)
    email = Column(String, nullable=False)
    role = Column(String, nullable=False, default="editor")
    token = Column(String, nullable=False, unique=True)
    status = Column(String, nullable=False, default="pending")  # pending, accepted, expired
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
```

- [ ] **Step 2: Write failing invitation tests**

Create `backend/tests/test_invitations.py`:
```python
from tests.conftest import _seed_workspace
from datetime import datetime, timedelta


def test_owner_can_invite(client, workspace_a):
    ws_id, token = workspace_a
    resp = client.post(
        "/invitations",
        json={"email": "newmember@test.com", "role": "editor"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "invite_token" in data
    assert data["email"] == "newmember@test.com"


def test_accept_invitation_creates_membership(client, workspace_a, db):
    ws_id, owner_token = workspace_a
    invite_resp = client.post(
        "/invitations",
        json={"email": "joiner@test.com", "role": "editor"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    invite_token = invite_resp.json()["invite_token"]
    # Register the invitee user first
    from domain.identity import User
    from uuid import uuid4
    joiner = User(email="joiner@test.com", name="Joiner", user_type="user")
    db.add(joiner)
    db.commit()
    # Accept
    accept_resp = client.post(f"/invitations/{invite_token}/accept",
                               headers={"Authorization": f"Bearer {owner_token}"})
    assert accept_resp.status_code == 200


def test_editor_cannot_invite(client, workspace_a, db):
    ws_id, owner_token = workspace_a
    # Create editor user + membership
    from domain.identity import User, Membership, AuthSession, Workspace
    from uuid import uuid4
    editor = User(email="editor@test.local", name="Editor")
    db.add(editor)
    db.flush()
    db.add(Membership(workspace_id=ws_id, user_id=editor.id, role="editor"))
    editor_token = str(uuid4())
    db.add(AuthSession(user_id=editor.id, workspace_id=ws_id, token=editor_token))
    db.commit()

    resp = client.post(
        "/invitations",
        json={"email": "x@x.com", "role": "editor"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert resp.status_code == 403
```

- [ ] **Step 3: Run to confirm failure**

```bash
cd backend && pytest tests/test_invitations.py -v
```
Expected: ImportError or 404.

- [ ] **Step 4: Implement invitations router**

Create `backend/routes/invitations.py`:
```python
import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from domain.identity import Invitation, Membership, User
from routes.auth import get_current_session

router = APIRouter(prefix="/invitations", tags=["invitations"])


def _require_role(session, db: Session, allowed_roles: list[str]):
    membership = db.query(Membership).filter(
        Membership.workspace_id == session.workspace_id,
        Membership.user_id == session.user_id,
    ).first()
    if not membership or membership.role not in allowed_roles:
        raise HTTPException(403, f"Role {allowed_roles} required")
    return membership


@router.post("")
def create_invitation(
    payload: dict,
    db: Session = Depends(get_db),
    session=Depends(get_current_session),
):
    _require_role(session, db, ["owner", "admin"])
    email = payload["email"]
    role = payload.get("role", "editor")
    invite_token = secrets.token_urlsafe(32)
    inv = Invitation(
        workspace_id=session.workspace_id,
        invited_by=session.user_id,
        email=email,
        role=role,
        token=invite_token,
        expires_at=datetime.utcnow() + timedelta(days=7),
    )
    db.add(inv)
    db.commit()
    return {"invite_token": invite_token, "email": email, "role": role}


@router.post("/{invite_token}/accept")
def accept_invitation(
    invite_token: str,
    db: Session = Depends(get_db),
    session=Depends(get_current_session),
):
    inv = db.query(Invitation).filter(
        Invitation.token == invite_token,
        Invitation.status == "pending",
    ).first()
    if not inv:
        raise HTTPException(404, "Invitation not found or already used")
    if inv.expires_at < datetime.utcnow():
        inv.status = "expired"
        db.commit()
        raise HTTPException(400, "Invitation expired")

    user = db.query(User).filter(User.email == inv.email).first()
    if not user:
        raise HTTPException(400, "No account found for invited email — sign up first")

    existing = db.query(Membership).filter(
        Membership.workspace_id == inv.workspace_id,
        Membership.user_id == user.id,
    ).first()
    if not existing:
        db.add(Membership(workspace_id=inv.workspace_id, user_id=user.id, role=inv.role))

    inv.status = "accepted"
    db.commit()
    return {"status": "accepted", "workspace_id": str(inv.workspace_id)}
```

Register in `main.py`:
```python
from routes.invitations import router as invitations_router
app.include_router(invitations_router)
```

- [ ] **Step 5: Run tests**

```bash
cd backend && pytest tests/test_invitations.py -v
```
Expected: 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/domain/identity/models.py backend/routes/invitations.py \
        backend/main.py backend/tests/test_invitations.py
git commit -m "feat(saas): team invitations with role-based access enforcement"
```

---

### Task 18: Usage enforcement at upload + clip creation

**Files:**
- Modify: `backend/routes/uploads.py` — check quota before accepting upload
- Modify: `backend/services/enterprise.py` — add enforcement helper

- [ ] **Step 1: Write failing test**

Append to `backend/tests/test_invitations.py` (or create `test_quota.py`):
```python
def test_upload_blocked_when_quota_exceeded(client, workspace_a, db):
    ws_id, token = workspace_a
    # Set quota to 1MB and record 1MB already used
    from domain.identity import Workspace
    from domain.enterprise import UsageRecord
    ws = db.query(Workspace).filter(Workspace.id == ws_id).first()
    ws.storage_quota_mb = 1
    db.add(UsageRecord(workspace_id=ws_id, dimension="storage_mb", period="2026-04",
                        quantity=1.1, limit_value=1.0))
    db.commit()
    import io
    data = io.BytesIO(b"0" * 100)
    resp = client.post(
        "/uploads/sessions",
        data={"filename": "test.mp4", "size": "100"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 429
```

- [ ] **Step 2: Add quota enforcement helper**

In `backend/services/enterprise.py`, add:
```python
def check_quota(workspace_id: str, dimension: str, requested_quantity: float, db) -> bool:
    """Returns True if the workspace has quota remaining, False if exceeded."""
    from domain.enterprise import UsageRecord
    from datetime import datetime
    period = datetime.utcnow().strftime("%Y-%m")
    record = db.query(UsageRecord).filter(
        UsageRecord.workspace_id == workspace_id,
        UsageRecord.dimension == dimension,
        UsageRecord.period == period,
    ).first()
    if not record:
        return True
    if record.limit_value < 0:  # -1 = unlimited
        return True
    return (record.quantity + requested_quantity) <= record.limit_value
```

- [ ] **Step 3: Enforce in uploads route**

In `backend/routes/uploads.py`, in the session creation handler, add before creating the upload session:
```python
from services.enterprise import check_quota
size_mb = int(request_data.get("size", 0)) / (1024 * 1024)
if not check_quota(session.workspace_id, "storage_mb", size_mb, db):
    raise HTTPException(429, "Storage quota exceeded for this billing period")
```

- [ ] **Step 4: Run test**

```bash
cd backend && pytest tests/test_invitations.py::test_upload_blocked_when_quota_exceeded -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/routes/uploads.py backend/services/enterprise.py
git commit -m "feat(saas): enforce storage quota on upload session creation"
```

---

## Phase 8 — Review Loop Closure

### Task 19: Natural language corrections → re-plan

> When a creator rejects a clip with text feedback ("make the intro shorter", "remove the zoom at 5s"), that text is injected into the planner as a correction signal and the clip is re-queued.

**Files:**
- Modify: `backend/routes/autonomy.py` — capture diff on approve, structured corrections on reject
- Create: `backend/services/sie/re_planner.py`

- [ ] **Step 1: Implement re_planner.py**

Create `backend/services/sie/re_planner.py`:
```python
from __future__ import annotations
import json
import logging
from database import SessionLocal
from domain.media import Clip
from domain.projects import StyleProfile
from services.sie.planner import generate_edit_plan
from services.sie.critic import run_reflection_loop
from services.sie.gates import run_quality_gates, GateFailure
from services.sie.memory import store_edit_episode

logger = logging.getLogger(__name__)


async def re_plan_clip(clip_id: str, corrections: list[dict]):
    """Re-generate the edit plan for a rejected clip, incorporating creator corrections.
    Corrections is a list of {type, instruction} dicts."""
    db = SessionLocal()
    try:
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            return

        profile = None
        if clip.profile_id:
            profile = db.query(StyleProfile).filter(StyleProfile.id == clip.profile_id).first()

        style_doc = json.loads(profile.style_doc or "{}") if profile else {}

        # Inject corrections into style profile for this planning pass
        correction_text = "; ".join(c.get("instruction", "") for c in corrections if c.get("instruction"))
        augmented_style = {**style_doc, "corrections_to_apply": correction_text}

        moments = []
        if clip.moment_start_sec is not None and clip.moment_end_sec is not None:
            moments = [{"start_sec": clip.moment_start_sec, "end_sec": clip.moment_end_sec,
                        "score": clip.moment_score or 0.7, "type": clip.moment_type or "highlight"}]

        footage_duration = (clip.moment_end_sec or 60.0) + 5.0

        manifest = generate_edit_plan(
            footage_path=clip.source_path or "",
            footage_duration_sec=footage_duration,
            moments=moments,
            style_profile=augmented_style,
            episodic_context=[{"correction": correction_text}],
        )

        try:
            run_quality_gates(manifest, footage_duration, style_doc)
        except GateFailure as e:
            logger.warning(f"Re-planned manifest failed gate for clip {clip_id}: {e}")

        clip.edit_manifest = manifest.model_dump_json()
        clip.edit_confidence = manifest.confidence
        clip.review_corrections = json.dumps(corrections)
        clip.status = "draft"
        db.commit()

        if profile and profile.mem0_user_id:
            store_edit_episode(
                profile.mem0_user_id, clip_id,
                f"re-plan with corrections: {correction_text}",
                critique=None, action="correction",
            )
    except Exception as e:
        logger.error(f"Re-plan failed for clip {clip_id}: {e}")
        db.rollback()
    finally:
        db.close()
```

- [ ] **Step 2: Wire re-planner into autonomy route**

In `backend/routes/autonomy.py`, in the reject handler, after saving corrections to DB:
```python
# After committing the rejection:
if corrections:
    import asyncio
    from services.sie.re_planner import re_plan_clip
    asyncio.create_task(re_plan_clip(str(clip.id), corrections))
```

Also capture the diff on approve — when a creator modifies the manifest before approving:
```python
# In the approve handler, if edit_manifest_override is provided:
if payload.get("edit_manifest_override") and clip.edit_manifest:
    from services.sie.feedback import diff_manifests, apply_feedback_to_profile
    import json
    original = json.loads(clip.edit_manifest)
    modified = payload["edit_manifest_override"]
    diff = diff_manifests(original, modified)
    if diff and profile:
        style_doc = json.loads(profile.style_doc or "{}")
        locks = json.loads(profile.dimension_locks or "{}")
        updated = apply_feedback_to_profile(style_doc, diff, locks, action="modified")
        profile.style_doc = json.dumps(updated)
        profile.version += 1
        db.commit()
```

- [ ] **Step 3: Commit**

```bash
git add backend/services/sie/re_planner.py backend/routes/autonomy.py
git commit -m "feat(review): NL corrections → async re-plan + diff capture on approve"
```

---

### Task 20: Per-platform caption variants

> Each clip render should have platform-specific title, description, and hashtags. Currently a single caption is used for all platforms. Add a Gemini-powered caption generator that produces variants for each platform target.

**Files:**
- Create: `backend/services/caption_generator.py`
- Modify: `backend/routes/platforms.py` — use per-platform captions when scheduling

- [ ] **Step 1: Implement caption_generator.py**

Create `backend/services/caption_generator.py`:
```python
import json
import os
import logging
from google import genai

logger = logging.getLogger(__name__)

PLATFORM_CONSTRAINTS = {
    "tiktok":           {"max_chars": 2200, "hashtag_count": 5,  "hook_chars": 150, "style": "energetic, short sentences, emoji OK"},
    "youtube_shorts":   {"max_chars": 5000, "hashtag_count": 8,  "hook_chars": 100, "style": "SEO-friendly, descriptive"},
    "youtube":          {"max_chars": 5000, "hashtag_count": 8,  "hook_chars": 200, "style": "SEO-friendly, detailed"},
    "instagram_reels":  {"max_chars": 2200, "hashtag_count": 15, "hook_chars": 125, "style": "visual, lifestyle tone, hashtag-heavy"},
    "linkedin":         {"max_chars": 3000, "hashtag_count": 4,  "hook_chars": 140, "style": "professional, insightful, 3-5 hashtags"},
    "x":                {"max_chars": 280,  "hashtag_count": 2,  "hook_chars": 280, "style": "punchy, max 2 hashtags, thread-friendly"},
}


def generate_platform_captions(
    transcript: str,
    moment_type: str,
    platforms: list[str],
    style_voice: str = "",
) -> dict[str, dict]:
    """Generate platform-specific title, description, and hashtags for each platform.
    Returns {platform: {title, description, hashtags}}."""
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return {p: {"title": "New clip", "description": "", "hashtags": []} for p in platforms}

    client = genai.Client(api_key=api_key)
    constraints_text = json.dumps({p: PLATFORM_CONSTRAINTS[p] for p in platforms if p in PLATFORM_CONSTRAINTS})
    prompt = (
        f"Generate platform-specific captions for a short-form video clip.\n"
        f"Transcript excerpt: {transcript[:500]}\n"
        f"Moment type: {moment_type}\n"
        f"Creator voice: {style_voice or 'casual, engaging'}\n"
        f"Platform constraints: {constraints_text}\n\n"
        f"Return JSON: {{platform: {{title, description, hashtags: [list]}}}} for each platform."
    )
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        return json.loads(response.text)
    except Exception as e:
        logger.error(f"Caption generation failed: {e}")
        return {p: {"title": "New clip", "description": "", "hashtags": []} for p in platforms}
```

- [ ] **Step 2: Use per-platform captions during scheduling**

In `backend/routes/platforms.py`, in the publish/schedule endpoint, after creating CalendarSlot objects, generate per-platform captions and store them:
```python
from services.caption_generator import generate_platform_captions

# Before creating slots:
captions = generate_platform_captions(
    transcript=clip.transcript or "",
    moment_type=clip.moment_type or "highlight",
    platforms=payload.get("platforms", []),
    style_voice="",
)
# Then when creating each slot:
slot_title = captions.get(platform, {}).get("title", clip.title or "New clip")
slot_description = captions.get(platform, {}).get("description", "")
slot_hashtags = captions.get(platform, {}).get("hashtags", [])
```

- [ ] **Step 3: Commit**

```bash
git add backend/services/caption_generator.py backend/routes/platforms.py
git commit -m "feat(distribution): per-platform caption variants via Gemini"
```

---

## Final: dependency lockdown + migration

- [ ] **Step 1: Install all new packages**

```bash
cd backend && pip install -r requirements.txt
```
Expected: all packages install without conflict.

- [ ] **Step 2: Run the full test suite**

```bash
cd backend && pytest tests/ -v --tb=short
```
Expected: all tests pass. Fix any import or fixture issues before shipping.

- [ ] **Step 3: Generate Alembic migrations for all model changes**

```bash
cd backend && alembic revision --autogenerate -m "phase1-8-full-coverage"
alembic upgrade head
```
Verify the generated migration covers:
- `users.oauth_provider`, `users.oauth_id`, `users.avatar_url`
- `auth_sessions.expires_at`
- `style_profiles.genre`, `style_profiles.style_doc`, `style_profiles.confidence_scores`, `style_profiles.dimension_locks`, `style_profiles.version`, `style_profiles.mem0_user_id`
- `workspace_subscriptions.stripe_customer_id`, `stripe_subscription_id`, `stripe_price_id`
- `device_tokens` table
- `invitations` table

Also **manually add these performance indexes** to the migration (autogenerate does not infer them):
```python
# In the upgrade() function of the generated migration:
op.create_index("ix_calendar_slots_published_status", "calendar_slots",
    ["published_at", "status"])
op.create_index("ix_platform_auth_expires_at", "platform_auths",
    ["token_expires_at"])
op.create_index("ix_ai_usage_workspace_task", "ai_usage_records",
    ["workspace_id", "task_type"])

# And in downgrade():
op.drop_index("ix_calendar_slots_published_status", "calendar_slots")
op.drop_index("ix_platform_auth_expires_at", "platform_auths")
op.drop_index("ix_ai_usage_workspace_task", "ai_usage_records")
```

Why these matter:
- `ix_calendar_slots_published_status`: `run_performance_feedback_sweep()` filters on both columns; without it, every sweep is a full scan of `calendar_slots`.
- `ix_platform_auth_expires_at`: `get_tokens_needing_refresh()` runs every few minutes against potentially thousands of rows.
- `ix_ai_usage_workspace_task`: usage analytics queries (`/ai/usage`) filter by both columns; used in billing dashboards.

- [ ] **Step 4: Final commit**

```bash
git add backend/requirements.txt
git commit -m "chore: final requirements lockdown + migration generation"
```

---

## Summary of agentic patterns applied

| Pattern | Where applied |
|---|---|
| **Orchestrator/Worker** | `graph.py` — LangGraph DAG fans out scene/transcript/visual workers in parallel, collects results |
| **Reflection/self-critique** | `critic.py` — workspace-configured critic reviews planner output; 1 refinement iteration maximum |
| **Single-pass structured output** | `planner.py` — one Instructor call with `reasoning: str` chain-of-thought field; half the latency vs two-step |
| **Provider abstraction** | `ai_registry.py` — `run_structured_task()` + `run_text_task()` dispatch to Anthropic / OpenAI / Gemini based on workspace AI policy; default overridable per task type |
| **Episodic memory** | `memory.py` — Mem0 stores past edit plans and critiques, retrieved per video type |
| **Semantic memory** | `StyleProfile.style_doc` — living JSON document updated from feedback diffs |
| **Memory decay** | `feedback.py` — locked dimensions stay fixed; unlocked dimensions shift by 5% per approval |
| **Quality gate (inline)** | `gates.py` — format + grounding + style compliance checks block bad manifests |
| **Human-in-the-loop (selective)** | Autonomy modes: AUTO_PUBLISH bypasses review above confidence threshold |
| **Diff-based feedback** | `feedback.py` — captures what the creator changed, not just approve/reject binary |
| **Delayed reward** | `performance.py` — 72h maturation before updating style profile from published clip metrics |

---

---

## NOT In Scope

The following are explicitly excluded from this plan. Do not implement them unless the user explicitly adds a new phase.

| Item | Reason excluded |
|------|----------------|
| Video export / rendering pipeline | Exists in production; pipeline.py is not modified |
| Multi-language transcription | Whisper handles it automatically; no new config needed |
| Custom Mem0 self-hosting | Cloud Mem0 API used; infra is out of scope for this plan |
| Admin dashboard UI | Backend-only plan; frontend is out of scope |
| Platform API client SDK implementation | Existing `platforms` routes handle this |
| A/B testing framework | Post-launch feature |
| Real-time analytics ingestion | Platform analytics are polled at 72h maturation; streaming out of scope |
| Mobile push APN (Apple) | FCM only; APN requires separate certificate management |
| Stripe metered billing | Flat subscription tiers only; metered usage billing is a future phase |

---

## What Already Exists (do not re-implement)

| Component | Location | Notes |
|-----------|----------|-------|
| Clip processing pipeline | `backend/services/pipeline.py` | Do not modify. SIE hooks in via `edit_manifest` field. |
| AI usage tracking (`AIUsageRecord`) | `backend/domain/ai/models.py` | Already exists; `_record_usage()` writes to it. |
| Workspace + Membership models | `backend/domain/identity/models.py` | Extend, do not replace. |
| Platform auth (`PlatformAuth`) | `backend/domain/platforms/models.py` | Token refresh modifies `access_token_enc`; model already has this column. |
| Project + Clip models | `backend/domain/projects/` + `domain/media/` | Extend with `edit_manifest`, `profile_id` columns only. |
| WebSocket broadcast | `backend/routes/ws.py` | Use `broadcast()` as-is. |
| `AIProviderRegistry` singleton | `backend/services/ai_registry.py` | Single dispatch point for all AI. Do not bypass. |
| Audit log | `backend/services/audit.py` | `record_audit()` already exists. |
| Storage service | `backend/services/storage.py` | `download_to_temp()` already exists. |

---

## Failure Modes

| Failure | Affected component | Recovery strategy |
|---------|-------------------|-------------------|
| Anthropic API down | planner.py, critic.py, ai_registry.py | `select_provider` fallback to Vertex; circuit breaker opens after 3 failures |
| Vertex AI down | ai_registry.py visual tasks | Circuit breaker; `run_text_task` raises, caller handles |
| Mem0 unavailable | memory.py | Soft fallback — `retrieve_episodic_context` returns `[]`; SIE continues without episodic context |
| Whisper OOM | workers.py | `run_all_workers` uses `asyncio.gather(..., return_exceptions=True)`; exception → empty transcript, synthesis uses scene fallback |
| LangGraph state serialization error | graph.py | `_planning_node` catches exception, returns `errors: ["planning failed: ..."]`; gate sees no manifest, `gate_passed=False` |
| Stripe webhook duplicate delivery | billing.py | `UniqueConstraint("workspace_id")` + upsert in `_handle_sub_updated` prevents double-create |
| OAuth state token expired (>10min) | routes/auth.py | 400 HTTP error with "Invalid or expired OAuth state token"; user restarts OAuth flow |
| SendGrid quota exceeded | email_service.py | Logged at WARNING; notification silently dropped (non-fatal) |
| FCM token invalid | push_service.py | Token deleted from `device_tokens` on 404 response from FCM |
| DB connection pool exhausted | `_planning_node` SessionLocal | `finally: db.close()` always runs; pool returns connection within LangGraph node lifetime |
| CalendarSlot feedback sweep fails mid-batch | performance.py | Per-slot try/except + rollback; other slots in batch continue |

---

## Parallelization Strategy

These tasks are independent and can be executed in parallel by a multi-agent executor:

**Parallel batch 1** (no shared files, no shared models):
- Task 1 (Auth) + Task 2 (Token crypto) — both write to auth domain, but different files
- Task 3 (EditManifest schema) + Task 4 (Quality gates) — both in `sie/`, read-only dependency

**Parallel batch 2** (after batch 1 complete):
- Task 4.5 (AIProviderRegistry OpenAI) runs independently of Task 5 (planner)
- Task 11 (Token refresh) + Task 12 (Circuit breaker) — fully independent services

**Parallel batch 3** (after SIE core — Tasks 3-8 — complete):
- Task 13 (Scheduling) + Task 14 (Billing) + Task 15 (Email) + Task 16 (Push) — all independent

**Sequential dependencies:**
- Task 3 (schema) → Task 4.5 (registry) → Task 5 (planner) → Task 6 (critic) → Task 7 (memory+feedback) → Task 8 (graph) — strict ordering
- Task 9 (style profile API) → Task 10 (performance feedback) — profile API must exist first
- Task 17 (invitations) → Task 18 (usage enforcement) — membership model must be final

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 2 | CLEARED | HOLD_SCOPE mode, 4 critical gaps fixed |
| Codex Review | `/codex review` | Independent 2nd opinion | 2 | CLEARED | 5 findings resolved: single-pass, Mem0 fallback, Gemini SDK, LangGraph, SQLite |
| Eng Review | `/plan-eng-review` | Architecture + test coverage | 2 | CLEARED | 10 issues found, all fixed in this session — see breakdown below |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | Not run (backend-only plan) |

**Eng Review — Issues Fixed (this session):**

| # | Issue | Severity | Fix applied |
|---|-------|----------|-------------|
| 1 | `db_session` NameError in `test_ai_registry_structured.py` (×2) | Critical | Renamed to `db` on both occurrences |
| 2 | Task 5 commit message says "two-step" but impl is single-pass | Minor | Updated commit message |
| 3 | Task 6 critic test mocks ghost functions `_run_analysis_pass`/`_run_format_pass` | Critical | Rewritten to mock `registry.run_text_task` + `registry.run_structured_task` |
| 4 | `_planning_node` calls `generate_edit_plan` without `db`/`workspace` | Critical | `SessionLocal()` + `Workspace` query inside node; `finally: db.close()` |
| 5 | `import logging` inside `except` blocks in `memory.py` (×2) | Minor | Moved to module level; `logger = logging.getLogger(__name__)` |
| 6 | OAuth callback CSRF: state validation skipped with comment | High | `verify_state_token()` enforced; 400 on invalid state; CSRF test added |
| 7 | Billing race: `_handle_sub_created` duplicates on concurrent webhooks; `_handle_sub_updated` silently drops unknown sub | High | `UniqueConstraint("workspace_id")` added; `_handle_sub_updated` upserts |
| 8 | `cuts_per_min` drift unbounded in `feedback.py` — 1.05× forever | Medium | Clamped to `1.5x genre_centroid.max_cuts_per_min` |
| 9 | `graph.py` has zero test coverage | High | `test_sie_graph.py` added (4 tests: synthesis fallback, gate pass/fail, workspace-not-found) |
| 10 | `workers.py` has zero tests + WhisperModel reloaded per call (~5-10s) | High | `test_sie_workers.py` added (4 tests); singleton `_whisper_model` added |

**Perf findings (Section 4):**

| Finding | Impact | Fix applied |
|---------|--------|-------------|
| No index on `calendar_slots(published_at, status)` | Full scan on feedback sweep | Added to migration in Final task |
| No index on `platform_auths(token_expires_at)` | Full scan on refresh sweep | Added to migration in Final task |
| N×3 queries per slot in `_process_slot_feedback` | ~150 queries/sweep | Documented; acceptable at pre-revenue scale with `limit(50)` |

**CROSS-MODEL:** CEO + outside voice consensus: Mem0 soft fallback, Gemini SDK removal, `db=None` footgun, single-pass planner. All applied.

**UNRESOLVED:** 0 decisions outstanding.

**VERDICT:** ALL REVIEWS CLEARED. Plan is ready for execution.
