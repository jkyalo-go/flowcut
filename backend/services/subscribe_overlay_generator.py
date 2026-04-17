import json
import logging
import anthropic

from config import ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)


def generate_subscribe_overlays(timestamped_transcript: str, total_duration: float) -> list[dict]:
    """Use Claude to pick 2 moments for a subscribe text overlay."""
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    truncated = timestamped_transcript[:30000]
    if len(timestamped_transcript) > 30000:
        truncated += "\n\n[transcript truncated]"

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=512,
        system=(
            "You are a video editor assistant. Given a timestamped vlog transcript, pick exactly "
            "2 moments where a 'subscribe' text overlay should briefly appear. The overlay slides "
            "up from the bottom and stays for about 4 seconds.\n\n"
            "Rules:\n"
            "- Pick exactly 2 moments\n"
            "- The first moment should be in the first ~25% of the video\n"
            "- The second moment should be in the last ~25% of the video\n"
            "- Choose natural pauses, transitions, or moments between sentences — never mid-sentence\n"
            "- Each overlay displays for exactly 4 seconds\n"
            "- The text is always \"subscribe\"\n"
            "- start_time and end_time are in seconds\n"
            "- Do not place overlays beyond the total video duration\n"
            f"- Total video duration is {total_duration:.1f} seconds\n\n"
            "Return ONLY a JSON array like:\n"
            '[{"text": "subscribe", "start_time": 5.0, "end_time": 9.0}, '
            '{"text": "subscribe", "start_time": 55.0, "end_time": 59.0}]'
        ),
        messages=[{"role": "user", "content": truncated}],
    )

    raw = response.content[0].text.strip()

    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1])

    items = json.loads(raw)

    validated = []
    for t in items:
        if not isinstance(t, dict) or "start_time" not in t or "end_time" not in t:
            continue
        start = max(0.0, float(t["start_time"]))
        end = min(float(t["end_time"]), total_duration)
        if end <= start:
            continue
        validated.append({
            "text": t.get("text", "subscribe"),
            "start_time": round(start, 2),
            "end_time": round(end, 2),
        })

    logger.info("Generated %d subscribe overlays for %.1fs video", len(validated), total_duration)
    return validated
