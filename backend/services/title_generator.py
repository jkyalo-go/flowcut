import json
import logging

from sqlalchemy.orm import Session

from domain.identity import Workspace
from services.ai_registry import registry

logger = logging.getLogger(__name__)


DEFAULT_DESCRIPTION_PROMPT = (
    "You are a video description writer. Write a compelling video description "
    "based on the transcript and title provided. Include:\n"
    "- A hook/summary in the first 2 lines\n"
    "- Key topics covered\n"
    "- A call to action\n\n"
    "Keep it under 300 words. Do not include timestamps or hashtags."
)


def _line_parser(text: str) -> list[str]:
    return [line.strip() for line in text.strip().splitlines() if line.strip()]


def generate_titles(db: Session, workspace: Workspace, transcript: str, count: int = 5) -> list[str]:
    truncated = transcript[:8000]
    if len(transcript) > 8000:
        truncated += "\n\n[transcript truncated]"
    result = registry.run_text_task(
        db,
        workspace,
        task_type="titles",
        prompt_builder=lambda provider, _model: (
            f"You are a {provider.value} title assistant. Generate exactly {count} engaging Flowcut-ready video titles. "
            "Return one title per line with no numbering.",
            truncated,
        ),
        parser=_line_parser,
    )
    logger.info("Generated %d title suggestions", len(result))
    return result[:count]


def generate_description(
    db: Session,
    workspace: Workspace,
    transcript: str,
    title: str,
    system_prompt: str | None = None,
) -> str:
    truncated = transcript[:8000]
    if len(transcript) > 8000:
        truncated += "\n\n[transcript truncated]"
    result = registry.run_text_task(
        db,
        workspace,
        task_type="description",
        prompt_builder=lambda _provider, _model: (
            system_prompt or DEFAULT_DESCRIPTION_PROMPT,
            f"Title: {title}\n\nTranscript:\n{truncated}",
        ),
        parser=lambda text: text.strip(),
    )
    logger.info("Generated video description")
    return result


def generate_tags(db: Session, workspace: Workspace, transcript: str, title: str, count: int = 10) -> list[str]:
    truncated = transcript[:4000]
    if len(transcript) > 4000:
        truncated += "\n\n[transcript truncated]"
    result = registry.run_text_task(
        db,
        workspace,
        task_type="tags",
        prompt_builder=lambda _provider, _model: (
            f"Generate exactly {count} relevant tags for this video. Return one tag per line.",
            f"Title: {title}\n\nTranscript:\n{truncated}",
        ),
        parser=_line_parser,
    )
    logger.info("Generated %d tags", len(result))
    return result[:count]


def generate_overlay_plan(db: Session, workspace: Workspace, timestamped_transcript: str, total_duration: float) -> list[dict]:
    truncated = timestamped_transcript[:30000]
    if len(timestamped_transcript) > 30000:
        truncated += "\n\n[transcript truncated]"
    raw = registry.run_text_task(
        db,
        workspace,
        task_type="titles",
        prompt_builder=lambda _provider, _model: (
            "You are a video editor assistant. Return only a JSON array of title overlays with fields text,start_time,end_time.",
            (
                f"Create 3-7 lowercase section title overlays for this vlog transcript. "
                f"Total duration: {total_duration:.1f}s. "
                "Each title should last about 5 seconds.\n\n"
                f"{truncated}"
            ),
        ),
        parser=lambda text: text.strip(),
    )
    text = raw
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1])
    titles = json.loads(text)
    validated = []
    for item in titles:
        if not isinstance(item, dict):
            continue
        if not {"text", "start_time", "end_time"}.issubset(item):
            continue
        start = max(0.0, float(item["start_time"]))
        end = min(float(item["end_time"]), total_duration)
        if end <= start:
            continue
        validated.append({
            "text": str(item["text"]),
            "start_time": round(start, 2),
            "end_time": round(end, 2),
        })
    return validated
