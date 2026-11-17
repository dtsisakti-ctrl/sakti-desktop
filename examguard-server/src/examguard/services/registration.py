"""Catalog, self-registration, invitations and enrollment management (PRD §8.3, §8.4, §28)."""
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import audit, clock, emailer, state
from ..config import get_settings
from ..db import elevated
from ..errors import AppError, conflict, forbidden, invalid, not_found
from ..models import Attempt, Candidate, Enrollment, Exam, Invitation, Organization
from ..principal import Principal
from ..security import new_token, token_hash, verify_password


# ------------------------------------------------------------------ helpers
def registration_status(exam: Exam, now: datetime) -> str:
    if exam.registration_open and now < exam.registration_open:
        return "NOT_YET_OPEN"
    if exam.registration_close and now >= exam.registration_close:
        return "CLOSED"
    if exam.capacity is not None and exam.registered_count >= exam.capacity:
        return "FULL"
    return "OPEN"


def _reserve_seat(db: Session, exam_id: UUID) -> None:
    ok = db.execute(text("SELECT eg_reserve_seat(:e)"), {"e": exam_id}).scalar_one()
    if not ok:
        raise conflict("EXAM_FULL", "no seats left for this exam")


def _release_seat(db: Session, exam_id: UUID) -> None:
    db.execute(text("SELECT eg_release_seat(:e)"), {"e": exam_id})


def _create_enrollment(db: Session, exam: Exam, cand: Candidate, source: str) -> Enrollment:
    """Seat reservation + enrollment + attempt, all in the caller's transaction."""
    _reserve_seat(db, exam.id)
    enr = Enrollment(exam_id=exam.id, candidate_id=cand.id, source=source, status="CONFIRMED")
    db.add(enr)
    try:
        with db.begin_nested():
            db.flush()
    except IntegrityError:
        raise conflict("ALREADY_REGISTERED", "already registered for this exam") from None
    db.add(Attempt(enrollment_id=enr.id, status="NOT_STARTED", state_version=0))
    db.flush()
    return enr


def _require_verified(cand: Candidate) -> None:
    if cand.email_verified_at is None:
        raise AppError(403, "EMAIL_NOT_VERIFIED", "verify your email before registering")


def _check_access_code(exam: Exam, access_code: str | None) -> None:
    if exam.access_code_hash and not verify_password(access_code or "", exam.access_code_hash):
        raise AppError(403, "INVALID_ACCESS_CODE", "access code is missing or incorrect")


def _open_public_exam(db: Session, exam_id: UUID) -> Exam:
    exam = db.scalar(select(Exam).where(Exam.id == exam_id, Exam.visibility == "PUBLIC"))
    if exam is None or exam.status not in ("READY",):
        raise not_found("exam")
    status = registration_status(exam, clock.now())
    if status == "FULL":
        raise conflict("EXAM_FULL", "no seats left for this exam")
    if status != "OPEN":
        raise conflict("REGISTRATION_CLOSED", f"registration is {status.lower().replace('_', ' ')}")
    return exam


# ------------------------------------------------------------------ public catalog
def catalog(db: Session, series: str | None = None) -> list[dict[str, Any]]:
    now = clock.now()
    q = (select(Exam, Organization.name)
         .join(Organization, Organization.id == Exam.org_id)
         .where(Exam.visibility == "PUBLIC", Exam.status == "READY",
                Exam.registration_close > now))
    if series:
        q = q.where(Exam.series == series)
    out = []
    for exam, org_name in db.execute(q.order_by(Exam.window_start)).all():
        out.append({
            "id": exam.id, "org_name": org_name, "code": exam.code, "name": exam.name,
            "description": exam.description, "series": exam.series,
            "window_start": exam.window_start, "window_end": exam.window_end,
            "duration_minutes": exam.duration_minutes,
            "registration_open": exam.registration_open, "registration_close": exam.registration_close,
            "registration_status": registration_status(exam, now),
            "seats_left": None if exam.capacity is None else max(exam.capacity - exam.registered_count, 0),
            "requires_access_code": exam.access_code_hash is not None,
            "identity_check": exam.identity_check,
        })
    return out


# ------------------------------------------------------------------ candidate self-service
def register(db: Session, cand: Candidate, exam_id: UUID, access_code: str | None) -> Enrollment:
    _require_verified(cand)
    exam = _open_public_exam(db, exam_id)
    _check_access_code(exam, access_code)
    enr = _create_enrollment(db, exam, cand, "SELF_REGISTERED")
    audit.record(db, org_id=exam.org_id, actor_kind="candidate", actor_id=cand.id,
                 action="enrollment.created", target_type="enrollment", target_id=enr.id,
                 data={"exam_id": exam.id, "source": "SELF_REGISTERED"})
    emailer.enqueue(db, cand.email, "registration_confirmed", name=cand.full_name,
                    exam_name=exam.name, window_start=exam.window_start.isoformat())
    return enr


def _own_enrollment(db: Session, cand: Candidate, enrollment_id: UUID) -> Enrollment:
    enr = db.scalar(select(Enrollment).where(Enrollment.id == enrollment_id,
                                             Enrollment.candidate_id == cand.id))
    if enr is None:
        raise not_found("enrollment")
    return enr


def _withdraw(db: Session, enr: Enrollment, reason: str) -> None:
    attempt = db.scalar(select(Attempt).where(Attempt.enrollment_id == enr.id))
    if attempt is not None and attempt.status != "NOT_STARTED":
        raise conflict("ATTEMPT_ALREADY_STARTED", "the exam attempt has already started")
    if attempt is not None:
        db.delete(attempt)
    enr.status, enr.cancelled_at, enr.cancel_reason = "CANCELLED", clock.now(), reason
    _release_seat(db, enr.exam_id)
    db.flush()


def _check_candidate_may_change(enr: Enrollment) -> None:
    if enr.status != "CONFIRMED":
        raise conflict("ENROLLMENT_NOT_ACTIVE", "enrollment is not active")
    if enr.source != "SELF_REGISTERED":
        raise forbidden("enrollments created by an organization can only be changed by that organization")
    exam = enr.exam
    if exam.status != "READY" or (exam.registration_close and clock.now() >= exam.registration_close):
        raise conflict("REGISTRATION_CLOSED", "changes are no longer possible for this exam")


def cancel_own(db: Session, cand: Candidate, enrollment_id: UUID) -> Enrollment:
    enr = _own_enrollment(db, cand, enrollment_id)
    _check_candidate_may_change(enr)
    _withdraw(db, enr, "CANDIDATE_CANCELLED")
    audit.record(db, org_id=enr.org_id, actor_kind="candidate", actor_id=cand.id,
                 action="enrollment.cancelled", target_type="enrollment", target_id=enr.id,
                 data={"reason": "CANDIDATE_CANCELLED"})
    emailer.enqueue(db, cand.email, "registration_cancelled", name=cand.full_name,
                    exam_name=enr.exam.name, reason="dibatalkan oleh peserta")
    return enr


def move_own(db: Session, cand: Candidate, enrollment_id: UUID, target_exam_id: UUID,
             access_code: str | None) -> Enrollment:
    enr = _own_enrollment(db, cand, enrollment_id)
    _check_candidate_may_change(enr)
    source_exam = enr.exam
    if target_exam_id == source_exam.id:
        raise invalid("SAME_EXAM", "target is the current exam")
    target = _open_public_exam(db, target_exam_id)
    if not source_exam.series or target.series != source_exam.series or target.org_id != source_exam.org_id:
        raise conflict("NOT_SAME_SERIES", "you can only move to another session of the same test series")
    _check_access_code(target, access_code)
    _withdraw(db, enr, "MOVED")
    new = _create_enrollment(db, target, cand, "SELF_REGISTERED")
    audit.record(db, org_id=target.org_id, actor_kind="candidate", actor_id=cand.id,
                 action="enrollment.moved", target_type="enrollment", target_id=new.id,
                 data={"from_enrollment": enr.id, "from_exam": source_exam.id, "to_exam": target.id})
    emailer.enqueue(db, cand.email, "registration_moved", name=cand.full_name,
                    exam_name=target.name, window_start=target.window_start.isoformat())
    return new


def launch_window(exam: Exam, attempt: Attempt | None, now: datetime) -> tuple[bool, str | None]:
    """May the candidate start the client now? (PRD §28.4) Returns (allowed, reason when not)."""
    if attempt is None or attempt.status in state.FINAL:
        return False, "ENDED"
    if exam.status not in ("READY", "RUNNING", "CLOSED"):
        return False, "EXAM_NOT_OPEN"
    if attempt.status != state.NOT_STARTED:
        return True, None                       # relaunch after a crash, reopened or reinstated attempt
    if exam.checkin_open and now < exam.checkin_open:
        return False, "NOT_YET_OPEN"
    if exam.latest_start and now > exam.latest_start:
        return False, "LATE_START_CLOSED"
    return True, None


def my_enrollments(db: Session, cand: Candidate) -> list[dict[str, Any]]:
    """'Ujian Saya' (PRD §28.4): schedule, attempt status and what the candidate can do now."""
    now = clock.now()
    rows = db.execute(
        select(Enrollment, Attempt)
        .outerjoin(Attempt, Attempt.enrollment_id == Enrollment.id)
        .where(Enrollment.candidate_id == cand.id)
        .order_by(Enrollment.created_at.desc())
    ).all()
    with elevated(db):
        org_ids = {enr.org_id for enr, _ in rows}
        org_names = dict(db.execute(select(Organization.id, Organization.name)
                                    .where(Organization.id.in_(org_ids))).all()) if org_ids else {}
    out = []
    for enr, attempt in rows:
        e = enr.exam
        can_launch, launch_reason = launch_window(e, attempt, now) if enr.status == "CONFIRMED" else (False, "NOT_ENROLLED")
        try:
            _check_candidate_may_change(enr)
            can_change = True
        except AppError:
            can_change = False
        out.append({
            "id": enr.id, "status": enr.status, "source": enr.source, "created_at": enr.created_at,
            "cancelled_at": enr.cancelled_at, "cancel_reason": enr.cancel_reason,
            "attempt_status": attempt.status if attempt else None,
            "attempt": None if attempt is None else {
                "id": attempt.id, "status": attempt.status, "started_at": attempt.started_at,
                "deadline": attempt.deadline, "ended_at": attempt.ended_at,
            },
            "can_launch": can_launch, "launch_reason": launch_reason, "can_change": can_change,
            "exam": {**{k: getattr(e, k) for k in ("id", "code", "name", "series", "visibility", "status",
                                                   "window_start", "window_end", "checkin_open",
                                                   "registration_close", "latest_start", "duration_minutes",
                                                   "description", "identity_check")},
                     "org_name": org_names.get(e.org_id)},
        })
    return out


def invitation_preview(db: Session, token: str) -> dict[str, Any]:
    """What an invitation link is for, shown before sign-in (PRD §28.3). Anonymous."""
    now = clock.now()
    with elevated(db):
        inv = db.scalar(select(Invitation).where(Invitation.token_hash == token_hash(token)))
        if inv is None:
            raise invalid("INVALID_TOKEN", "invitation is invalid")
        exam = db.get(Exam, inv.exam_id)
        org = db.get(Organization, exam.org_id)
        status = inv.status if inv.status != "PENDING" or inv.expires_at > now else "EXPIRED"
        return {"status": status, "email": inv.email, "expires_at": inv.expires_at,
                "org_name": org.name, "exam_name": exam.name, "exam_code": exam.code,
                "window_start": exam.window_start, "window_end": exam.window_end,
                "account_exists": db.scalar(select(func.count()).select_from(Candidate)
                                            .where(func.lower(Candidate.email) == inv.email.lower())) > 0}


# ------------------------------------------------------------------ invitations
def create_invitations(db: Session, actor: Principal, exam_id: UUID, emails: list[str],
                       expires_in_days: int | None) -> dict[str, Any]:
    exam = db.scalar(select(Exam).where(Exam.id == exam_id, Exam.org_id == actor.org_id))
    if exam is None:
        raise not_found("exam")
    if exam.status not in ("DRAFT", "READY"):
        raise conflict("INVALID_STATE", f"cannot invite to an exam in status {exam.status}")
    org = db.get(Organization, actor.org_id)
    days = expires_in_days or get_settings().invitation_days
    expires = clock.now() + timedelta(days=days)
    created, skipped, seen = [], [], set()
    for email in emails:
        key = email.lower()
        if key in seen:
            skipped.append({"email": email, "reason": "duplicate in request"})
            continue
        seen.add(key)
        pending = db.scalar(select(Invitation.id).where(
            Invitation.exam_id == exam.id, func.lower(Invitation.email) == key,
            Invitation.status == "PENDING"))
        if pending:
            skipped.append({"email": email, "reason": "already invited"})
            continue
        enrolled = db.scalar(select(Enrollment.id).join(Candidate, Candidate.id == Enrollment.candidate_id)
                             .where(Enrollment.exam_id == exam.id, Enrollment.status == "CONFIRMED",
                                    func.lower(Candidate.email) == key))
        if enrolled:
            skipped.append({"email": email, "reason": "already enrolled"})
            continue
        token = new_token()
        inv = Invitation(exam_id=exam.id, email=email, token_hash=token_hash(token), status="PENDING",
                         expires_at=expires, created_by=actor.id)
        db.add(inv)
        db.flush()
        created.append(inv)
        emailer.enqueue(db, email, "invitation", org_name=org.name, exam_name=exam.name, token=token,
                        expires_at=expires.isoformat())
    audit.record(db, org_id=exam.org_id, actor_kind=actor.actor_kind, actor_id=actor.id,
                 action="invitations.created", target_type="exam", target_id=exam.id,
                 data={"created": len(created), "skipped": len(skipped)})
    return {"created": created, "skipped": skipped}


def list_invitations(db: Session, org_id: UUID, exam_id: UUID) -> list[Invitation]:
    return list(db.scalars(select(Invitation).where(Invitation.exam_id == exam_id,
                                                    Invitation.org_id == org_id)
                           .order_by(Invitation.created_at.desc())))


def revoke_invitation(db: Session, actor: Principal, invitation_id: UUID) -> Invitation:
    inv = db.scalar(select(Invitation).where(Invitation.id == invitation_id,
                                             Invitation.org_id == actor.org_id))
    if inv is None:
        raise not_found("invitation")
    if inv.status != "PENDING":
        raise conflict("INVALID_STATE", f"invitation is {inv.status}")
    inv.status = "REVOKED"
    audit.record(db, org_id=inv.org_id, actor_kind=actor.actor_kind, actor_id=actor.id,
                 action="invitation.revoked", target_type="invitation", target_id=inv.id)
    return inv


def accept_invitation(db: Session, cand: Candidate, token: str) -> Enrollment:
    _require_verified(cand)
    now = clock.now()
    with elevated(db):
        inv = db.scalar(select(Invitation).where(Invitation.token_hash == token_hash(token)))
        if inv is None or inv.status != "PENDING" or inv.expires_at <= now:
            raise invalid("INVALID_TOKEN", "invitation is invalid, used, revoked or expired")
        if inv.email.lower() != cand.email.lower():
            raise AppError(403, "INVITATION_EMAIL_MISMATCH",
                           "this invitation was sent to a different email address")
        exam = db.get(Exam, inv.exam_id)
        if exam.status != "READY":
            raise conflict("EXAM_NOT_OPEN", "the exam is not open for enrollment yet")
    # Enrollment is written as the candidate, so RLS checks candidate ownership.
    enr = _create_enrollment(db, exam, cand, "INVITED")
    with elevated(db):
        inv.status, inv.accepted_enrollment_id = "ACCEPTED", enr.id
        audit.record(db, org_id=exam.org_id, actor_kind="candidate", actor_id=cand.id,
                     action="invitation.accepted", target_type="invitation", target_id=inv.id,
                     data={"enrollment_id": enr.id})
    return enr


# ------------------------------------------------------------------ organization side
def org_enrollments(db: Session, org_id: UUID, exam_id: UUID) -> list[dict[str, Any]]:
    rows = db.execute(
        select(Enrollment, Candidate).join(Candidate, Candidate.id == Enrollment.candidate_id)
        .where(Enrollment.exam_id == exam_id, Enrollment.org_id == org_id)
        .order_by(Enrollment.created_at)
    ).all()
    return [{
        "id": e.id, "candidate_id": c.id, "candidate_name": c.full_name, "candidate_email": c.email,
        "source": e.source, "status": e.status, "time_accommodation_minutes": e.time_accommodation_minutes,
        "created_at": e.created_at, "cancelled_at": e.cancelled_at, "cancel_reason": e.cancel_reason,
    } for e, c in rows]


def _org_enrollment(db: Session, org_id: UUID, enrollment_id: UUID) -> Enrollment:
    enr = db.scalar(select(Enrollment).where(Enrollment.id == enrollment_id, Enrollment.org_id == org_id))
    if enr is None:
        raise not_found("enrollment")
    return enr


def org_cancel_enrollment(db: Session, actor: Principal, enrollment_id: UUID, reason: str) -> Enrollment:
    enr = _org_enrollment(db, actor.org_id, enrollment_id)
    if enr.status != "CONFIRMED":
        raise conflict("ENROLLMENT_NOT_ACTIVE", "enrollment is not active")
    _withdraw(db, enr, "ORG_CANCELLED")
    audit.record(db, org_id=enr.org_id, actor_kind=actor.actor_kind, actor_id=actor.id,
                 action="enrollment.cancelled", target_type="enrollment", target_id=enr.id,
                 data={"reason": reason})
    emailer.enqueue(db, enr.candidate.email, "registration_cancelled", name=enr.candidate.full_name,
                    exam_name=enr.exam.name, reason=reason)
    return enr


def org_patch_enrollment(db: Session, actor: Principal, enrollment_id: UUID, minutes: int) -> Enrollment:
    enr = _org_enrollment(db, actor.org_id, enrollment_id)
    old = enr.time_accommodation_minutes
    enr.time_accommodation_minutes = minutes
    audit.record(db, org_id=enr.org_id, actor_kind=actor.actor_kind, actor_id=actor.id,
                 action="enrollment.accommodation_updated", target_type="enrollment", target_id=enr.id,
                 data={"from": old, "to": minutes})
    return enr
