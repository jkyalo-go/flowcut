from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_session
from contracts.identity import DevLoginRequest, SessionResponse, UserResponse, WorkspaceResponse
from domain.enterprise import OnboardingState, QuotaPolicy, SubscriptionPlan, WorkspaceSubscription
from domain.identity import AuthSession, Membership, User, Workspace
from domain.shared import SubscriptionStatus

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
