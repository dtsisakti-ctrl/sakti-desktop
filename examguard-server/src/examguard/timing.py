"""Exam timing rules (PRD §11). Pure functions: no database, no clock.

The server is the only time authority; every deadline stored and sent is absolute.
"""
from datetime import datetime, timedelta

from .models import Enrollment, Exam


def initial_deadline(exam: Exam, enrollment: Enrollment, started_at: datetime) -> datetime:
    """Deadline at the moment an attempt goes NOT_STARTED -> ACTIVE (§11.2).

    ``exam.extension_minutes`` (whole-exam extend, §11.3) is added on top, so candidates
    who start after an extension receive the same extra time as those already running.
    """
    accommodation = timedelta(minutes=enrollment.time_accommodation_minutes or 0)
    extension = timedelta(minutes=exam.extension_minutes or 0)
    window_limit = exam.window_end + accommodation
    if exam.duration_minutes:
        base = started_at + timedelta(minutes=exam.duration_minutes) + accommodation
        deadline = base if exam.late_start_policy == "FULL_DURATION" else min(base, window_limit)
    else:
        deadline = window_limit
    return deadline + extension


def deadline_after_resume(deadline: datetime, paused_at: datetime, resumed_at: datetime,
                          timer_mode: str | None) -> datetime:
    """PAUSE_TIMER shifts the deadline by the paused duration; KEEP_RUNNING leaves it (§11.4)."""
    if timer_mode == "PAUSE_TIMER" and resumed_at > paused_at:
        return deadline + (resumed_at - paused_at)
    return deadline


def timer_frozen(status: str, timer_mode: str | None) -> bool:
    """While PAUSED with PAUSE_TIMER the deadline does not run and the attempt cannot expire."""
    return status == "PAUSED" and timer_mode == "PAUSE_TIMER"


def remaining_seconds(deadline: datetime | None, now: datetime, *, status: str,
                      timer_mode: str | None, paused_at: datetime | None) -> int | None:
    if deadline is None:
        return None
    ref = paused_at if timer_frozen(status, timer_mode) and paused_at else now
    return max(int((deadline - ref).total_seconds()), 0)
