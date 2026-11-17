"""Hierarchical settings (PRD §8.5, §24.1): platform default → organization → exam.

* The most specific level wins.
* Integer settings are bounded by platform `bounds`; string settings by `choices`.
* Overrides that fall outside (possibly tightened) bounds are clamped at resolution time.
* Shortening a retention period requires an explicit confirmation flag.
"""
from typing import Any

from sqlalchemy.orm import Session

from .errors import conflict, invalid
from .models import Exam, Organization, PlatformSettings

RETENTION_KEYS = ("retention_dismissed_days", "retention_default_days", "retention_identity_days")
# Keys that make sense at exam level (identity-check defaults are org-level only).
EXAM_LEVEL_KEYS = RETENTION_KEYS + (
    "reentry_approval_threshold_minutes",
    "interruption_threshold_seconds",
    "offline_release_grace_minutes",
)


def platform(db: Session) -> dict[str, Any]:
    return db.get(PlatformSettings, 1).settings


def _clamp(key: str, value: Any, ps: dict[str, Any]) -> Any:
    if key in ps.get("bounds", {}):
        lo, hi = ps["bounds"][key]
        return max(lo, min(hi, int(value)))
    if key in ps.get("choices", {}) and value not in ps["choices"][key]:
        return ps["defaults"][key]
    return value


def resolve(db: Session, org: Organization, exam: Exam | None = None) -> dict[str, dict[str, Any]]:
    ps = platform(db)
    out: dict[str, dict[str, Any]] = {}
    for key, default in ps["defaults"].items():
        value, source = default, "platform"
        if key in (org.settings or {}):
            value, source = org.settings[key], "organization"
        if exam is not None and key in (exam.settings or {}):
            value, source = exam.settings[key], "exam"
        clamped = _clamp(key, value, ps)
        out[key] = {"value": clamped, "source": source, "clamped": clamped != value}
    return out


def value(db: Session, org: Organization, key: str, exam: Exam | None = None) -> Any:
    return resolve(db, org, exam)[key]["value"]


def validate_overrides(db: Session, overrides: dict[str, Any], *, allowed: tuple[str, ...] | None) -> None:
    ps = platform(db)
    errors = []
    for key, v in overrides.items():
        if key not in ps["defaults"] or (allowed is not None and key not in allowed):
            errors.append({"key": key, "problem": "unknown or not allowed at this level"})
            continue
        if v is None:
            continue  # None removes the override
        if key in ps.get("bounds", {}):
            lo, hi = ps["bounds"][key]
            if not isinstance(v, int) or isinstance(v, bool) or not lo <= v <= hi:
                errors.append({"key": key, "problem": f"must be an integer between {lo} and {hi}"})
        elif key in ps.get("choices", {}):
            if v not in ps["choices"][key]:
                errors.append({"key": key, "problem": f"must be one of {ps['choices'][key]}"})
    if errors:
        raise invalid("INVALID_SETTINGS", "invalid settings", errors)


def merge(current: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    new = dict(current or {})
    for k, v in patch.items():
        if v is None:
            new.pop(k, None)
        else:
            new[k] = v
    return new


def check_retention_shortening(
    before: dict[str, dict[str, Any]], after: dict[str, dict[str, Any]], confirm: bool
) -> list[dict[str, Any]]:
    shortened = [
        {"key": k, "from": before[k]["value"], "to": after[k]["value"]}
        for k in RETENTION_KEYS
        if after[k]["value"] < before[k]["value"]
    ]
    if shortened and not confirm:
        raise conflict(
            "RETENTION_SHORTEN_CONFIRMATION_REQUIRED",
            "Shortening retention may delete data immediately; resend with confirm_shorten=true",
            shortened,
        )
    return shortened


def validate_platform_document(doc: dict[str, Any]) -> None:
    errors = []
    defaults, bounds, choices = doc.get("defaults", {}), doc.get("bounds", {}), doc.get("choices", {})
    for key, (lo, hi) in bounds.items():
        if not (isinstance(lo, int) and isinstance(hi, int) and lo <= hi):
            errors.append({"key": key, "problem": "bounds must be [min, max] integers"})
        elif key in defaults and not lo <= defaults[key] <= hi:
            errors.append({"key": key, "problem": "default outside bounds"})
    for key, opts in choices.items():
        if key in defaults and defaults[key] not in opts:
            errors.append({"key": key, "problem": "default not in choices"})
    for key in defaults:
        if key not in bounds and key not in choices:
            errors.append({"key": key, "problem": "every default needs bounds or choices"})
    if errors:
        raise invalid("INVALID_SETTINGS", "invalid platform settings", errors)
