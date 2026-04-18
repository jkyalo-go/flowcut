from datetime import UTC, datetime


def utc_now() -> datetime:
    """Timezone-aware UTC now. Use instead of datetime.utcnow()."""
    return datetime.now(UTC)


def ensure_utc(value: datetime | None) -> datetime | None:
    """Coerce a naive datetime to timezone-aware UTC. Passthrough for aware."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
