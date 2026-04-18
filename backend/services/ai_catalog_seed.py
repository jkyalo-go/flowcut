"""Idempotent seeder for ai_provider_configs.

Populates the provider catalog on first boot so the /api/ai/admin/providers
endpoint returns a meaningful list. Running this on every boot is safe —
existing rows (matched by model_key) are left alone.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from domain.ai import AIProviderConfig

logger = logging.getLogger(__name__)

# (provider, model_key, display_name, task_types)
_CATALOG: list[tuple[str, str, str, list[str]]] = [
    ("anthropic", "claude-sonnet-4-20250514", "Claude Sonnet 4", ["titles", "description", "tags", "edit_planning", "style_critique"]),
    ("anthropic", "claude-3-5-haiku-latest", "Claude Haiku 3.5", ["titles", "description", "tags"]),
    ("openai", "gpt-4o", "GPT-4o", ["titles", "description", "tags"]),
    ("openai", "gpt-4o-mini", "GPT-4o mini", ["titles", "description", "tags"]),
    ("vertex", "gemini-2.5-flash", "Gemini 2.5 Flash", ["thumbnail", "titles", "description"]),
    ("vertex", "gemini-2.5-pro", "Gemini 2.5 Pro", ["thumbnail", "edit_planning"]),
    ("deepgram", "nova-3", "Deepgram Nova 3", ["transcription"]),
    ("dashscope", "wan2.7-i2v-turbo", "Wan 2.7 i2v Turbo", ["broll"]),
    ("dashscope", "wan2.7-t2v-turbo", "Wan 2.7 t2v Turbo", ["broll"]),
    ("dashscope", "wan2.7-v2v", "Wan 2.7 v2v", ["broll"]),
]


def seed_ai_catalog(db: Session) -> int:
    """Insert missing rows. Returns number of rows inserted."""
    existing = {row.model_key for row in db.query(AIProviderConfig.model_key).all()}
    inserted = 0
    for provider, model_key, display_name, task_types in _CATALOG:
        if model_key in existing:
            continue
        db.add(
            AIProviderConfig(
                provider=provider,
                model_key=model_key,
                display_name=display_name,
                task_types=json.dumps(task_types),
                enabled=1,
            )
        )
        inserted += 1
    if inserted:
        db.commit()
        logger.info("seeded %d rows into ai_provider_configs", inserted)
    return inserted
