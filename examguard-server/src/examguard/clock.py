"""Single source of 'now' for business rules, so tests can pin time."""
from datetime import datetime, timezone

_fixed: datetime | None = None


def now() -> datetime:
    return _fixed if _fixed is not None else datetime.now(timezone.utc)


def set_now(value: datetime | None) -> None:
    global _fixed
    if value is not None and value.tzinfo is None:
        raise ValueError("clock value must be timezone-aware")
    _fixed = value
