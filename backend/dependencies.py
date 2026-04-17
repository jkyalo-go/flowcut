from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from domain.identity import AdminUser, AuthSession, Membership, User, Workspace


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    prefix = "Bearer "
    if authorization.startswith(prefix):
        return authorization[len(prefix):].strip()
    return authorization.strip()


def get_current_session(
    authorization: str | None = Header(default=None),
    x_flowcut_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> AuthSession:
    token = x_flowcut_token or _extract_bearer_token(authorization)
    if not token:
        raise HTTPException(401, "Missing authorization token")

    session = db.query(AuthSession).filter(AuthSession.token == token).first()
    if not session:
        raise HTTPException(401, "Invalid session token")
    return session


def get_current_user(
    session: AuthSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> User:
    user = db.query(User).filter(User.id == session.user_id).first()
    if not user:
        raise HTTPException(401, "User not found")
    return user


def get_system_admin(
    user: User = Depends(get_current_user),
) -> User:
    if not isinstance(user, AdminUser):
        raise HTTPException(403, "System admin access required")
    return user


def get_current_workspace(
    session: AuthSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> Workspace:
    workspace = db.query(Workspace).filter(Workspace.id == session.workspace_id).first()
    if not workspace:
        raise HTTPException(401, "Workspace not found")
    membership = db.query(Membership).filter(
        Membership.workspace_id == workspace.id,
        Membership.user_id == session.user_id,
    ).first()
    if not membership:
        raise HTTPException(403, "You do not have access to this workspace")
    return workspace
