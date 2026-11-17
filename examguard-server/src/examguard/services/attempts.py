"""Invigilator / Exam Admin actions on attempts and the monitoring views (PRD §10.3, §11, §27.5–27.10).

Every action: authorize against the exam (invigilators only on assigned exams), lock the attempt
row, optionally check the state_version the Admin Web saw, apply the transition through
``state.apply`` and queue the client command. One request = one transaction.
"""
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import access, audit, clock, commands, permissions as P, sessions, state, timing
from ..errors import AppError, conflict, invalid
from ..models import Attempt, Candidate, Command, DeviceSession, Enrollment, Exam, StateTransition
from ..principal import Principal
from . import lifecycle


# ------------------------------------------------------------------ loading
def _load(db: Session, p: Principal, attempt_id: UUID, permission: str,
          expected_version: int | None = None, *, lock_exam: bool = False) -> tuple[Attempt, Exam]:
    exam_id = access.exam_id_of_attempt(db, p.org_id, attempt_id)
    exam = access.require_exam(db, p, exam_id, permission)
    if lock_exam:  # lock order is always exam -> attempt (see lifecycle.extend)
        exam = db.scalar(select(Exam).where(Exam.id == exam_id).with_for_update())
    attempt = state.lock_attempt(db, attempt_id, org_id=p.org_id)
    state.check_version(attempt, expected_version)
    return attempt, exam


def _result(attempt: Attempt, command: Command | None = None) -> dict[str, Any]:
    return {"attempt_id": attempt.id, "status": attempt.status, "state_version": attempt.state_version,
            "deadline": attempt.deadline, "command_id": command.id if command else None}


# ------------------------------------------------------------------ invigilator actions
def warning(db: Session, p: Principal, attempt_id: UUID, message: str) -> dict[str, Any]:
    attempt, _ = _load(db, p, attempt_id, P.CONTROL)
    if attempt.status not in state.LIVE:
        raise conflict("INVALID_STATE", f"cannot send a warning to an attempt in status {attempt.status}")
    cmd = commands.issue(db, attempt, "WARNING", {"message": message}, issued_by=p.id)
    audit.record(db, org_id=attempt.org_id, actor_kind=p.actor_kind, actor_id=p.id, action="attempt.warning_sent",
                 target_type="attempt", target_id=attempt.id, data={"message": message, "command_id": cmd.id})
    return _result(attempt, cmd)


def pause(db: Session, p: Principal, attempt_id: UUID, reason: str, timer_mode: str,
          expected_version: int | None = None) -> dict[str, Any]:
    attempt, _ = _load(db, p, attempt_id, P.CONTROL, expected_version)
    now = clock.now()
    state.apply(db, attempt, "PAUSE", actor_kind=p.actor_kind, actor_id=p.id, reason=reason,
                data={"timer_mode": timer_mode}, now=now)
    attempt.paused_at, attempt.pause_timer_mode = now, timer_mode
    cmd = commands.issue(db, attempt, "PAUSE_EXAM", {"reason": reason, "timer_mode": timer_mode}, issued_by=p.id)
    return _result(attempt, cmd)


def resume(db: Session, p: Principal, attempt_id: UUID, reason: str,
           expected_version: int | None = None) -> dict[str, Any]:
    attempt, _ = _load(db, p, attempt_id, P.CONTROL, expected_version)
    if attempt.status != state.PAUSED:
        state.apply(db, attempt, "RESUME", actor_kind=p.actor_kind, actor_id=p.id)  # raises INVALID_TRANSITION
    now = clock.now()
    new_deadline = timing.deadline_after_resume(attempt.deadline, attempt.paused_at, now, attempt.pause_timer_mode)
    paused_for = int((now - attempt.paused_at).total_seconds())
    data = {"paused_seconds": paused_for, "timer_mode": attempt.pause_timer_mode}
    attempt.paused_at, attempt.pause_timer_mode = None, None
    if new_deadline <= now:
        # KEEP_RUNNING and the time ran out during the pause: the attempt is over.
        state.apply(db, attempt, "EXPIRE", actor_kind="system", actor_id=None, data=data, now=now)
        attempt.ended_at = now
        return _result(attempt)
    state.apply(db, attempt, "RESUME", actor_kind=p.actor_kind, actor_id=p.id, reason=reason,
                deadline=new_deadline, data=data, now=now)
    cmd = commands.issue(db, attempt, "RESUME_EXAM", {"deadline": new_deadline}, issued_by=p.id)
    return _result(attempt, cmd)


def add_time(db: Session, p: Principal, attempt_id: UUID, minutes: int, reason: str,
             expected_version: int | None = None) -> dict[str, Any]:
    attempt, _ = _load(db, p, attempt_id, P.CONTROL, expected_version)
    if not state.is_allowed("UPDATE_DEADLINE", attempt.status) or attempt.deadline is None:
        raise conflict("INVALID_TRANSITION", f"cannot add time to an attempt in status {attempt.status}")
    lifecycle.shift_deadline(db, attempt, minutes, reason, actor_kind=p.actor_kind, actor_id=p.id)
    return _result(attempt, _last_command(db, attempt.id))


def force_submit(db: Session, p: Principal, attempt_id: UUID, reason: str,
                 expected_version: int | None = None) -> dict[str, Any]:
    attempt, _ = _load(db, p, attempt_id, P.FORCE_SUBMIT, expected_version)
    target = sessions.pending(db, attempt.id) if attempt.status == state.WAITING else None
    state.apply(db, attempt, "FORCE_SUBMIT", actor_kind=p.actor_kind, actor_id=p.id, reason=reason)
    attempt.ended_at = clock.now()
    cmd = commands.issue(db, attempt, "FORCE_SUBMIT", {"reason": reason}, issued_by=p.id, session=target)
    return _result(attempt, cmd)


def terminate(db: Session, p: Principal, attempt_id: UUID, reason: str, reason_category: str,
              expected_version: int | None = None) -> dict[str, Any]:
    attempt, _ = _load(db, p, attempt_id, P.TERMINATE, expected_version)
    target = sessions.pending(db, attempt.id) if attempt.status == state.WAITING else None
    state.apply(db, attempt, "FORCE_TERMINATE", actor_kind=p.actor_kind, actor_id=p.id, reason=reason,
                reason_category=reason_category)
    attempt.ended_at = clock.now()
    cmd = commands.issue(db, attempt, "FORCE_TERMINATE", {"reason": reason}, issued_by=p.id, session=target)
    return _result(attempt, cmd)


def allow_reentry(db: Session, p: Principal, attempt_id: UUID, reason: str,
                  expected_version: int | None = None) -> dict[str, Any]:
    attempt, _ = _load(db, p, attempt_id, P.REENTRY, expected_version)
    if attempt.status != state.WAITING:
        state.apply(db, attempt, "ALLOW_REENTRY", actor_kind=p.actor_kind, actor_id=p.id)  # raises
    now = clock.now()
    if attempt.deadline is not None and attempt.deadline <= now:
        state.apply(db, attempt, "EXPIRE", actor_kind="system", actor_id=None, now=now,
                    data={"note": "deadline passed while waiting for approval"})
        attempt.ended_at = now
        # Report instead of raising: raising would roll the expiry back.
        return {**_result(attempt), "note": "DEADLINE_PASSED"}
    device = sessions.promote_pending(db, attempt.id)
    state.apply(db, attempt, "ALLOW_REENTRY", actor_kind=p.actor_kind, actor_id=p.id, reason=reason, now=now,
                data={"device_changed": device is not None})
    cmd = commands.issue(db, attempt, "ALLOW_REENTRY", {"deadline": attempt.deadline}, issued_by=p.id)
    return _result(attempt, cmd)


def reject_reentry(db: Session, p: Principal, attempt_id: UUID, reason: str, reason_category: str,
                   expected_version: int | None = None) -> dict[str, Any]:
    attempt, _ = _load(db, p, attempt_id, P.REENTRY, expected_version)
    target = sessions.pending(db, attempt.id)
    state.apply(db, attempt, "REJECT_REENTRY", actor_kind=p.actor_kind, actor_id=p.id, reason=reason,
                reason_category=reason_category, data={"reason_code": "REENTRY_REJECTED"})
    attempt.ended_at = clock.now()
    cmd = commands.issue(db, attempt, "REJECT_REENTRY", {"reason": reason}, issued_by=p.id, session=target)
    return _result(attempt, cmd)


# ------------------------------------------------------------------ exam admin actions
def _reopen_like(db: Session, p: Principal, attempt_id: UUID, trigger: str, deadline: datetime, reason: str,
                 expected_version: int | None) -> dict[str, Any]:
    attempt, exam = _load(db, p, attempt_id, P.REOPEN, expected_version, lock_exam=True)
    now = clock.now()
    if deadline <= now:
        raise invalid("DEADLINE_IN_PAST", "the new deadline must be in the future")
    state.apply(db, attempt, trigger, actor_kind=p.actor_kind, actor_id=p.id, reason=reason, deadline=deadline,
                data={"previous_status": attempt.status}, now=now)
    if trigger == "REOPEN":
        attempt.reopen_count += 1
    else:
        attempt.reinstate_count += 1
        attempt.termination_reason_category = None
    attempt.ended_at = None
    # The previous client is gone; a new launch registers a new device session (§17.4).
    sessions.revoke_all(db, attempt.id, trigger)
    lifecycle.revive(db, exam, p.actor_kind, p.id)
    return _result(attempt)


def reopen(db: Session, p: Principal, attempt_id: UUID, deadline: datetime, reason: str,
           expected_version: int | None = None) -> dict[str, Any]:
    return _reopen_like(db, p, attempt_id, "REOPEN", deadline, reason, expected_version)


def reinstate(db: Session, p: Principal, attempt_id: UUID, deadline: datetime, reason: str,
              expected_version: int | None = None) -> dict[str, Any]:
    return _reopen_like(db, p, attempt_id, "REINSTATE", deadline, reason, expected_version)


# ------------------------------------------------------------------ identity check (§12.5)
MAX_IDENTITY_REJECTIONS = 3


def review_identity(db: Session, p: Principal, attempt_id: UUID, approve: bool, reason: str | None) -> dict[str, Any]:
    attempt, _ = _load(db, p, attempt_id, P.IDENTITY)
    if attempt.identity_status != "PENDING":
        raise conflict("IDENTITY_NOT_PENDING", f"identity check is {attempt.identity_status}")
    if not approve and not reason:
        raise invalid("REASON_REQUIRED", "a reason is required when rejecting an identity check")
    attempt.identity_status = "APPROVED" if approve else "REJECTED"
    if not approve:
        attempt.identity_rejections += 1
    audit.record(db, org_id=attempt.org_id, actor_kind=p.actor_kind, actor_id=p.id,
                 action="attempt.identity_approved" if approve else "attempt.identity_rejected",
                 target_type="attempt", target_id=attempt.id,
                 data={"reason": reason, "rejections": attempt.identity_rejections})
    return {"attempt_id": attempt.id, "identity_status": attempt.identity_status,
            "identity_rejections": attempt.identity_rejections,
            "retries_left": max(MAX_IDENTITY_REJECTIONS - attempt.identity_rejections, 0)}


# ------------------------------------------------------------------ bulk (§27.10)
BULK_ACTIONS = ("WARNING", "PAUSE", "RESUME", "ADD_TIME", "TERMINATE")


def bulk(db: Session, p: Principal, exam_id: UUID, action: str, attempt_ids: list[UUID], *,
         reason: str, message: str | None = None, minutes: int | None = None,
         timer_mode: str = "KEEP_RUNNING", reason_category: str | None = None,
         confirm_exam_code: str | None = None) -> dict[str, Any]:
    exam = access.require_exam(db, p, exam_id, P.CONTROL if action != "TERMINATE" else P.BULK_TERMINATE)
    if action == "TERMINATE" and confirm_exam_code != exam.code:
        raise invalid("CONFIRMATION_REQUIRED", "type the exam code in confirm_exam_code to terminate in bulk")
    if action == "WARNING" and not message:
        raise invalid("MESSAGE_REQUIRED", "message is required")
    if action == "ADD_TIME" and not minutes:
        raise invalid("MINUTES_REQUIRED", "minutes is required")
    in_exam = set(db.scalars(select(Attempt.id).join(Enrollment, Enrollment.id == Attempt.enrollment_id)
                             .where(Enrollment.exam_id == exam.id, Attempt.id.in_(attempt_ids))))
    parent = audit.record(db, org_id=exam.org_id, actor_kind=p.actor_kind, actor_id=p.id, action="bulk.started",
                          target_type="exam", target_id=exam.id,
                          data={"action": action, "count": len(attempt_ids), "reason": reason})
    results = []
    for aid in dict.fromkeys(attempt_ids):
        if aid not in in_exam:
            results.append({"attempt_id": aid, "ok": False, "error": "NOT_FOUND"})
            continue
        try:
            with db.begin_nested():
                if action == "WARNING":
                    r = warning(db, p, aid, message)
                elif action == "PAUSE":
                    r = pause(db, p, aid, reason, timer_mode)
                elif action == "RESUME":
                    r = resume(db, p, aid, reason)
                elif action == "ADD_TIME":
                    r = add_time(db, p, aid, minutes, reason)
                else:
                    r = terminate(db, p, aid, reason, reason_category)
            results.append({"attempt_id": aid, "ok": True, "status": r["status"],
                            "state_version": r["state_version"]})
        except AppError as e:
            results.append({"attempt_id": aid, "ok": False, "error": e.code})
    ok = sum(r["ok"] for r in results)
    audit.record(db, org_id=exam.org_id, actor_kind=p.actor_kind, actor_id=p.id, action="bulk.completed",
                 target_type="exam", target_id=exam.id,
                 data={"action": action, "parent_audit_id": parent, "succeeded": ok, "failed": len(results) - ok})
    return {"action": action, "succeeded": ok, "failed": len(results) - ok, "results": results}


# ------------------------------------------------------------------ views
def _last_command(db: Session, attempt_id: UUID) -> Command | None:
    return db.scalars(select(Command).where(Command.attempt_id == attempt_id)
                      .order_by(Command.issued_at.desc(), Command.state_version.desc())).first()


ACTIONS: dict[str, tuple[str | None, str]] = {
    # action -> (trigger that must be allowed, permission)
    "warning": (None, P.CONTROL),
    "pause": ("PAUSE", P.CONTROL),
    "resume": ("RESUME", P.CONTROL),
    "add_time": ("UPDATE_DEADLINE", P.CONTROL),
    "force_submit": ("FORCE_SUBMIT", P.FORCE_SUBMIT),
    "terminate": ("FORCE_TERMINATE", P.TERMINATE),
    "allow_reentry": ("ALLOW_REENTRY", P.REENTRY),
    "reject_reentry": ("REJECT_REENTRY", P.REENTRY),
    "reopen": ("REOPEN", P.REOPEN),
    "reinstate": ("REINSTATE", P.REOPEN),
}


def available_actions(db: Session, p: Principal, exam_id: UUID, attempt: Attempt) -> list[str]:
    """Buttons shown in Candidate Detail: valid for the status (§10.3) and allowed for the role (§7)."""
    out = []
    for name, (trigger, perm) in ACTIONS.items():
        valid = attempt.status in state.LIVE if trigger is None else state.is_allowed(trigger, attempt.status)
        if valid and access.can(db, p, exam_id, perm):
            out.append(name)
    if attempt.identity_status == "PENDING" and access.can(db, p, exam_id, P.IDENTITY):
        out += ["identity_approve", "identity_reject"]
    return out


def _open_incidents(db: Session, attempt_ids: list[UUID]) -> dict[UUID, int]:
    if not attempt_ids:
        return {}
    from sqlalchemy import func
    from ..models import Incident
    rows = db.execute(select(Incident.attempt_id, func.count()).where(
        Incident.attempt_id.in_(attempt_ids), Incident.status == "OPEN").group_by(Incident.attempt_id)).all()
    return {a: n for a, n in rows}


def _row(attempt: Attempt, enr: Enrollment, cand: Candidate, ds: DeviceSession | None, now: datetime,
         open_incidents: int = 0, threshold: int | None = None) -> dict[str, Any]:
    return {
        "attempt_id": attempt.id, "enrollment_id": enr.id, "candidate_id": cand.id,
        "candidate_name": cand.full_name, "candidate_email": cand.email,
        "status": attempt.status, "state_version": attempt.state_version,
        "connection_status": sessions.connection_status(ds, now, threshold) if ds else "OFFLINE",
        "last_seen_at": sessions.last_seen(ds),
        "started_at": attempt.started_at, "deadline": attempt.deadline,
        "remaining_seconds": timing.remaining_seconds(attempt.deadline, now, status=attempt.status,
                                                      timer_mode=attempt.pause_timer_mode,
                                                      paused_at=attempt.paused_at),
        "paused_at": attempt.paused_at, "pause_timer_mode": attempt.pause_timer_mode,
        "identity_status": attempt.identity_status,
        "time_accommodation_minutes": enr.time_accommodation_minutes,
        "reopen_count": attempt.reopen_count, "reinstate_count": attempt.reinstate_count,
        "termination_reason_category": attempt.termination_reason_category,
        "final_status": attempt.final_status,
        "open_incidents": open_incidents,
        # latest heartbeat health summary (lockdown_ok, camera_ok, mic_ok, queue_depth — §17.6)
        "health": ((ds.os_info or {}).get("health") or {}) if ds else {},
        "client_version": ds.client_version if ds else None,
    }


def exam_attempts(db: Session, p: Principal, exam_id: UUID, status: str | None = None) -> dict[str, Any]:
    exam = access.require_exam(db, p, exam_id, P.MONITOR)
    now = clock.now()
    q = (select(Attempt, Enrollment, Candidate, DeviceSession)
         .join(Enrollment, Enrollment.id == Attempt.enrollment_id)
         .join(Candidate, Candidate.id == Enrollment.candidate_id)
         .outerjoin(DeviceSession, (DeviceSession.attempt_id == Attempt.id) & (DeviceSession.status == "ACTIVE"))
         .where(Enrollment.exam_id == exam.id, Enrollment.status == "CONFIRMED")
         .order_by(Candidate.full_name))
    if status:
        q = q.where(Attempt.status == status)
    result = db.execute(q).all()
    incidents = _open_incidents(db, [a.id for a, *_ in result])
    threshold = sessions.offline_threshold(db, exam)
    rows = [_row(a, e, c, ds, now, incidents.get(a.id, 0), threshold) for a, e, c, ds in result]
    summary: dict[str, int] = {s: 0 for s in state.ALL_STATUSES}
    for r in rows:
        summary[r["status"]] += 1
    summary["ONLINE"] = sum(r["connection_status"] == "ONLINE" and r["status"] in state.LIVE for r in rows)
    summary["OFFLINE"] = sum(r["connection_status"] == "OFFLINE" and r["status"] in state.LIVE for r in rows)
    summary["OPEN_INCIDENTS"] = sum(r["open_incidents"] for r in rows)
    return {"exam_id": exam.id, "exam_status": exam.status, "server_time": now,
            "summary": summary, "attempts": rows}


def attempt_detail(db: Session, p: Principal, attempt_id: UUID) -> dict[str, Any]:
    exam_id = access.exam_id_of_attempt(db, p.org_id, attempt_id)
    exam = access.require_exam(db, p, exam_id, P.MONITOR)
    threshold = sessions.offline_threshold(db, exam)
    now = clock.now()
    attempt = db.get(Attempt, attempt_id)
    enr = db.get(Enrollment, attempt.enrollment_id)
    cand = db.get(Candidate, enr.candidate_id)
    devices = list(db.scalars(select(DeviceSession).where(DeviceSession.attempt_id == attempt.id)
                              .order_by(DeviceSession.created_at)))
    active = next((d for d in devices if d.status == "ACTIVE"), None)
    transitions = list(db.scalars(select(StateTransition).where(StateTransition.attempt_id == attempt.id)
                                  .order_by(StateTransition.state_version)))
    cmds = list(db.scalars(select(Command).where(Command.attempt_id == attempt.id)
                           .order_by(Command.issued_at.desc()).limit(50)))
    from ..models import Event, Incident
    events = list(db.scalars(select(Event).where(Event.attempt_id == attempt.id)
                             .order_by(Event.started_at.desc(), Event.seq.desc()).limit(200)))
    incidents = list(db.scalars(select(Incident).where(Incident.attempt_id == attempt.id)))
    incident_status = {i.id: i.status for i in incidents}
    open_count = sum(1 for st in incident_status.values() if st == "OPEN")
    # §27.6: this candidate's incidents, open first, then newest first
    incidents.sort(key=lambda i: i.started_at, reverse=True)
    incidents.sort(key=lambda i: i.status != "OPEN")
    from .proctoring import _incident_out
    return {
        **_row(attempt, enr, cand, active, now, open_count, threshold),
        "exam_id": exam_id, "server_time": now,
        "available_actions": available_actions(db, p, exam_id, attempt),
        "device_sessions": [{
            "id": d.id, "status": d.status, "client_version": d.client_version, "os_info": d.os_info,
            "created_at": d.created_at, "activated_at": d.activated_at, "revoked_at": d.revoked_at,
            "revoke_reason": d.revoke_reason, "last_heartbeat_at": d.last_heartbeat_at,
            "connection_status": sessions.connection_status(d, now, threshold) if d.status != "REVOKED" else "OFFLINE",
        } for d in devices],
        "transitions": [{
            "state_version": t.state_version, "from_status": t.from_status, "to_status": t.to_status,
            "trigger": t.trigger, "actor_kind": t.actor_kind, "actor_id": t.actor_id, "reason": t.reason,
            "reason_category": t.reason_category, "old_deadline": t.old_deadline,
            "new_deadline": t.new_deadline, "data": t.data, "occurred_at": t.occurred_at,
        } for t in transitions],
        "commands": [{
            "id": c.id, "type": c.type, "payload": c.payload, "state_version": c.state_version,
            "device_session_id": c.device_session_id, "issued_at": c.issued_at,
            "delivery_status": c.delivery_status,
        } for c in cmds],
        "incidents": [_incident_out(i) for i in incidents],
        # §27.6 event timeline (newest first); severity is for sorting only, never a verdict (§15)
        "events": [{
            "event_id": e.id, "type": e.type, "phase": e.phase, "severity": e.severity,
            "started_at": e.started_at, "ended_at": e.ended_at, "confidence": e.confidence,
            "metadata": e.metadata_, "incident_id": e.incident_id,
            "incident_status": incident_status.get(e.incident_id) if e.incident_id else None,
        } for e in events],
    }


def waiting_list(db: Session, p: Principal, exam_id: UUID) -> list[dict[str, Any]]:
    """Interrupted Sessions & Re-entry Requests (§27.9)."""
    exam = access.require_exam(db, p, exam_id, P.MONITOR)
    q = (select(StateTransition, Candidate)
         .join(Attempt, Attempt.id == StateTransition.attempt_id)
         .join(Enrollment, Enrollment.id == Attempt.enrollment_id)
         .join(Candidate, Candidate.id == Enrollment.candidate_id)
         .where(Enrollment.exam_id == exam.id,
                StateTransition.trigger.in_(("AUTO_RESUME", "REQUIRE_APPROVAL")))
         .order_by(StateTransition.occurred_at.desc()))
    out = []
    for t, c in db.execute(q).all():
        attempt = db.get(Attempt, t.attempt_id)
        out.append({
            "attempt_id": t.attempt_id, "candidate_name": c.full_name, "occurred_at": t.occurred_at,
            "last_seen_at": t.data.get("last_seen_at"), "gap_seconds": t.data.get("gap_seconds"),
            "cause": t.data.get("cause"), "device_changed": t.data.get("device_changed", False),
            "outcome": "AUTO_RESUMED" if t.trigger == "AUTO_RESUME" else "WAITING",
            "current_status": attempt.status, "state_version": attempt.state_version,
        })
    return out
