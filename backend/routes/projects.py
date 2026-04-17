from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from dependencies import get_current_workspace
from contracts.projects import ProjectCreate, ProjectMetadataUpdate, ProjectResponse
from domain.projects import Project

router = APIRouter()


@router.post("", response_model=ProjectResponse)
def create_project(
    body: ProjectCreate,
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    if body.workspace_id != workspace.id:
        raise HTTPException(403, "Workspace mismatch")
    project = Project(
        workspace_id=workspace.id,
        name=body.name,
        intake_mode="upload",
        source_type="upload",
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id, Project.workspace_id == workspace.id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@router.get("", response_model=list[ProjectResponse])
def list_projects(workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    return db.query(Project).filter(Project.workspace_id == workspace.id).all()


@router.put("/{project_id}/metadata")
def update_metadata(project_id: str, body: ProjectMetadataUpdate, workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id, Project.workspace_id == workspace.id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    db.commit()
    return {"ok": True}


@router.delete("/{project_id}")
def delete_project(project_id: str, workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id, Project.workspace_id == workspace.id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    db.delete(project)
    db.commit()
    return {"ok": True}


