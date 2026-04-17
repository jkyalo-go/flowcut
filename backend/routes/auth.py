import os
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_session
from contracts.identity import DevLoginRequest, SessionResponse, UserResponse, WorkspaceResponse
from domain.enterprise import OnboardingState, QuotaPolicy, SubscriptionPlan, WorkspaceSubscription
from domain.identity import AuthSession, Membership, User, Workspace
from domain.shared import SubscriptionStatus
import services.oauth as _oauth_svc

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:3000/auth/callback/google")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-prod")

router = APIRouter()


def _slugify(name: str) -> str:
    return name.strip().lower().replace(" ", "-")


@router.post("/dev-login", response_model=SessionResponse)
def dev_login(body: DevLoginRequest, db: Session = Depends(get_db)):
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
        starter = db.query(SubscriptionPlan).filter(SubscriptionPlan.key == "starter").first()
        if starter:
            db.add(WorkspaceSubscription(workspace_id=workspace.id, plan_id=starter.id, status=SubscriptionStatus.TRIAL))
        db.add(QuotaPolicy(workspace_id=workspace.id, storage_quota_mb=workspace.storage_quota_mb, retained_footage_days=workspace.raw_retention_days))
        db.add(OnboardingState(
            workspace_id=workspace.id,
            checklist_json='{"workspace_created":true,"brand_setup":false,"provider_policy_configured":false,"platform_connected":false,"first_upload":false,"style_profile_created":false,"first_publish_ready":false}',
        ))
        db.commit()

    membership = db.query(Membership).filter(
        Membership.workspace_id == workspace.id,
        Membership.user_id == user.id,
    ).first()
    if not membership:
        db.add(Membership(workspace_id=workspace.id, user_id=user.id, role="owner"))
        db.commit()

    token = uuid4().hex
    session = AuthSession(user_id=user.id, workspace_id=workspace.id, token=token)
    db.add(session)
    db.commit()

    return SessionResponse(
        token=token,
        user=UserResponse.model_validate(user),
        workspace=WorkspaceResponse.model_validate(workspace),
    )


@router.get("/me", response_model=SessionResponse)
def me(session: AuthSession = Depends(get_current_session), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == session.user_id).first()
    workspace = db.query(Workspace).filter(Workspace.id == session.workspace_id).first()
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
async def google_oauth_callback(payload: dict, db: Session = Depends(get_db)):
    code = payload.get("code", "")
    state = payload.get("state", "")
    try:
        _oauth_svc.verify_state_token(SECRET_KEY, state)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state token")
    user_info = await _oauth_svc.exchange_google_code(
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
