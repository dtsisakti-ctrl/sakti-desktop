"""Exam definition and publication lifecycle (PRD §9, §11.1, §27.3).

Phase 1a covers DRAFT → READY (publish), READY → DRAFT (unpublish, only without enrollments)
and DRAFT/READY → CANCELLED. RUNNING/CLOSED/FINALIZED are driven by the scheduler in Phase 1b.
"""
from datetime import timedelta
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import audit, clock, emailer, settings_service
from ..config import get_settings
from ..errors import AppError, conflict, invalid, not_found
from ..models import Attempt, Enrollment, Exam, Organization
from ..principal import Principal
from ..schemas import ExamCreateIn, ExamPatchIn, SecurityPolicy
from ..security import hash_password

DEFAULT_LATEST_START = timedelta(minutes=30)
DEFAULT_CHECKIN_LEAD = timedelta(minutes=30)
EDITABLE_STATUSES = {"DRAFT"}


def get_exam(db: Session, org_id: UUID, exam_id: UUID) -> Exam:
    exam = db.scalar(select(Exam).where(Exam.id == exam_id, Exam.org_id == org_id))
    if exam is None:
        raise not_found("exam")
    return exam


def list_exams(db: Session, org_id: UUID, status: str | None = None) -> list[Exam]:
    q = select(Exam).where(Exam.org_id == org_id)
    if status:
        q = q.where(Exam.status == status)
    return list(db.scalars(q.order_by(Exam.window_start.desc().nulls_last(), Exam.created_at.desc())))


def to_out(exam: Exam) -> dict[str, Any]:
    data = {c.key: getattr(exam, c.key) for c in Exam.__table__.columns}
    data["has_access_code"] = exam.access_code_hash is not None
    return data


def _origin(url: str) -> str | None:
    parts = urlsplit(url)
    if not parts.scheme or not parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}"


def _apply_fields(exam: Exam, data: dict[str, Any]) -> dict[str, Any]:
    changes: dict[str, Any] = {}
    for key, value in data.items():
        if key == "access_code":
            exam.access_code_hash = hash_password(value) if value else None
            changes["access_code"] = "set" if value else "removed"
            continue
        if key == "policy":
            value = SecurityPolicy.model_validate(value).model_dump() if value is not None else {}
        if key == "allowed_origins" and value is not None:
            value = sorted({o.rstrip("/") for o in value})
        if getattr(exam, key) != value:
            changes[key] = value
            setattr(exam, key, value)
    return changes


def create_exam(db: Session, actor: Principal, body: ExamCreateIn) -> Exam:
    org = db.get(Organization, actor.org_id)
    data = body.model_dump(exclude_unset=True)
    exam = Exam(org_id=org.id, code=body.code, name=body.name, visibility=body.visibility,
                status="DRAFT", created_by=actor.id, allowed_origins=[], settings={},
                policy=SecurityPolicy().model_dump())
    if "identity_check" not in data:
        key = "default_identity_check_public" if body.visibility == "PUBLIC" else "default_identity_check_private"
        exam.identity_check = settings_service.value(db, org, key)
    for k in ("code", "name", "visibility"):
        data.pop(k, None)
    _apply_fields(exam, data)
    db.add(exam)
    try:
        db.flush()
    except IntegrityError:
        raise conflict("EXAM_CODE_TAKEN", f"exam code '{body.code}' already exists") from None
    audit.record(db, org_id=org.id, actor_kind=actor.actor_kind, actor_id=actor.id,
                 action="exam.created", target_type="exam", target_id=exam.id,
                 data={"code": exam.code, "visibility": exam.visibility})
    return exam


def patch_exam(db: Session, actor: Principal, exam_id: UUID, body: ExamPatchIn) -> Exam:
    exam = get_exam(db, actor.org_id, exam_id)
    if exam.status not in EDITABLE_STATUSES:
        raise conflict("EXAM_NOT_EDITABLE", f"exam in status {exam.status} cannot be edited; unpublish it first")
    changes = _apply_fields(exam, body.model_dump(exclude_unset=True))
    if changes:
        exam.updated_at = clock.now()
        audit.record(db, org_id=exam.org_id, actor_kind=actor.actor_kind, actor_id=actor.id,
                     action="exam.updated", target_type="exam", target_id=exam.id, data=changes)
    return exam


def publication_problems(exam: Exam, org: Organization) -> list[dict[str, str]]:
    """Everything that blocks DRAFT → READY. Assumes defaults were already filled in."""
    p: list[dict[str, str]] = []

    def add(field: str, problem: str) -> None:
        p.append({"field": field, "problem": problem})

    now = clock.now()
    if not exam.exam_url:
        add("exam_url", "required")
    else:
        u = urlsplit(exam.exam_url)
        local = u.hostname in ("localhost", "127.0.0.1")
        if u.scheme != "https" and not (u.scheme == "http" and local and get_settings().is_dev):
            add("exam_url", "must use https")
    for o in exam.allowed_origins:
        if _origin(o) != o:
            add("allowed_origins", f"'{o}' is not an origin (scheme://host[:port])")
    if not exam.window_start or not exam.window_end:
        add("window", "window_start and window_end are required")
    else:
        if exam.window_start >= exam.window_end:
            add("window_end", "must be after window_start")
        if exam.window_start <= now:
            add("window_start", "must be in the future")
        if exam.latest_start and not exam.window_start <= exam.latest_start <= exam.window_end:
            add("latest_start", "must be between window_start and window_end")
        if exam.checkin_open and exam.checkin_open > exam.window_start:
            add("checkin_open", "must not be after window_start")
    if exam.late_start_policy == "FULL_DURATION" and not exam.duration_minutes:
        add("duration_minutes", "required when late_start_policy is FULL_DURATION")
    if exam.visibility == "PUBLIC":
        if not org.can_publish_public:
            add("visibility", "organization is not allowed to publish public exams")
        if not exam.registration_open or not exam.registration_close:
            add("registration", "registration_open and registration_close are required for public exams")
        elif exam.registration_open >= exam.registration_close:
            add("registration_close", "must be after registration_open")
        elif exam.window_start and exam.registration_close > exam.window_start:
            add("registration_close", "must not be after window_start")
    pol = exam.policy or {}
    if (pol.get("face_detection") or pol.get("person_detection")) and not pol.get("require_camera"):
        add("policy", "face/person detection requires require_camera")
    if pol.get("voice_activity_detection") and not pol.get("require_microphone"):
        add("policy", "voice activity detection requires require_microphone")
    if pol.get("evidence_snapshot") and not pol.get("require_camera"):
        add("policy", "evidence_snapshot requires require_camera")
    if pol.get("block_virtual_machines"):
        add("policy", "blocking virtual machines is not available yet (warn-only in MVP)")
    if pol.get("block_wsl"):
        add("policy", "blocking WSL is not available yet (roadmap)")
    if exam.identity_check == "MANUAL" and not pol.get("require_camera"):
        add("identity_check", "MANUAL identity check requires require_camera")
    return p


def _fill_defaults(exam: Exam) -> None:
    if exam.window_start and exam.window_end:
        if exam.latest_start is None:
            exam.latest_start = min(exam.window_start + DEFAULT_LATEST_START, exam.window_end)
        if exam.checkin_open is None:
            exam.checkin_open = exam.window_start - DEFAULT_CHECKIN_LEAD
    if exam.exam_url:
        origin = _origin(exam.exam_url)
        if origin and origin not in exam.allowed_origins:
            exam.allowed_origins = sorted({*exam.allowed_origins, origin})


def publish(db: Session, actor: Principal, exam_id: UUID) -> Exam:
    exam = get_exam(db, actor.org_id, exam_id)
    if exam.status != "DRAFT":
        raise conflict("INVALID_TRANSITION", f"cannot publish an exam in status {exam.status}")
    org = db.get(Organization, exam.org_id)
    _fill_defaults(exam)
    problems = publication_problems(exam, org)
    if problems:
        raise invalid("EXAM_NOT_PUBLISHABLE", "exam cannot be published", problems)
    exam.status = "READY"
    exam.updated_at = clock.now()
    audit.record(db, org_id=exam.org_id, actor_kind=actor.actor_kind, actor_id=actor.id,
                 action="exam.published", target_type="exam", target_id=exam.id,
                 data={"latest_start": exam.latest_start, "checkin_open": exam.checkin_open,
                       "allowed_origins": exam.allowed_origins})
    return exam


def unpublish(db: Session, actor: Principal, exam_id: UUID) -> Exam:
    exam = get_exam(db, actor.org_id, exam_id)
    if exam.status != "READY":
        raise conflict("INVALID_TRANSITION", f"cannot unpublish an exam in status {exam.status}")
    has_enrollments = db.scalar(select(Enrollment.id).where(
        Enrollment.exam_id == exam.id, Enrollment.status == "CONFIRMED").limit(1))
    if has_enrollments:
        raise conflict("EXAM_HAS_ENROLLMENTS", "exam has confirmed enrollments; cancel the exam instead")
    exam.status = "DRAFT"
    audit.record(db, org_id=exam.org_id, actor_kind=actor.actor_kind, actor_id=actor.id,
                 action="exam.unpublished", target_type="exam", target_id=exam.id)
    return exam


def cancel(db: Session, actor: Principal, exam_id: UUID, reason: str) -> Exam:
    exam = get_exam(db, actor.org_id, exam_id)
    if exam.status not in ("DRAFT", "READY"):
        raise conflict("INVALID_TRANSITION", f"cannot cancel an exam in status {exam.status}")
    now = clock.now()
    enrollments = list(db.scalars(select(Enrollment).where(
        Enrollment.exam_id == exam.id, Enrollment.status == "CONFIRMED")))
    for e in enrollments:
        e.status, e.cancelled_at, e.cancel_reason = "CANCELLED", now, "EXAM_CANCELLED"
        db.query(Attempt).filter(Attempt.enrollment_id == e.id,
                                 Attempt.status == "NOT_STARTED").delete()
        emailer.enqueue(db, e.candidate.email, "registration_cancelled", name=e.candidate.full_name,
                        exam_name=exam.name, reason=reason)
    exam.status, exam.registered_count, exam.updated_at = "CANCELLED", 0, now
    audit.record(db, org_id=exam.org_id, actor_kind=actor.actor_kind, actor_id=actor.id,
                 action="exam.cancelled", target_type="exam", target_id=exam.id,
                 data={"reason": reason, "enrollments_cancelled": len(enrollments)})
    return exam


def exam_settings(db: Session, org_id: UUID, exam_id: UUID) -> dict[str, Any]:
    exam = get_exam(db, org_id, exam_id)
    org = db.get(Organization, org_id)
    return {"overrides": exam.settings, "effective": settings_service.resolve(db, org, exam)}


def patch_exam_settings(db: Session, actor: Principal, exam_id: UUID, overrides: dict[str, Any],
                        confirm_shorten: bool) -> dict[str, Any]:
    exam = get_exam(db, actor.org_id, exam_id)
    if exam.status in ("FINALIZED", "CANCELLED"):
        raise AppError(409, "EXAM_NOT_EDITABLE", f"settings of a {exam.status} exam are frozen")
    org = db.get(Organization, actor.org_id)
    settings_service.validate_overrides(db, overrides, allowed=settings_service.EXAM_LEVEL_KEYS)
    before = settings_service.resolve(db, org, exam)
    exam.settings = settings_service.merge(exam.settings, overrides)
    after = settings_service.resolve(db, org, exam)
    shortened = settings_service.check_retention_shortening(before, after, confirm_shorten)
    db.flush()
    audit.record(db, org_id=exam.org_id, actor_kind=actor.actor_kind, actor_id=actor.id,
                 action="settings.updated", target_type="exam", target_id=exam.id,
                 data={"patch": overrides, "retention_shortened": shortened})
    return {"overrides": exam.settings, "effective": after}
