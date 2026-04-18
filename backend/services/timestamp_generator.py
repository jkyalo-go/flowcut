import json
import logging

import anthropic

from config import ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)


def generate_timestamps(datetime_transcript: str, total_duration: float) -> list[dict]:
    """Use Claude to generate contextual time-of-day timestamps from transcript + clip datetimes."""
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    truncated = datetime_transcript[:30000]
    if len(datetime_transcript) > 30000:
        truncated += "\n\n[transcript truncated]"

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=(
            "You are a video editor assistant. Given a vlog transcript with timeline positions "
            "and the real-world recording timestamps of each clip, generate contextual time markers "
            "that help viewers follow the chronological flow of the vlog.\n\n"
            "Rules:\n"
            "- Use natural, casual labels like: \"monday morning\", \"later that afternoon\", "
            "\"the next day\", \"that evening\", \"tuesday\", \"day 3\"\n"
            "- Space markers naturally across the entire video from start to end — do not cluster them\n"
            "- The first marker should be near the start, the last marker should be in the final third\n"
            "- If a clip was recorded on a weekend (Saturday or Sunday), do NOT mention the day name — "
            "just use the time of day (e.g. \"that morning\", \"later that afternoon\", not \"saturday morning\")\n"
            "- Each marker should display for 4 seconds\n"
            "- Place each marker at a clip boundary where the recording time matches the label\n"
            "- Return lowercase text\n"
            "- start_time and end_time are in seconds (timeline position, not real-world time)\n"
            "- Do not place markers beyond the total video duration\n"
            f"- Total video duration is {total_duration:.1f} seconds\n\n"
            "Return ONLY a JSON array like:\n"
            '[{"text": "saturday morning", "start_time": 0.0, "end_time": 4.0}, ...]'
        ),
        messages=[{"role": "user", "content": truncated}],
    )

    raw = response.content[0].text.strip()

    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1])

    timestamps = json.loads(raw)

    validated = []
    for t in timestamps:
        if not isinstance(t, dict) or "text" not in t or "start_time" not in t or "end_time" not in t:
            continue
        start = max(0.0, float(t["start_time"]))
        end = min(float(t["end_time"]), total_duration)
        if end <= start:
            continue
        validated.append({
            "text": str(t["text"]),
            "start_time": round(start, 2),
            "end_time": round(end, 2),
        })

    logger.info("Generated %d timestamp markers for %.1fs video", len(validated), total_duration)
    return validated
