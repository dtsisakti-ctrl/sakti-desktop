"""Exam-scoped authorization for staff (PRD §7).

ORG_ADMIN/EXAM_ADMIN permissions cover every exam of the organization; INVIGILATOR
permissions only cover exams the user is assigned to. Missing objects answer 404 before
any permission check, so data of other organizations never leaks (RLS hides it anyway).
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from .errors import forbidden, not_found
from .models import Enrollment, Exam, InvigilatorAssignment
from .permissions import unscoped_permissions
from .principal import Principal


def is_assigned(db: Session, exam_id: UUID, user_id: UUID) -> bool:
    return db.scalar(select(InvigilatorAssignment.id).where(
        InvigilatorAssignment.exam_id == exam_id, InvigilatorAssignment.user_id == user_id)) is not None


def can(db: Session, p: Principal, exam_id: UUID, permission: str) -> bool:
    if permission in unscoped_permissions(p.roles):
        return True
    return (permission in p.permissions and "INVIGILATOR" in p.roles
            and is_assigned(db, exam_id, p.id))


def require_exam(db: Session, p: Principal, exam_id: UUID, permission: str) -> Exam:
    exam = db.scalar(select(Exam).where(Exam.id == exam_id, Exam.org_id == p.org_id))
    if exam is None:
        raise not_found("exam")
    if not can(db, p, exam_id, permission):
        raise forbidden(f"missing permission {permission} for this exam")
    return exam


def exam_id_of_attempt(db: Session, org_id: UUID, attempt_id: UUID) -> UUID:
    from .models import Attempt
    exam_id = db.scalar(select(Enrollment.exam_id).join(Attempt, Attempt.enrollment_id == Enrollment.id)
                        .where(Attempt.id == attempt_id, Attempt.org_id == org_id))
    if exam_id is None:
        raise not_found("attempt")
    return exam_id


def visible_exam_ids(db: Session, p: Principal) -> list[UUID] | None:
    """None = all exams of the organization; otherwise the assigned exams only."""
    if "exam.read" in p.permissions:
        return None
    return list(db.scalars(select(InvigilatorAssignment.exam_id).where(
        InvigilatorAssignment.user_id == p.id, InvigilatorAssignment.org_id == p.org_id)))
