"""Invigilator assignment per exam (PRD §7, §27.3)."""
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import access, audit, permissions as P
from ..errors import conflict, invalid, not_found
from ..models import InvigilatorAssignment, Membership, User
from ..principal import Principal


def list_assignments(db: Session, p: Principal, exam_id: UUID) -> list[dict[str, Any]]:
    access.require_exam(db, p, exam_id, P.MONITOR)
    rows = db.execute(select(InvigilatorAssignment, User).join(User, User.id == InvigilatorAssignment.user_id)
                      .where(InvigilatorAssignment.exam_id == exam_id)
                      .order_by(User.full_name)).all()
    return [{"user_id": u.id, "email": u.email, "full_name": u.full_name, "assigned_at": a.created_at}
            for a, u in rows]


def assign(db: Session, p: Principal, exam_id: UUID, user_id: UUID) -> dict[str, Any]:
    exam = access.require_exam(db, p, exam_id, P.ASSIGN)
    if exam.status in ("FINALIZED", "CANCELLED"):
        raise conflict("INVALID_STATE", f"exam is {exam.status}")
    is_invigilator = db.scalar(select(Membership.id).where(
        Membership.org_id == p.org_id, Membership.user_id == user_id, Membership.role == "INVIGILATOR"))
    if not is_invigilator:
        raise invalid("NOT_AN_INVIGILATOR", "user is not an INVIGILATOR of this organization")
    a = InvigilatorAssignment(exam_id=exam.id, user_id=user_id, created_by=p.id)
    db.add(a)
    try:
        with db.begin_nested():
            db.flush()
    except IntegrityError:
        raise conflict("ALREADY_ASSIGNED", "invigilator is already assigned to this exam") from None
    audit.record(db, org_id=exam.org_id, actor_kind=p.actor_kind, actor_id=p.id, action="invigilator.assigned",
                 target_type="exam", target_id=exam.id, data={"user_id": user_id})
    user = db.get(User, user_id)
    return {"user_id": user.id, "email": user.email, "full_name": user.full_name, "assigned_at": a.created_at}


def unassign(db: Session, p: Principal, exam_id: UUID, user_id: UUID) -> None:
    exam = access.require_exam(db, p, exam_id, P.ASSIGN)
    a = db.scalar(select(InvigilatorAssignment).where(InvigilatorAssignment.exam_id == exam.id,
                                                      InvigilatorAssignment.user_id == user_id))
    if a is None:
        raise not_found("assignment")
    db.delete(a)
    audit.record(db, org_id=exam.org_id, actor_kind=p.actor_kind, actor_id=p.id, action="invigilator.unassigned",
                 target_type="exam", target_id=exam.id, data={"user_id": user_id})


def assignable(db: Session, p: Principal) -> list[dict[str, Any]]:
    p.require(P.ASSIGN)
    rows = db.execute(select(User).join(Membership, Membership.user_id == User.id)
                      .where(Membership.org_id == p.org_id, Membership.role == "INVIGILATOR")
                      .order_by(User.full_name)).scalars().all()
    return [{"user_id": u.id, "email": u.email, "full_name": u.full_name} for u in rows]
