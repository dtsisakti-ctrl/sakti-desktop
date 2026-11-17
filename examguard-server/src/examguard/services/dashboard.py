"""Dashboard (PRD §27.2): one row per exam the caller may see, with live counts."""
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from .. import access, clock, sessions, state
from ..models import Attempt, DeviceSession, Enrollment, Exam, Incident
from ..principal import Principal

SHOWN = ("READY", "RUNNING", "CLOSED")


def dashboard(db: Session, p: Principal) -> dict[str, Any]:
    now = clock.now()
    visible = access.visible_exam_ids(db, p)
    q = select(Exam).where(Exam.org_id == p.org_id, Exam.status.in_(SHOWN)).order_by(Exam.window_start)
    if visible is not None:
        q = q.where(Exam.id.in_(visible))
    exams = list(db.scalars(q))
    ids = [e.id for e in exams]
    per_exam: dict[UUID, dict[str, int]] = {i: {"enrolled": 0, "online": 0, "interrupted": 0, "waiting": 0,
                                                 "paused": 0, "ended": 0, "open_incidents": 0} for i in ids}
    if ids:
        rows = db.execute(
            select(Enrollment.exam_id, Attempt.status, DeviceSession)
            .join(Attempt, Attempt.enrollment_id == Enrollment.id)
            .outerjoin(DeviceSession, and_(DeviceSession.attempt_id == Attempt.id, DeviceSession.status == "ACTIVE"))
            .where(Enrollment.exam_id.in_(ids), Enrollment.status == "CONFIRMED")).all()
        thresholds = {e.id: sessions.offline_threshold(db, e) for e in exams}
        for exam_id, status, ds in rows:
            c = per_exam[exam_id]
            c["enrolled"] += 1
            if status in state.LIVE and sessions.connection_status(ds, now, thresholds[exam_id]) == "ONLINE":
                c["online"] += 1
            c["interrupted"] += status == state.INTERRUPTED
            c["waiting"] += status == state.WAITING
            c["paused"] += status == state.PAUSED
            c["ended"] += status in state.FINAL
        for exam_id, n in db.execute(
                select(Enrollment.exam_id, func.count()).join(Attempt, Attempt.enrollment_id == Enrollment.id)
                .join(Incident, Incident.attempt_id == Attempt.id)
                .where(Enrollment.exam_id.in_(ids), Incident.status == "OPEN").group_by(Enrollment.exam_id)).all():
            per_exam[exam_id]["open_incidents"] = n
    total = {k: sum(c[k] for c in per_exam.values()) for k in ("online", "interrupted", "waiting", "open_incidents")}
    total["running_exams"] = sum(e.status == "RUNNING" for e in exams)
    soon = now + timedelta(hours=24)
    return {
        "server_time": now,
        "totals": total,
        "exams": [{
            "id": e.id, "code": e.code, "name": e.name, "status": e.status, "visibility": e.visibility,
            "window_start": e.window_start, "latest_start": e.latest_start, "window_end": e.window_end,
            "checkin_open": e.checkin_open, "identity_check": e.identity_check,
            "starts_within_24h": e.status == "READY" and e.window_start is not None and e.window_start <= soon,
            **per_exam[e.id],
        } for e in exams],
    }
