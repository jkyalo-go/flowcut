from datetime import datetime

from services.scheduler import DEFAULT_HEATMAP, find_gaps, score_slot


def test_score_slot_returns_float_0_to_1():
    score = score_slot(
        platform="tiktok",
        day_of_week=1,
        hour=14,
        heatmap=DEFAULT_HEATMAP,
        content_pillar="gaming",
        pillar_targets={"gaming": 0.4},
        current_pillar_counts={"gaming": 2},
        total_scheduled=5,
        recently_scheduled_hours=[],
    )
    assert 0.0 <= score <= 1.0


def test_score_penalises_overloaded_pillar():
    score_over = score_slot(
        platform="tiktok", day_of_week=1, hour=14,
        heatmap=DEFAULT_HEATMAP,
        content_pillar="gaming",
        pillar_targets={"gaming": 0.4},
        current_pillar_counts={"gaming": 10},
        total_scheduled=10,
        recently_scheduled_hours=[],
    )
    score_ok = score_slot(
        platform="tiktok", day_of_week=1, hour=14,
        heatmap=DEFAULT_HEATMAP,
        content_pillar="gaming",
        pillar_targets={"gaming": 0.4},
        current_pillar_counts={"gaming": 4},
        total_scheduled=10,
        recently_scheduled_hours=[],
    )
    assert score_over < score_ok


def test_score_penalises_recent_post_spacing():
    score_crowded = score_slot(
        platform="tiktok", day_of_week=1, hour=14,
        heatmap=DEFAULT_HEATMAP,
        content_pillar="vlog",
        pillar_targets={},
        current_pillar_counts={},
        total_scheduled=0,
        recently_scheduled_hours=[13],  # 1 hour ago
    )
    score_spaced = score_slot(
        platform="tiktok", day_of_week=1, hour=14,
        heatmap=DEFAULT_HEATMAP,
        content_pillar="vlog",
        pillar_targets={},
        current_pillar_counts={},
        total_scheduled=0,
        recently_scheduled_hours=[6],  # 8 hours ago
    )
    assert score_crowded < score_spaced


def test_find_gaps_returns_open_slots():
    gaps = find_gaps(
        platform="tiktok",
        scheduled_slots=[
            {"scheduled_at": datetime(2026, 4, 20, 10, 0)},
            {"scheduled_at": datetime(2026, 4, 20, 18, 0)},
        ],
        window_days=3,
        min_audience_score=0.6,
    )
    assert isinstance(gaps, list)
    for g in gaps:
        assert "datetime" in g
        assert "audience_score" in g
        assert g["audience_score"] >= 0.6
