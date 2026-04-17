import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from dependencies import get_current_session
from domain.identity import Invitation, Membership, User

router = APIRouter(prefix="/invitations", tags=["invitations"])


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
    payload: dict,
    db: Session = Depends(get_db),
    session=Depends(get_current_session),
):
    _require_owner_or_admin(session, db)
    email = payload.get("email")
    if not email:
        raise HTTPException(400, "email is required")
    role = payload.get("role", "editor")
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
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if inv.expires_at < now:
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
