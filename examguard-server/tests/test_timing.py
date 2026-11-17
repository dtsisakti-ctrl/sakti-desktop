"""Deadline formulas (PRD §11.2–11.4). Pure functions, no database."""
from datetime import datetime, timezone
from types import SimpleNamespace as NS

from examguard import timing

T = lambda h, m=0: datetime(2026, 10, 12, h, m, tzinfo=timezone.utc)  # noqa: E731


def exam(duration=90, policy="FIXED_END", ext=0):
    return NS(window_start=T(9), window_end=T(10, 30), duration_minutes=duration,
              late_start_policy=policy, extension_minutes=ext)


def enr(acc=0):
    return NS(time_accommodation_minutes=acc)


def test_fixed_end_prd_example():
    # window 09:00–10:30, 90 minutes, start 09:20 -> 10:30, not 10:50
    assert timing.initial_deadline(exam(), enr(), T(9, 20)) == T(10, 30)


def test_fixed_end_on_time_start_gets_full_duration():
    assert timing.initial_deadline(exam(duration=60), enr(), T(9)) == T(10)


def test_full_duration_ignores_window_end():
    assert timing.initial_deadline(exam(policy="FULL_DURATION"), enr(), T(9, 20)) == T(10, 50)


def test_no_duration_uses_window_end():
    assert timing.initial_deadline(exam(duration=None), enr(), T(9, 20)) == T(10, 30)


def test_accommodation_extends_both_base_and_window_limit():
    assert timing.initial_deadline(exam(), enr(15), T(9)) == T(10, 45)
    assert timing.initial_deadline(exam(), enr(15), T(9, 20)) == T(10, 45)       # capped at window_end + 15
    assert timing.initial_deadline(exam(duration=None), enr(15), T(9, 20)) == T(10, 45)
    assert timing.initial_deadline(exam(policy="FULL_DURATION"), enr(15), T(9, 20)) == T(11, 5)


def test_exam_extension_applies_to_later_starters():
    assert timing.initial_deadline(exam(ext=10), enr(), T(9, 20)) == T(10, 40)
    assert timing.initial_deadline(exam(ext=10, policy="FULL_DURATION"), enr(), T(9, 20)) == T(11)


def test_resume_shifts_only_with_pause_timer():
    d, paused, resumed = T(10, 30), T(9, 40), T(9, 52)
    assert timing.deadline_after_resume(d, paused, resumed, "PAUSE_TIMER") == T(10, 42)
    assert timing.deadline_after_resume(d, paused, resumed, "KEEP_RUNNING") == d


def test_remaining_seconds_frozen_while_paused_with_pause_timer():
    d = T(10, 30)
    running = timing.remaining_seconds(d, T(10), status="ACTIVE", timer_mode=None, paused_at=None)
    assert running == 30 * 60
    frozen = timing.remaining_seconds(d, T(10, 10), status="PAUSED", timer_mode="PAUSE_TIMER", paused_at=T(10))
    assert frozen == 30 * 60
    ticking = timing.remaining_seconds(d, T(10, 10), status="PAUSED", timer_mode="KEEP_RUNNING", paused_at=T(10))
    assert ticking == 20 * 60
    assert timing.remaining_seconds(d, T(11), status="ACTIVE", timer_mode=None, paused_at=None) == 0
    assert timing.remaining_seconds(None, T(10), status="NOT_STARTED", timer_mode=None, paused_at=None) is None
