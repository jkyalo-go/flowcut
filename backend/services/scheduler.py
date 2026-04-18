from __future__ import annotations

from datetime import UTC, datetime, timedelta

DEFAULT_HEATMAP = {
    0: [0.1]*6 + [0.3, 0.4, 0.5, 0.5, 0.6, 0.6, 0.7, 0.8, 0.8, 0.7, 0.7, 0.9, 0.95, 0.9, 0.85, 0.8, 0.7, 0.5],
    1: [0.1]*6 + [0.3, 0.4, 0.5, 0.5, 0.6, 0.6, 0.7, 0.8, 0.8, 0.7, 0.7, 0.9, 0.95, 0.9, 0.85, 0.8, 0.7, 0.5],
    2: [0.1]*6 + [0.3, 0.4, 0.5, 0.5, 0.6, 0.6, 0.7, 0.8, 0.8, 0.7, 0.7, 0.9, 0.95, 0.9, 0.85, 0.8, 0.7, 0.5],
    3: [0.1]*6 + [0.3, 0.4, 0.5, 0.5, 0.6, 0.6, 0.7, 0.8, 0.8, 0.7, 0.7, 0.9, 0.95, 0.9, 0.85, 0.8, 0.7, 0.5],
    4: [0.1]*6 + [0.3, 0.4, 0.5, 0.5, 0.6, 0.6, 0.7, 0.8, 0.85, 0.85, 0.8, 0.95, 1.0, 0.95, 0.9, 0.85, 0.8, 0.6],
    5: [0.2]*5 + [0.4, 0.5, 0.6, 0.65, 0.7, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0, 0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.6, 0.6],
    6: [0.2]*5 + [0.4, 0.5, 0.6, 0.65, 0.7, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0, 0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.6, 0.6],
}
assert all(len(v) == 24 for v in DEFAULT_HEATMAP.values()), "All heatmap days must have 24 hours"


def score_slot(
    platform: str,
    day_of_week: int,
    hour: int,
    heatmap: dict,
    content_pillar: str,
    pillar_targets: dict[str, float],
    current_pillar_counts: dict[str, int],
    total_scheduled: int,
    recently_scheduled_hours: list[int],
    min_spacing_hours: int = 4,
) -> float:
    day_heatmap = heatmap.get(day_of_week, [0.5] * 24)
    hour = min(hour, len(day_heatmap) - 1)
    audience_score = day_heatmap[hour]

    target = pillar_targets.get(content_pillar, 0)
    if total_scheduled > 0 and target > 0:
        current_ratio = current_pillar_counts.get(content_pillar, 0) / total_scheduled
        balance_penalty = max(0.0, abs(current_ratio - target) * 2)
    else:
        balance_penalty = 0.0

    spacing_penalty = 0.0
    for scheduled_hour in recently_scheduled_hours:
        if abs(scheduled_hour - hour) < min_spacing_hours:
            spacing_penalty = 0.4
            break

    raw = audience_score * 0.60 - balance_penalty * 0.25 - spacing_penalty * 0.15
    return max(0.0, min(1.0, raw))


def find_gaps(
    platform: str,
    scheduled_slots: list[dict],
    window_days: int = 14,
    min_audience_score: float = 0.7,
    heatmap: dict | None = None,
) -> list[dict]:
    if heatmap is None:
        heatmap = DEFAULT_HEATMAP
    scheduled_dts = {s["scheduled_at"] for s in scheduled_slots}
    now = datetime.now(UTC).replace(tzinfo=None)
    gaps = []

    for day_offset in range(window_days):
        day = now + timedelta(days=day_offset)
        dow = day.weekday()
        day_heatmap = heatmap.get(dow, [0.5] * 24)

        for hour, activity in enumerate(day_heatmap):
            if activity < min_audience_score:
                continue
            slot_dt = day.replace(hour=hour, minute=0, second=0, microsecond=0)
            if slot_dt <= now:
                continue
            if any(abs((slot_dt - s).total_seconds()) < 4 * 3600 for s in scheduled_dts):
                continue
            gaps.append({"datetime": slot_dt.isoformat(), "platform": platform, "audience_score": round(activity, 2)})

    return sorted(gaps, key=lambda g: g["audience_score"], reverse=True)[:20]
