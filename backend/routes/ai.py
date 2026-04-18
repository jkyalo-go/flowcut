import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from contracts.ai import (
    AIProviderConfigResponse,
    AIProviderConfigUpdate,
    AIProviderCredentialCreate,
    AIProviderCredentialResponse,
    AIProviderOption,
    AISettingsUpdate,
    AIUsageRecordResponse,
)
from contracts.generation import (
    VideoGenerateRequest,
    VideoTaskResponse,
)
from database import get_db
from dependencies import get_current_workspace, get_system_admin
from domain.ai import AIProviderConfig, AIProviderCredential, AIUsageRecord
from domain.enterprise import OnboardingState
from services.ai_registry import registry
from services.video_generation import generate_with_dashscope, generate_with_vertex, get_dashscope_task

router = APIRouter()


@router.get("/providers", response_model=list[AIProviderOption])
def list_providers(workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    return registry.provider_catalog(db)


@router.get("/credentials", response_model=list[AIProviderCredentialResponse])
def list_credentials(workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    return db.query(AIProviderCredential).filter(AIProviderCredential.workspace_id == workspace.id).all()


@router.post("/credentials", response_model=AIProviderCredentialResponse)
def create_credential(
    body: AIProviderCredentialCreate,
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    provider = "vertex" if body.provider == "gemini" else body.provider
    row = AIProviderCredential(
        workspace_id=workspace.id,
        provider=provider,
        credential_source="byok",
        label=body.label,
        api_key=body.api_key,
        allowed_models=json.dumps(body.allowed_models),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/admin/providers", response_model=list[AIProviderConfigResponse])
def admin_list_provider_configs(_admin=Depends(get_system_admin), db: Session = Depends(get_db)):
    return db.query(AIProviderConfig).order_by(AIProviderConfig.provider, AIProviderConfig.model_key).all()


@router.put("/admin/providers/{config_id}", response_model=AIProviderConfigResponse)
def admin_update_provider_config(
    config_id: str,
    body: AIProviderConfigUpdate,
    _admin=Depends(get_system_admin),
    db: Session = Depends(get_db),
):
    row = db.query(AIProviderConfig).filter(AIProviderConfig.id == config_id).first()
    if not row:
        raise HTTPException(404, "Provider config not found")
    if body.display_name is not None:
        row.display_name = body.display_name
    if body.task_types is not None:
        row.task_types = json.dumps(body.task_types)
    if body.capabilities is not None:
        row.capabilities_json = json.dumps(body.capabilities)
    if body.enabled is not None:
        row.enabled = 1 if body.enabled else 0
    if body.api_key is not None:
        row.api_key = body.api_key
    if body.base_url is not None:
        row.base_url = body.base_url
    if body.config is not None:
        row.config_json = json.dumps(body.config)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/credentials/{credential_id}")
def delete_credential(credential_id: str, workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    row = db.query(AIProviderCredential).filter(
        AIProviderCredential.id == credential_id,
        AIProviderCredential.workspace_id == workspace.id,
    ).first()
    if not row:
        raise HTTPException(404, "Credential not found")
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.put("/settings")
def update_ai_settings(body: AISettingsUpdate, workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    workspace.ai_policy = json.dumps({
        "default_provider_by_task": body.default_provider_by_task,
        "allowed_providers": body.allowed_providers,
        "spend_cap_usd": body.spend_cap_usd,
        "fallback_chains": body.fallback_chains,
    })
    db.commit()
    onboarding = db.query(OnboardingState).filter(OnboardingState.workspace_id == workspace.id).first()
    if onboarding:
        try:
            checklist = json.loads(onboarding.checklist_json or "{}")
        except Exception:
            checklist = {}
        checklist["provider_policy_configured"] = True
        onboarding.checklist_json = json.dumps(checklist)
        db.commit()
    return {"ok": True, "ai_policy": workspace.ai_policy}


@router.get("/usage", response_model=list[AIUsageRecordResponse])
def list_usage(workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    rows = db.query(AIUsageRecord).filter(
        AIUsageRecord.workspace_id == workspace.id
    ).order_by(AIUsageRecord.id.desc()).limit(200).all()
    return rows


@router.post("/video/generate", response_model=VideoTaskResponse)
def generate_video(body: VideoGenerateRequest, workspace=Depends(get_current_workspace)):
    if body.provider == "vertex":
        return generate_with_vertex(body)
    if body.provider == "dashscope":
        return generate_with_dashscope(body)
    raise HTTPException(400, "Unsupported video provider")


@router.get("/video/tasks/{task_id}", response_model=VideoTaskResponse)
def get_video_task(task_id: str, provider: str):
    if provider == "dashscope":
        return get_dashscope_task(task_id)
    raise HTTPException(400, "Task polling is currently supported for DashScope video jobs only")
