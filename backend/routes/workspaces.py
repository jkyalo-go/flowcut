from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user, get_current_workspace
from contracts.identity import MembershipResponse, WorkspaceCreate, WorkspaceResponse
from domain.enterprise import OnboardingState, QuotaPolicy, SubscriptionPlan, WorkspaceSubscription
from domain.identity import Membership, Workspace
from domain.shared import SubscriptionStatus

router = APIRouter()


def _slugify(name: str) -> str:
    return name.strip().lower().replace(" ", "-")


@router.get("", response_model=list[WorkspaceResponse])
def list_workspaces(user=Depends(get_current_user), db: Session = Depends(get_db)):
    memberships = db.query(Membership).filter(Membership.user_id == user.id).all()
    ids = [m.workspace_id for m in memberships]
    if not ids:
        return []
    return db.query(Workspace).filter(Workspace.id.in_(ids)).all()


@router.post("", response_model=WorkspaceResponse)
def create_workspace(body: WorkspaceCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    slug = body.slug or _slugify(body.name)
    existing = db.query(Workspace).filter(Workspace.slug == slug).first()
    if existing:
        raise HTTPException(409, "Workspace slug already exists")
    workspace = Workspace(name=body.name, slug=slug)
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    db.add(Membership(workspace_id=workspace.id, user_id=user.id, role="owner"))
    starter = db.query(SubscriptionPlan).filter(SubscriptionPlan.key == "starter").first()
    if starter:
        db.add(WorkspaceSubscription(workspace_id=workspace.id, plan_id=starter.id, status=SubscriptionStatus.TRIAL))
    db.add(QuotaPolicy(workspace_id=workspace.id, storage_quota_mb=workspace.storage_quota_mb, retained_footage_days=workspace.raw_retention_days))
    db.add(OnboardingState(
        workspace_id=workspace.id,
        checklist_json='{"workspace_created":true,"brand_setup":false,"provider_policy_configured":false,"platform_connected":false,"first_upload":false,"style_profile_created":false,"first_publish_ready":false}',
    ))
    db.commit()
    return workspace


@router.get("/current/members", response_model=list[MembershipResponse])
def list_members(workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    rows = db.query(Membership).filter(Membership.workspace_id == workspace.id).all()
    return rows
