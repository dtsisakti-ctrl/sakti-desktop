"""Exam-level lifecycle after publication (PRD §9, §11.3, §27.10).

READY -> RUNNING     scheduler at window_start (or inline when the first candidate starts)
RUNNING -> CLOSED    scheduler, once latest_start has passed and every attempt is final
CLOSED -> RUNNING    when an attempt is reopened or reinstated
CLOSED -> FINALIZED  Exam Admin; every attempt becomes FINALIZED
"""
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import access, audit, clock, commands, permissions, state
from ..errors import conflict, invalid
from ..models import Attempt, Enrollment, Exam
from ..principal import Principal

MAX_EXTENSION_MINUTES = 1440


def _exam_audit(db: Session, exam: Exam, action: str, actor_kind: str, actor_id: UUID | None,
                data: dict[str, Any] | None = None) -> None:
    audit.record(db, org_id=exam.org_id, actor_kind=actor_kind, actor_id=actor_id, action=action,
                 target_type="exam", target_id=exam.id, data=data)


def mark_running(db: Session, exam: Exam, now: datetime, *, actor_kind: str = "system") -> bool:
    if exam.status != "READY" or exam.window_start is None or exam.window_start > now:
        return False
    exam.status, exam.running_at, exam.updated_at = "RUNNING", now, now
    _exam_audit(db, exam, "exam.running", actor_kind, None, {"window_start": exam.window_start})
    return True


def revive(db: Session, exam: Exam, actor_kind: str, actor_id: UUID | None) -> None:
    """A reopened/reinstated attempt brings a CLOSED exam back to RUNNING (§9)."""
    if exam.status == "CLOSED":
        now = clock.now()
        exam.status, exam.closed_at, exam.updated_at = "RUNNING", None, now
        _exam_audit(db, exam, "exam.reopened", actor_kind, actor_id)


def open_attempts(db: Session, exam_id: UUID) -> int:
    return db.scalar(select(func.count()).select_from(Attempt)
                     .join(Enrollment, Enrollment.id == Attempt.enrollment_id)
                     .where(Enrollment.exam_id == exam_id, Attempt.status.not_in(state.FINAL))) or 0


def try_close(db: Session, exam: Exam, now: datetime) -> bool:
    if exam.status != "RUNNING" or exam.latest_start is None or now <= exam.latest_start:
        return False
    if open_attempts(db, exam.id):
        return False
    exam.status, exam.closed_at, exam.updated_at = "CLOSED", now, now
    _exam_audit(db, exam, "exam.closed", "system", None)
    return True


def _locked_exam(db: Session, p: Principal, exam_id: UUID, permission: str) -> Exam:
    access.require_exam(db, p, exam_id, permission)
    return db.scalar(select(Exam).where(Exam.id == exam_id, Exam.org_id == p.org_id)
                     .with_for_update())


def finalize(db: Session, p: Principal, exam_id: UUID, reason: str | None) -> dict[str, Any]:
    exam = _locked_exam(db, p, exam_id, permissions.FINALIZE)
    if exam.status != "CLOSED":
        raise conflict("INVALID_TRANSITION", f"only a CLOSED exam can be finalized (status {exam.status})")
    attempts = list(db.scalars(
        select(Attempt).join(Enrollment, Enrollment.id == Attempt.enrollment_id)
        .where(Enrollment.exam_id == exam.id).order_by(Attempt.id).with_for_update(of=Attempt)))
    not_final = [a.id for a in attempts if a.status not in state.FINAL]
    if not_final:
        raise conflict("ATTEMPTS_NOT_FINAL", "some attempts are not final yet", {"attempt_ids": not_final})
    now = clock.now()
    n = 0
    for a in attempts:
        if a.status == state.FINALIZED:
            continue
        a.final_status = a.status
        state.apply(db, a, "FINALIZE", actor_kind=p.actor_kind, actor_id=p.id, reason=reason, now=now)
        n += 1
    exam.status, exam.finalized_at, exam.updated_at = "FINALIZED", now, now
    _exam_audit(db, exam, "exam.finalized", p.actor_kind, p.id, {"reason": reason, "attempts": n})
    return {"exam_id": exam.id, "status": exam.status, "attempts_finalized": n}


def extend(db: Session, p: Principal, exam_id: UUID, minutes: int, reason: str) -> dict[str, Any]:
    """Add X minutes to every non-final attempt, and to candidates who start later (§11.3)."""
    exam = _locked_exam(db, p, exam_id, permissions.EXTEND)
    if exam.status not in ("READY", "RUNNING", "CLOSED"):
        raise conflict("INVALID_STATE", f"cannot extend an exam in status {exam.status}")
    if exam.extension_minutes + minutes > MAX_EXTENSION_MINUTES:
        raise invalid("EXTENSION_TOO_LONG", f"total extension may not exceed {MAX_EXTENSION_MINUTES} minutes")
    exam.extension_minutes += minutes
    exam.updated_at = clock.now()
    _exam_audit(db, exam, "exam.extended", p.actor_kind, p.id,
                {"minutes": minutes, "total_extension_minutes": exam.extension_minutes, "reason": reason})
    attempts = list(db.scalars(
        select(Attempt).join(Enrollment, Enrollment.id == Attempt.enrollment_id)
        .where(Enrollment.exam_id == exam.id, Attempt.status.in_(state.HAS_DEADLINE))
        .order_by(Attempt.id).with_for_update(of=Attempt)))
    for a in attempts:
        shift_deadline(db, a, minutes, reason, actor_kind=p.actor_kind, actor_id=p.id,
                       data={"exam_extension": True})
    return {"exam_id": exam.id, "extension_minutes": exam.extension_minutes, "attempts_updated": len(attempts)}


def shift_deadline(db: Session, attempt: Attempt, minutes: int, reason: str, *, actor_kind: str,
                   actor_id: UUID | None, data: dict[str, Any] | None = None) -> None:
    new = attempt.deadline + timedelta(minutes=minutes)
    state.apply(db, attempt, "UPDATE_DEADLINE", actor_kind=actor_kind, actor_id=actor_id, reason=reason,
                deadline=new, data={"minutes": minutes, **(data or {})})
    commands.issue(db, attempt, "UPDATE_DEADLINE", {"deadline": new, "reason": reason}, issued_by=actor_id)
