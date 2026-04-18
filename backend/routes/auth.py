import os
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import bcrypt as _bcrypt
import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

import services.oauth as _oauth_svc
from config import FRONTEND_URL
from contracts.identity import (
    DevLoginRequest,
    LoginRequest,
    RegisterRequest,
    SessionResponse,
    SwitchWorkspaceRequest,
    UserResponse,
    WorkspaceResponse,
)
from database import get_db
from dependencies import get_current_session, get_current_user
from domain.enterprise import OnboardingState, QuotaPolicy, SubscriptionPlan, WorkspaceSubscription
from domain.identity import AuthSession, Membership, User, Workspace
from domain.shared import SubscriptionStatus


def _hash_password(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()

def _verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode(), hashed.encode())

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", f"{FRONTEND_URL}/auth/callback")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-prod")
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "flowcut_session")
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").strip().lower() in {"1", "true", "yes", "on"}
ENABLE_DEV_LOGIN = os.getenv("ENABLE_DEV_LOGIN", "false").strip().lower() in {"1", "true", "yes", "on"}

router = APIRouter()


def _slugify(name: str) -> str:
    return name.strip().lower().replace(" ", "-")


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _set_session_cookie(response: Response, token: str, expires_at: datetime | None) -> None:
    max_age = None
    expires = None
    if expires_at is not None:
        max_age = max(int((expires_at - _utc_now()).total_seconds()), 0)
        expires = expires_at.replace(tzinfo=UTC)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite="lax",
        path="/",
        max_age=max_age,
        expires=expires,
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


def _provision_workspace_defaults(workspace: Workspace, db: Session) -> None:
    starter = db.query(SubscriptionPlan).filter(SubscriptionPlan.key == "starter").first()
    if starter and not db.query(WorkspaceSubscription).filter(WorkspaceSubscription.workspace_id == workspace.id).first():
        db.add(WorkspaceSubscription(workspace_id=workspace.id, plan_id=starter.id, status=SubscriptionStatus.TRIAL))
    if not db.query(QuotaPolicy).filter(QuotaPolicy.workspace_id == workspace.id).first():
        db.add(QuotaPolicy(workspace_id=workspace.id, storage_quota_mb=workspace.storage_quota_mb, retained_footage_days=workspace.raw_retention_days))
    if not db.query(OnboardingState).filter(OnboardingState.workspace_id == workspace.id).first():
        db.add(OnboardingState(
            workspace_id=workspace.id,
            checklist_json='{"workspace_created":true,"brand_setup":false,"provider_policy_configured":false,"platform_connected":false,"first_upload":false,"style_profile_created":false,"first_publish_ready":false}',
        ))


def _create_session(user: User, db: Session, response: Response, *, workspace: Workspace | None = None,
                    ttl: timedelta = timedelta(days=30)) -> SessionResponse:
    ws = workspace or (db.query(Workspace)
                       .join(Membership, Membership.workspace_id == Workspace.id)
                       .filter(Membership.user_id == user.id)
                       .first())
    if ws is None:
        raise HTTPException(status_code=422, detail="User has no workspace")
    token = uuid4().hex
    expires_at = _utc_now() + ttl
    db.add(AuthSession(user_id=user.id, workspace_id=ws.id, token=token, expires_at=expires_at))
    db.commit()
    _set_session_cookie(response, token, expires_at)
    return SessionResponse(
        token=token,
        user=UserResponse.model_validate(user),
        workspace=WorkspaceResponse.model_validate(ws),
    )


@router.post("/register", response_model=SessionResponse)
def register(body: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        email=email,
        name=(body.name or email.split("@")[0]),
        password_hash=_hash_password(body.password),
    )
    db.add(user)
    db.flush()
    base_slug = email.split("@")[0].lower().replace(".", "-")
    slug = f"{base_slug}-{secrets.token_hex(3)}"
    ws = Workspace(name=f"{user.name}'s Workspace", slug=slug, plan_tier="starter",
                   storage_quota_mb=10240, raw_retention_days=30)
    db.add(ws)
    db.flush()
    db.add(Membership(workspace_id=ws.id, user_id=user.id, role="owner"))
    _provision_workspace_defaults(ws, db)
    db.commit()
    db.refresh(user)
    return _create_session(user, db, response, workspace=ws)


@router.post("/login", response_model=SessionResponse)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not _verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return _create_session(user, db, response)


@router.post("/switch-workspace", response_model=SessionResponse)
def switch_workspace(
    payload: SwitchWorkspaceRequest,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace_id = payload.workspace_id
    membership = db.query(Membership).filter(
        Membership.workspace_id == workspace_id,
        Membership.user_id == user.id,
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="No access to that workspace")
    ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return _create_session(user, db, response, workspace=ws)


@router.post("/dev-login", response_model=SessionResponse)
def dev_login(body: DevLoginRequest, response: Response, db: Session = Depends(get_db)):
    if not ENABLE_DEV_LOGIN:
        raise HTTPException(status_code=404, detail="Dev login is disabled")
    user = db.query(User).filter(User.email == body.email.strip().lower()).first()
    if not user:
        user = User(email=body.email.strip().lower(), name=body.name or body.email.split("@")[0])
        db.add(user)
        db.commit()
        db.refresh(user)

    workspace_name = body.workspace_name or "Default Workspace"
    workspace_slug = _slugify(workspace_name)
    workspace = db.query(Workspace).filter(Workspace.slug == workspace_slug).first()
    if not workspace:
        workspace = Workspace(name=workspace_name, slug=workspace_slug)
        db.add(workspace)
        db.commit()
        db.refresh(workspace)
        _provision_workspace_defaults(workspace, db)
        db.commit()

    membership = db.query(Membership).filter(
        Membership.workspace_id == workspace.id,
        Membership.user_id == user.id,
    ).first()
    if not membership:
        db.add(Membership(workspace_id=workspace.id, user_id=user.id, role="owner"))
        db.commit()

    return _create_session(user, db, response, workspace=workspace)


@router.get("/me", response_model=SessionResponse)
def me(response: Response, session: AuthSession = Depends(get_current_session), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == session.user_id).first()
    workspace = db.query(Workspace).filter(Workspace.id == session.workspace_id).first()
    _set_session_cookie(response, session.token, session.expires_at)
    return SessionResponse(
        token=session.token,
        user=UserResponse.model_validate(user),
        workspace=WorkspaceResponse.model_validate(workspace),
    )


@router.get("/oauth/google/start")
async def google_oauth_start():
    state = _oauth_svc.generate_state_token(SECRET_KEY)
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
async def google_oauth_callback(payload: dict, response: Response, db: Session = Depends(get_db)):
    code = payload.get("code", "")
    state = payload.get("state", "")
    try:
        _oauth_svc.verify_state_token(SECRET_KEY, state)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state token")
    try:
        user_info = await _oauth_svc.exchange_google_code(
            code=code,
            redirect_uri=GOOGLE_REDIRECT_URI,
            client_id=GOOGLE_CLIENT_ID,
            client_secret=GOOGLE_CLIENT_SECRET,
        )
    except httpx.HTTPStatusError:
        raise HTTPException(status_code=400, detail="Google token exchange failed")

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
        base_slug = email.split("@")[0].lower().replace(".", "-")
        slug = f"{base_slug}-{secrets.token_hex(3)}"
        ws = Workspace(name=f"{user.name}'s Workspace", slug=slug, plan_tier="starter",
                       storage_quota_mb=10240, raw_retention_days=7)
        db.add(ws)
        db.flush()
        db.add(Membership(workspace_id=ws.id, user_id=user.id, role="owner"))
        _provision_workspace_defaults(ws, db)
        db.flush()
    else:
        ws = (db.query(Workspace)
              .join(Membership, Membership.workspace_id == Workspace.id)
              .filter(Membership.user_id == user.id)
              .first())
        if ws is None:
            raise HTTPException(status_code=422, detail="User has no workspace.")
        user.oauth_provider = "google"
        user.oauth_id = oauth_id

    db.commit()
    return _create_session(user, db, response, workspace=ws, ttl=timedelta(hours=24))


@router.post("/logout")
def logout(response: Response, session: AuthSession = Depends(get_current_session), db: Session = Depends(get_db)):
    db.delete(session)
    db.commit()
    _clear_session_cookie(response)
    return {"ok": True}
