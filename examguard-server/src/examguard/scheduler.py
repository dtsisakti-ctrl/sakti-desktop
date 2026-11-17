"""Time-driven transitions (PRD §9, §10.3, §17.6).

``tick()`` runs one pass; ``run_forever()`` loops it. Each step runs in its own transaction in
the ``system`` context and locks rows with ``FOR UPDATE SKIP LOCKED``, so several server
instances (or an instance plus a CLI runner) can tick concurrently without double-processing
and without waiting on rows a staff action is holding.

Steps, in order:
  1. exams      READY -> RUNNING               window_start reached
  2. attempts   NOT_STARTED -> NO_SHOW          now > latest_start
  3. attempts   * -> EXPIRED                    now >= deadline (not while PAUSED + PAUSE_TIMER)
  4. attempts   ACTIVE -> INTERRUPTED           no heartbeat for interruption_threshold
  5. exams      RUNNING -> CLOSED               latest_start passed and every attempt final
  6. webhooks   deliver due rows of the webhook outbox (PRD §16.6)
"""
import logging
import threading
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, select

from . import clock, sessions, settings_service, state
from .db import transaction
from .models import Attempt, DeviceSession, Enrollment, Exam, Organization
from .services import lifecycle

log = logging.getLogger("examguard.scheduler")
BATCH = 500


def _exams_to_run(db, now):
    return list(db.scalars(select(Exam).where(Exam.status == "READY", Exam.window_start <= now)
                           .order_by(Exam.window_start).limit(BATCH).with_for_update(skip_locked=True)))


def _no_shows(db, now):
    return list(db.scalars(
        select(Attempt).join(Enrollment, Enrollment.id == Attempt.enrollment_id)
        .join(Exam, Exam.id == Enrollment.exam_id)
        .where(Attempt.status == state.NOT_STARTED, Exam.status.in_(("READY", "RUNNING")),
               Exam.latest_start < now)
        .limit(BATCH).with_for_update(of=Attempt, skip_locked=True)))


def _expired(db, now):
    return list(db.scalars(
        select(Attempt).where(
            Attempt.status.in_(state.HAS_DEADLINE), Attempt.deadline <= now,
            ~and_(Attempt.status == state.PAUSED, Attempt.pause_timer_mode == "PAUSE_TIMER"))
        .limit(BATCH).with_for_update(skip_locked=True)))


def _silent(db, now, min_threshold: int):
    seen = func.coalesce(DeviceSession.last_heartbeat_at, DeviceSession.activated_at)
    return db.execute(
        select(Attempt, DeviceSession, Exam)
        .join(DeviceSession, and_(DeviceSession.attempt_id == Attempt.id, DeviceSession.status == "ACTIVE"))
        .join(Enrollment, Enrollment.id == Attempt.enrollment_id)
        .join(Exam, Exam.id == Enrollment.exam_id)
        .where(Attempt.status == state.ACTIVE, seen < now - timedelta(seconds=min_threshold))
        .limit(BATCH).with_for_update(of=Attempt, skip_locked=True)).all()


def _exams_to_close(db, now):
    return list(db.scalars(select(Exam).where(Exam.status == "RUNNING", Exam.latest_start < now)
                           .limit(BATCH).with_for_update(skip_locked=True)))


def tick(now: datetime | None = None) -> dict[str, int]:
    now = now or clock.now()
    counts = {"running": 0, "no_show": 0, "expired": 0, "interrupted": 0, "closed": 0}

    with transaction("system") as db:
        for exam in _exams_to_run(db, now):
            counts["running"] += lifecycle.mark_running(db, exam, now)

    with transaction("system") as db:
        for a in _no_shows(db, now):
            state.apply(db, a, "NO_SHOW", actor_kind="system", actor_id=None, now=now)
            a.ended_at = now
            counts["no_show"] += 1

    with transaction("system") as db:
        for a in _expired(db, now):
            state.apply(db, a, "EXPIRE", actor_kind="system", actor_id=None, now=now,
                        data={"deadline": a.deadline.isoformat()})
            a.ended_at = now
            counts["expired"] += 1

    with transaction("system") as db:
        ps = settings_service.platform(db)
        min_threshold = ps["bounds"]["interruption_threshold_seconds"][0]
        thresholds: dict[Any, int] = {}
        for a, ds, exam in _silent(db, now, min_threshold):
            if exam.id not in thresholds:
                thresholds[exam.id] = settings_service.value(
                    db, db.get(Organization, exam.org_id), "interruption_threshold_seconds", exam)
            seen = sessions.last_seen(ds)
            if (now - seen).total_seconds() > thresholds[exam.id]:
                state.apply(db, a, "INTERRUPT", actor_kind="system", actor_id=None, now=now,
                            data={"last_seen_at": seen.isoformat(), "device_session_id": str(ds.id)})
                counts["interrupted"] += 1

    with transaction("system") as db:
        for exam in _exams_to_close(db, now):
            counts["closed"] += lifecycle.try_close(db, exam, now)

    from . import webhooks
    wh = webhooks.deliver_due(now)
    counts["webhooks_delivered"], counts["webhooks_failed"] = wh["delivered"], wh["failed"]

    if any(counts.values()):
        log.info("scheduler tick %s", counts)
    return counts


def run_forever(interval: float = 2.0, stop: threading.Event | None = None) -> None:
    stop = stop or threading.Event()
    while not stop.is_set():
        try:
            tick()
        except Exception:  # keep ticking; the next pass retries
            log.exception("scheduler tick failed")
        stop.wait(interval)


def start_background(interval: float = 2.0) -> threading.Event:
    stop = threading.Event()
    threading.Thread(target=run_forever, args=(interval, stop), name="examguard-scheduler", daemon=True).start()
    return stop
