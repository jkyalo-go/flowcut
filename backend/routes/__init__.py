from fastapi import HTTPException
from sqlalchemy.orm import Session

from domain.projects import Project


def require_project(project_id: str, workspace_id: str, db: Session) -> Project:
    project = db.query(Project).filter(
        Project.id == project_id, Project.workspace_id == workspace_id
    ).first()
    if not project:
        raise HTTPException(404, "Project not found")
    return project
