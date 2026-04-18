from datetime import UTC, datetime

from common.time import ensure_utc, utc_now


def test_utc_now_is_timezone_aware():
    now = utc_now()
    assert now.tzinfo is not None
    assert now.utcoffset().total_seconds() == 0


def test_ensure_utc_on_naive_datetime():
    naive = datetime(2026, 4, 18, 12, 0, 0)
    aware = ensure_utc(naive)
    assert aware.tzinfo is UTC


def test_ensure_utc_on_aware_datetime_passthrough():
    aware = datetime(2026, 4, 18, 12, 0, 0, tzinfo=UTC)
    assert ensure_utc(aware) is aware


def test_ensure_utc_none_returns_none():
    assert ensure_utc(None) is None
