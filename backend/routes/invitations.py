import os
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from config import FRONTEND_URL
from database import get_db
from dependencies import get_current_session
from contracts.identity import InvitationCreateRequest, SessionResponse
from domain.identity import Invitation, Membership, User, Workspace
from routes.auth import _create_session
from services.email_service import send_email

router = APIRouter(prefix="/invitations", tags=["invitations"])
ALLOWED_ROLES = {"owner", "admin", "editor", "viewer"}


def _require_owner_or_admin(session, db: Session):
    membership = db.query(Membership).filter(
        Membership.workspace_id == session.workspace_id,
        Membership.user_id == session.user_id,
    ).first()
    if not membership or membership.role not in ("owner", "admin"):
        raise HTTPException(403, "Owner or admin role required")
    return membership


@router.post("")
def create_invitation(
    payload: InvitationCreateRequest,
    db: Session = Depends(get_db),
    session=Depends(get_current_session),
):
    _require_owner_or_admin(session, db)
    email = payload.email.strip().lower()
    if not email:
        raise HTTPException(400, "email is required")
    role = payload.role.strip().lower()
    if role not in ALLOWED_ROLES:
        raise HTTPException(400, "Invalid role")
    invite_token = secrets.token_urlsafe(32)
    inv = Invitation(
        workspace_id=session.workspace_id,
        invited_by=session.user_id,
        email=email,
        role=role,
        token=invite_token,
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=7),
    )
    db.add(inv)
    db.commit()
    workspace = db.query(Workspace).filter(Workspace.id == session.workspace_id).first()
    invite_url = f"{FRONTEND_URL}/invitations/{invite_token}/accept"
    email_sent = send_email(
        to_email=email,
        subject=f"Invitation to join {workspace.name if workspace else 'Flowcut'}",
        html_body=(
            f"<p>You were invited to join <strong>{workspace.name if workspace else 'a Flowcut workspace'}</strong> as "
            f"<strong>{role}</strong>.</p><p><a href=\"{invite_url}\">Accept the invitation</a></p>"
        ),
    )
    return {
        "invite_token": invite_token,
        "invite_url": invite_url,
        "email": email,
        "role": role,
        "email_sent": email_sent,
    }


@router.get("/{invite_token}")
def get_invitation(invite_token: str, db: Session = Depends(get_db)):
    inv = db.query(Invitation).filter(Invitation.token == invite_token).first()
    if not inv:
        raise HTTPException(404, "Invitation not found")
    workspace = db.query(Workspace).filter(Workspace.id == inv.workspace_id).first()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    expired = inv.expires_at < now
    if expired and inv.status == "pending":
        inv.status = "expired"
        db.commit()
    return {
        "id": inv.id,
        "email": inv.email,
        "role": inv.role,
        "status": "expired" if expired else inv.status,
        "expires_at": inv.expires_at.isoformat(),
        "workspace_id": str(inv.workspace_id),
        "workspace_name": workspace.name if workspace else "Workspace",
    }


@router.post("/{invite_token}/accept", response_model=SessionResponse)
def accept_invitation(
    invite_token: str,
    response: Response,
    db: Session = Depends(get_db),
    session=Depends(get_current_session),
):
    inv = db.query(Invitation).filter(
        Invitation.token == invite_token,
        Invitation.status == "pending",
    ).first()
    if not inv:
        raise HTTPException(404, "Invitation not found or already used")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if inv.expires_at < now:
        inv.status = "expired"
        db.commit()
        raise HTTPException(400, "Invitation expired")

    user = db.query(User).filter(User.id == session.user_id).first()
    if not user:
        raise HTTPException(401, "Session user not found")
    if user.email.strip().lower() != inv.email.strip().lower():
        raise HTTPException(403, "This invitation is for a different account")

    existing = db.query(Membership).filter(
        Membership.workspace_id == inv.workspace_id,
        Membership.user_id == user.id,
    ).first()
    if not existing:
        db.add(Membership(workspace_id=inv.workspace_id, user_id=user.id, role=inv.role))

    inv.status = "accepted"
    db.commit()
    workspace = db.query(Workspace).filter(Workspace.id == inv.workspace_id).first()
    if not workspace:
        raise HTTPException(404, "Workspace not found")
    return _create_session(user, db, response, workspace=workspace)
