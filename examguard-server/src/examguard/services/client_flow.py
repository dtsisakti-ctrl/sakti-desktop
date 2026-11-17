"""Transitions triggered by the ExamGuard Client (PRD §10.3, §12.2, §18, §20).

Phase 1b exposes these as internal services, exercised by tests and by `examguard sim`.
Phase 1c wraps them in the signed client protocol (§17) without changing their rules.
"""
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit, clock, sessions, settings_service, state, timing
from ..errors import AppError, conflict, not_found
from ..models import Attempt, DeviceSession, Enrollment, Exam, Organization
from . import lifecycle

MAX_IDENTITY_REJECTIONS = 3


def _context(db: Session, attempt: Attempt) -> tuple[Enrollment, Exam]:
    enr = db.get(Enrollment, attempt.enrollment_id)
    return enr, db.get(Exam, enr.exam_id)


def _setting(db: Session, exam: Exam, key: str) -> int:
    return settings_service.value(db, db.get(Organization, exam.org_id), key, exam)


def _actor(enr: Enrollment) -> dict[str, Any]:
    return {"actor_kind": "candidate", "actor_id": enr.candidate_id}


def full_state(db: Session, attempt: Attempt) -> dict[str, Any]:
    """Body of the full state sync response (§17.7); Phase 1c signs it."""
    return {"attempt_id": attempt.id, "status": attempt.status, "state_version": attempt.state_version,
            "deadline": attempt.deadline, "server_time": clock.now(),
            "resume_allowed": attempt.status == state.ACTIVE, "identity_status": attempt.identity_status,
            "pause_timer_mode": attempt.pause_timer_mode}


def _expire(db: Session, attempt: Attempt, now: datetime, data: dict[str, Any] | None = None) -> None:
    state.apply(db, attempt, "EXPIRE", actor_kind="system", actor_id=None, now=now, data=data)
    attempt.ended_at = now


# ------------------------------------------------------------------ device session
def register_device(db: Session, attempt_id: UUID, *, public_key: str | None = None,
                    client_version: str | None = None, os_info: dict[str, Any] | None = None) -> dict[str, Any]:
    """Register a device session for an attempt (§18).

    NOT_STARTED            -> replaces any earlier session (nothing to protect yet)
    REOPENED / REINSTATED  -> new ACTIVE session, attempt -> ACTIVE (RELAUNCH)
    ACTIVE / INTERRUPTED   -> device change: new session PENDING_APPROVAL, attempt -> WAITING
    WAITING                -> replaces an earlier pending session
    PAUSED                 -> refused until the invigilator resumes
    """
    attempt = state.lock_attempt(db, attempt_id)
    enr, exam = _context(db, attempt)
    now = clock.now()
    new = DeviceSession(attempt_id=attempt.id, public_key=public_key, client_version=client_version,
                        os_info=os_info or {}, created_at=now, last_heartbeat_at=now)

    if attempt.status in state.FINAL:
        raise conflict("ATTEMPT_ENDED", f"attempt is {attempt.status}")
    if attempt.status == state.PAUSED:
        raise conflict("ATTEMPT_PAUSED", "attempt is paused; the invigilator must resume it first")

    if attempt.status == state.NOT_STARTED:
        if exam.status not in ("READY", "RUNNING"):
            raise conflict("EXAM_NOT_OPEN", f"exam is {exam.status}")
        opens = exam.checkin_open or exam.window_start
        if now < opens:
            raise conflict("CHECKIN_NOT_OPEN", "check-in has not opened yet", {"checkin_open": opens})
        if now > exam.latest_start:
            raise conflict("LATE_START_CLOSED", "the latest start time has passed")
        sessions.revoke_all(db, attempt.id, "REPLACED_BEFORE_START")
        new.status, new.activated_at = "ACTIVE", now
        db.add(new)
        db.flush()

    elif attempt.status in (state.REOPENED, state.REINSTATED):
        if attempt.deadline <= now:
            _expire(db, attempt, now)
            return {"device_session_id": None, "device_status": None, **full_state(db, attempt)}
        sessions.revoke_all(db, attempt.id, "RELAUNCH")
        new.status, new.activated_at = "ACTIVE", now
        db.add(new)
        db.flush()
        state.apply(db, attempt, "RELAUNCH", **_actor(enr), now=now,
                    data={"device_session_id": str(new.id)})

    elif attempt.status in (state.ACTIVE, state.INTERRUPTED):
        old = sessions.active(db, attempt.id)
        new.status = "PENDING_APPROVAL"
        db.add(new)
        db.flush()
        seen = sessions.last_seen(old)
        state.apply(db, attempt, "REQUIRE_APPROVAL", actor_kind="system", actor_id=None, now=now, data={
            "device_changed": True, "device_session_id": str(new.id),
            "last_seen_at": seen.isoformat() if seen else None,
            "gap_seconds": int((now - seen).total_seconds()) if seen else None, "cause": "DEVICE_CHANGED"})

    else:  # WAITING_FOR_INVIGILATOR
        prev = sessions.pending(db, attempt.id)
        if prev is not None:
            sessions.revoke(db, prev, "REPLACED_BY_NEWER_DEVICE")
        new.status = "PENDING_APPROVAL"
        db.add(new)
        db.flush()

    audit.record(db, org_id=attempt.org_id, actor_kind="candidate", actor_id=enr.candidate_id,
                 action="device_session.registered", target_type="attempt", target_id=attempt.id,
                 data={"device_session_id": new.id, "status": new.status, "client_version": client_version})
    return {"device_session_id": new.id, "device_status": new.status, **full_state(db, attempt)}


# ------------------------------------------------------------------ identity check (§12.5)
def submit_identity(db: Session, attempt_id: UUID) -> dict[str, Any]:
    attempt = state.lock_attempt(db, attempt_id)
    enr, exam = _context(db, attempt)
    if exam.identity_check != "MANUAL":
        raise conflict("IDENTITY_NOT_REQUIRED", "this exam does not use an identity check")
    if attempt.status not in (state.NOT_STARTED,):
        raise conflict("INVALID_STATE", f"attempt is {attempt.status}")
    if attempt.identity_status in ("PENDING", "APPROVED"):
        raise conflict("IDENTITY_ALREADY_SUBMITTED", f"identity check is {attempt.identity_status}")
    if attempt.identity_rejections >= MAX_IDENTITY_REJECTIONS:
        raise conflict("IDENTITY_RETRY_LIMIT", "maximum identity check attempts reached; contact the invigilator")
    if sessions.active(db, attempt.id) is None:
        raise conflict("NO_DEVICE_SESSION", "register a device session first")
    attempt.identity_status = "PENDING"
    audit.record(db, org_id=attempt.org_id, actor_kind="candidate", actor_id=enr.candidate_id,
                 action="attempt.identity_submitted", target_type="attempt", target_id=attempt.id)
    return {"attempt_id": attempt.id, "identity_status": attempt.identity_status}


# ------------------------------------------------------------------ start
def start(db: Session, attempt_id: UUID, device_session_id: UUID) -> dict[str, Any]:
    """NOT_STARTED -> ACTIVE after preflight + lockdown (+ approved identity check)."""
    peek = db.get(Attempt, attempt_id)
    if peek is None:
        raise not_found("attempt")
    enr = db.get(Enrollment, peek.enrollment_id)
    now = clock.now()
    exam = db.scalar(select(Exam).where(Exam.id == enr.exam_id).with_for_update())  # lock order: exam -> attempt
    attempt = state.lock_attempt(db, attempt_id)
    ds = db.get(DeviceSession, device_session_id)
    if ds is None or ds.attempt_id != attempt.id or ds.status != "ACTIVE":
        raise conflict("DEVICE_SESSION_INVALID", "device session is not the active session of this attempt")
    if not state.is_allowed("START", attempt.status):
        state.apply(db, attempt, "START", **_actor(enr))  # raises INVALID_TRANSITION
    if now < exam.window_start:
        raise conflict("START_NOT_YET_ALLOWED", "the exam window has not started", {"window_start": exam.window_start})
    if now > exam.latest_start:
        raise conflict("LATE_START_CLOSED", "the latest start time has passed")
    lifecycle.mark_running(db, exam, now)  # scheduler may not have ticked yet
    if exam.status != "RUNNING":
        raise conflict("EXAM_NOT_RUNNING", f"exam is {exam.status}")
    if exam.identity_check == "MANUAL" and attempt.identity_status != "APPROVED":
        raise AppError(403, "IDENTITY_NOT_APPROVED", "identity check has not been approved")
    deadline = timing.initial_deadline(exam, enr, now)
    attempt.started_at = now
    ds.last_heartbeat_at, ds.connection_closed_at = now, None   # a signed start request proves the client is alive (waiting time in check-in is not a gap)
    state.apply(db, attempt, "START", **_actor(enr), deadline=deadline, now=now,
                data={"device_session_id": str(ds.id)})
    return full_state(db, attempt)


# ------------------------------------------------------------------ heartbeat & reconnect (§17.6, §20)
# An interruption shorter than this is a blip (Wi-Fi roam, app restart within seconds): it still shows in the
# attempt history, but it does not open an UNMONITORED_INTERRUPTION incident (PRD v0.3.5 Q26).
MIN_INCIDENT_GAP_SECONDS = 10


def _lock_pair(db: Session, device_session_id: UUID) -> tuple[Attempt, DeviceSession]:
    """Lock order: attempt -> device session (same as heartbeat, commands and the scheduler)."""
    ds0 = db.get(DeviceSession, device_session_id)
    if ds0 is None:
        raise not_found("device session")
    attempt = state.lock_attempt(db, ds0.attempt_id)
    ds = db.scalar(select(DeviceSession).where(DeviceSession.id == device_session_id)
                   .with_for_update().execution_options(populate_existing=True))
    return attempt, ds


def _alive(db: Session, attempt: Attempt, ds: DeviceSession, now: datetime, prev_seen: datetime | None,
           cause: str | None) -> None:
    """The active device proved it is alive at `now`; the previous proof was `prev_seen`."""
    ds.last_heartbeat_at, ds.connection_closed_at = now, None
    if ds.status != "ACTIVE":
        return
    enr, exam = _context(db, attempt)
    gap = (now - prev_seen).total_seconds() if prev_seen else 0
    if attempt.status == state.ACTIVE and gap > _setting(db, exam, "interruption_threshold_seconds"):
        # The scheduler has not caught the gap yet; record it in the same order it would have.
        state.apply(db, attempt, "INTERRUPT", actor_kind="system", actor_id=None, now=now,
                    data={"last_seen_at": prev_seen.isoformat(), "detected": "on_reconnect"})
    if attempt.status == state.INTERRUPTED:
        _reconnect(db, attempt, exam, now, prev_seen, cause)


def heartbeat(db: Session, device_session_id: UUID, seq: int, *, cause: str | None = None) -> dict[str, Any]:
    attempt, ds = _lock_pair(db, device_session_id)
    if ds.status == "REVOKED":
        raise conflict("DEVICE_SESSION_REVOKED", "this device session was revoked")
    now = clock.now()
    if seq <= ds.last_heartbeat_seq:  # replayed / out of order: no effect
        return {"device_status": ds.status, "stale": True, **full_state(db, attempt)}
    prev_seen = sessions.last_seen(ds)
    ds.last_heartbeat_seq = seq
    _alive(db, attempt, ds, now, prev_seen, cause)
    db.flush()
    return {"device_status": ds.status, "stale": False, **full_state(db, attempt)}


def touch(db: Session, device_session_id: UUID) -> None:
    """Any signed request from the active device is proof of life (PRD v0.3.5 §17.6).

    After a closed connection the client may call sync, finish or upload events before its next heartbeat;
    those calls resume an INTERRUPTED attempt exactly as a heartbeat would.
    """
    attempt, ds = _lock_pair(db, device_session_id)
    if ds.status != "ACTIVE":
        return
    _alive(db, attempt, ds, clock.now(), sessions.last_seen(ds), None)
    db.flush()


def connection_closed(db: Session, device_session_id: UUID, seq_seen: int) -> bool:
    """The client's WebSocket closed while the server did not close it (PRD v0.3.5 §17.6).

    `seq_seen` is the last heartbeat seq this socket saw (or the seq when it opened). A higher seq means the
    client is already heartbeating on a newer connection, so this close is old news and changes nothing.
    Returns True when the attempt was interrupted.
    """
    attempt, ds = _lock_pair(db, device_session_id)
    if ds.status != "ACTIVE" or ds.last_heartbeat_seq > seq_seen:
        return False
    now = clock.now()
    seen = sessions.last_seen(ds)
    ds.connection_closed_at = now
    if attempt.status != state.ACTIVE:
        return False      # PAUSED or already INTERRUPTED: the register shows OFFLINE, nothing else changes
    state.apply(db, attempt, "INTERRUPT", actor_kind="system", actor_id=None, now=now,
                data={"last_seen_at": seen.isoformat() if seen else None, "device_session_id": str(ds.id),
                      "detected": "connection_closed"})
    db.flush()
    return True


def _reconnect(db: Session, attempt: Attempt, exam: Exam, now: datetime, prev_seen: datetime | None,
               cause: str | None) -> None:
    gap = int((now - prev_seen).total_seconds()) if prev_seen else None
    data = {"last_seen_at": prev_seen.isoformat() if prev_seen else None, "gap_seconds": gap,
            "cause": cause or "UNKNOWN", "device_changed": False}
    if prev_seen is not None and gap >= MIN_INCIDENT_GAP_SECONDS:
        # The client was not monitored during the gap (PRD §15, §20.3).
        from ..models import Incident
        db.add(Incident(attempt_id=attempt.id, type="UNMONITORED_INTERRUPTION", severity="MEDIUM",
                        started_at=prev_seen, ended_at=now, data=data))
    if attempt.deadline is not None and attempt.deadline <= now:
        _expire(db, attempt, now, data)
        return
    threshold = _setting(db, exam, "reentry_approval_threshold_minutes") * 60
    if gap is not None and gap < threshold:
        state.apply(db, attempt, "AUTO_RESUME", actor_kind="system", actor_id=None, now=now, data=data)
    else:
        state.apply(db, attempt, "REQUIRE_APPROVAL", actor_kind="system", actor_id=None, now=now, data=data)


# ------------------------------------------------------------------ normal completion
def submit(db: Session, attempt_id: UUID, *, actor_kind: str = "candidate", actor_id: UUID | None = None,
           source: str = "MANUAL_FINISH") -> dict[str, Any]:
    """ACTIVE -> SUBMITTED: Level 0 'Selesai Ujian' button, or LMS completion (Phase 1c, §16.5)."""
    attempt = state.lock_attempt(db, attempt_id)
    enr, _ = _context(db, attempt)
    state.apply(db, attempt, "SUBMIT", actor_kind=actor_kind,
                actor_id=actor_id if actor_id is not None else enr.candidate_id, data={"source": source})
    attempt.ended_at = clock.now()
    return full_state(db, attempt)
