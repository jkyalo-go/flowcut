import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from common.time import ensure_utc, utc_now
from config import FRONTEND_URL
from contracts.identity import InvitationCreateRequest, SessionResponse
from database import get_db
from dependencies import get_current_session
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


def _is_expired(inv: Invitation) -> bool:
    return ensure_utc(inv.expires_at) < utc_now()


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
        expires_at=utc_now() + timedelta(days=7),
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
    """Read-only preview. Does not mutate status. A background sweep handles expiry."""
    inv = db.query(Invitation).filter(Invitation.token == invite_token).first()
    if not inv:
        raise HTTPException(404, "Invitation not found")
    workspace = db.query(Workspace).filter(Workspace.id == inv.workspace_id).first()
    effective_status = "expired" if _is_expired(inv) and inv.status == "pending" else inv.status
    return {
        "id": inv.id,
        "email": inv.email,
        "role": inv.role,
        "status": effective_status,
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
    # SELECT ... FOR UPDATE on the invitation row to serialize concurrent accepts.
    # SQLite ignores with_for_update(), but the UNIQUE(workspace_id, user_id)
    # constraint on memberships is the real backstop.
    inv = (
        db.query(Invitation)
        .filter(
            Invitation.token == invite_token,
            Invitation.status == "pending",
        )
        .with_for_update()
        .first()
    )
    if not inv:
        raise HTTPException(404, "Invitation not found or already used")
    if _is_expired(inv):
        inv.status = "expired"
        db.commit()
        raise HTTPException(400, "Invitation expired")

    user = db.query(User).filter(User.id == session.user_id).first()
    if not user:
        raise HTTPException(401, "Session user not found")
    if user.email.strip().lower() != inv.email.strip().lower():
        raise HTTPException(403, "This invitation is for a different account")

    # Idempotent membership creation: rely on UNIQUE(workspace_id, user_id).
    try:
        db.add(Membership(workspace_id=inv.workspace_id, user_id=user.id, role=inv.role))
        db.flush()
    except IntegrityError:
        db.rollback()
        # Already a member — still proceed to accept and issue session.
        db.add(inv)  # re-attach after rollback
        inv = (
            db.query(Invitation)
            .filter(Invitation.token == invite_token)
            .first()
        )
        if not inv:
            raise HTTPException(404, "Invitation disappeared mid-flight")  # noqa: B904

    inv.status = "accepted"
    db.commit()
    workspace = db.query(Workspace).filter(Workspace.id == inv.workspace_id).first()
    if not workspace:
        raise HTTPException(404, "Workspace not found")
    return _create_session(user, db, response, workspace=workspace)
