from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Callable

import anthropic
from google import genai
from sqlalchemy.orm import Session

from config import ANTHROPIC_API_KEY, GOOGLE_API_KEY, VERTEX_LOCATION, VERTEX_PROJECT_ID
from domain.ai import AIProviderConfig, AIProviderCredential, AIUsageRecord
from domain.shared import AIProvider, AIUsageStatus, CredentialSource

logger = logging.getLogger(__name__)


DEFAULT_PROVIDER_MODELS: dict[str, list[str]] = {
    AIProvider.ANTHROPIC.value: ["claude-sonnet-4-20250514", "claude-3-5-haiku-latest"],
    AIProvider.VERTEX.value: ["gemini-2.5-flash", "gemini-2.5-pro"],
    AIProvider.GEMINI.value: ["gemini-2.5-flash", "gemini-2.5-pro"],
    AIProvider.DEEPGRAM.value: ["nova-3"],
    AIProvider.DASHSCOPE.value: ["wan2.7-i2v-turbo", "wan2.7-t2v-turbo", "wan2.7-v2v"],
}


TASK_PROVIDER_DEFAULTS = {
    "transcription": AIProvider.DEEPGRAM,
    "titles": AIProvider.ANTHROPIC,
    "description": AIProvider.ANTHROPIC,
    "tags": AIProvider.ANTHROPIC,
    "thumbnail": AIProvider.VERTEX,
    "broll": AIProvider.DASHSCOPE,
}


@dataclass
class AIResult:
    content: str | list[str] | tuple[str, list[dict]]
    provider: AIProvider
    model: str
    credential_source: CredentialSource
    request_units: float | None = None
    response_units: float | None = None
    cost_estimate: float | None = None


class AIProviderRegistry:
    def __init__(self):
        self._anthropic_client: anthropic.Anthropic | None = None
        self._gemini_client: genai.Client | None = None

    def provider_catalog(self, db: Session | None = None) -> list[dict]:
        if db is None:
            providers = [AIProvider.ANTHROPIC.value, AIProvider.VERTEX.value, AIProvider.DEEPGRAM.value, AIProvider.DASHSCOPE.value]
            return [
                {
                    "provider": provider,
                    "task_types": [task for task, default in TASK_PROVIDER_DEFAULTS.items() if default.value == provider],
                    "models": DEFAULT_PROVIDER_MODELS[provider],
                }
                for provider in providers
            ]
        rows = db.query(AIProviderConfig).filter(AIProviderConfig.enabled == 1).all()
        grouped: dict[str, dict] = {}
        for row in rows:
            task_types = json.loads(row.task_types) if row.task_types else []
            grouped.setdefault(row.provider, {"provider": row.provider, "task_types": [], "models": []})
            grouped[row.provider]["task_types"] = sorted(set(grouped[row.provider]["task_types"] + task_types))
            grouped[row.provider]["models"].append(row.model_key)
        return list(grouped.values())

    def _workspace_ai_policy(self, workspace) -> dict:
        if not workspace.ai_policy:
            return {}
        try:
            return json.loads(workspace.ai_policy)
        except Exception:
            return {}

    def select_provider(self, db: Session, workspace, task_type: str) -> tuple[AIProvider, str, CredentialSource, str | None]:
        policy = self._workspace_ai_policy(workspace)
        preferred_model = policy.get("default_provider_by_task", {}).get(task_type)
        catalog_rows = db.query(AIProviderConfig).filter(AIProviderConfig.enabled == 1).all()
        matching_rows = []
        for row in catalog_rows:
            try:
                tasks = json.loads(row.task_types) if row.task_types else []
            except Exception:
                tasks = []
            if task_type in tasks:
                matching_rows.append(row)

        selected_row = None
        if preferred_model:
            selected_row = next((row for row in matching_rows if row.model_key == preferred_model), None)
        if selected_row is None and matching_rows:
            selected_row = matching_rows[0]

        if selected_row is None:
            provider = TASK_PROVIDER_DEFAULTS.get(task_type, AIProvider.ANTHROPIC)
            model = DEFAULT_PROVIDER_MODELS[provider.value][0]
            platform_api_key = None
        else:
            provider = AIProvider(selected_row.provider if selected_row.provider != AIProvider.GEMINI.value else AIProvider.VERTEX.value)
            model = selected_row.model_key
            platform_api_key = selected_row.api_key

        cred = db.query(AIProviderCredential).filter(
            AIProviderCredential.workspace_id == workspace.id,
            AIProviderCredential.provider == provider,
            AIProviderCredential.is_active == 1,
        ).order_by(AIProviderCredential.id.desc()).first()

        if cred:
            allowed_models = json.loads(cred.allowed_models) if cred.allowed_models else [model]
            model = model if model in allowed_models else allowed_models[0]
            return provider, model, CredentialSource.BYOK, cred.api_key

        return provider, model, CredentialSource.PLATFORM, platform_api_key

    def _get_anthropic_client(self, api_key: str | None = None) -> anthropic.Anthropic:
        key = api_key or ANTHROPIC_API_KEY
        if not key:
            raise RuntimeError("Anthropic API key is not configured")
        if api_key:
            return anthropic.Anthropic(api_key=key)
        if self._anthropic_client is None:
            self._anthropic_client = anthropic.Anthropic(api_key=key)
        return self._anthropic_client

    def _get_vertex_client(self, api_key: str | None = None) -> genai.Client:
        key = api_key or GOOGLE_API_KEY
        if not key and not VERTEX_PROJECT_ID:
            raise RuntimeError("Vertex AI is not configured")
        if api_key:
            return genai.Client(api_key=key)
        if self._gemini_client is None:
            if VERTEX_PROJECT_ID:
                self._gemini_client = genai.Client(
                    vertexai=True,
                    project=VERTEX_PROJECT_ID,
                    location=VERTEX_LOCATION,
                )
            else:
                self._gemini_client = genai.Client(api_key=key)
        return self._gemini_client

    def _record_usage(
        self,
        db: Session,
        workspace_id: str,
        task_type: str,
        provider: AIProvider,
        model: str,
        credential_source: CredentialSource,
        start_time: float,
        user_id: str | None = None,
        project_id: str | None = None,
        clip_id: str | None = None,
        request_units: float | None = None,
        response_units: float | None = None,
        cost_estimate: float | None = None,
        status: AIUsageStatus = AIUsageStatus.SUCCESS,
        error_message: str | None = None,
        metadata: dict | None = None,
    ) -> AIUsageRecord:
        row = AIUsageRecord(
            workspace_id=workspace_id,
            user_id=user_id,
            project_id=project_id,
            clip_id=clip_id,
            task_type=task_type,
            provider=provider,
            model=model,
            credential_source=credential_source,
            request_units=request_units,
            response_units=response_units,
            cost_estimate=cost_estimate,
            latency_ms=(time.time() - start_time) * 1000,
            status=status,
            error_message=error_message,
            correlation_id=uuid.uuid4().hex,
            metadata_json=json.dumps(metadata or {}),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    def run_text_task(
        self,
        db: Session,
        workspace,
        task_type: str,
        prompt_builder: Callable[[AIProvider, str], tuple[str | None, str]],
        parser: Callable[[str], str | list[str]],
        user_id: str | None = None,
        project_id: str | None = None,
        clip_id: str | None = None,
    ) -> str | list[str]:
        provider, model, credential_source, api_key = self.select_provider(db, workspace, task_type)
        start = time.time()
        system_prompt, user_prompt = prompt_builder(provider, model)
        try:
            if provider == AIProvider.ANTHROPIC:
                client = self._get_anthropic_client(api_key)
                response = client.messages.create(
                    model=model,
                    max_tokens=1024,
                    system=system_prompt or "",
                    messages=[{"role": "user", "content": user_prompt}],
                )
                text = response.content[0].text
                request_units = float(len(user_prompt))
                response_units = float(len(text))
            elif provider in {AIProvider.VERTEX, AIProvider.GEMINI}:
                client = self._get_vertex_client(api_key)
                payload = f"{system_prompt or ''}\n\n{user_prompt}".strip()
                response = client.models.generate_content(model=model, contents=payload)
                text = response.text
                request_units = float(len(payload))
                response_units = float(len(text or ""))
            else:
                raise RuntimeError(f"Provider {provider.value} does not support text task {task_type}")

            result = parser(text)
            self._record_usage(
                db,
                workspace_id=workspace.id,
                user_id=user_id,
                project_id=project_id,
                clip_id=clip_id,
                task_type=task_type,
                provider=provider,
                model=model,
                credential_source=credential_source,
                start_time=start,
                request_units=request_units,
                response_units=response_units,
                cost_estimate=(request_units + response_units) / 1_000_000,
            )
            return result
        except Exception as exc:
            logger.exception("AI text task failed")
            self._record_usage(
                db,
                workspace_id=workspace.id,
                user_id=user_id,
                project_id=project_id,
                clip_id=clip_id,
                task_type=task_type,
                provider=provider,
                model=model,
                credential_source=credential_source,
                start_time=start,
                status=AIUsageStatus.ERROR,
                error_message=str(exc),
            )
            raise


registry = AIProviderRegistry()
