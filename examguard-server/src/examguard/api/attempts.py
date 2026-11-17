"""Live monitoring and attempt control (Admin Web backend, PRD §27.5–27.10, §27.13)."""
from uuid import UUID

from fastapi import APIRouter, Query, status

from ..schemas import (AddTimeIn, AllowReentryIn, AssignIn, AttemptActionOut, AttemptDetailOut, BulkIn,
                       ExamAttemptsOut, ExtendIn, FinalizeIn, ForceSubmitIn, IdentityReviewIn, InvigilatorOut,
                       PauseIn, RejectReentryIn, ReopenIn, ResumeIn, TerminateIn, WarningIn)
from ..services import attempts, dashboard, invigilators, lifecycle
from .deps import DB, OrgPrincipal

router = APIRouter(prefix="/api/v1/org", tags=["monitoring & control"])


# ------------------------------------------------------------------ dashboard
@router.get("/dashboard")
def get_dashboard(db: DB, p: OrgPrincipal):
    """Exams that are READY, RUNNING or CLOSED with live counts; invigilators see only their exams."""
    return dashboard.dashboard(db, p)


# ------------------------------------------------------------------ invigilators
@router.get("/invigilators")
def assignable_invigilators(db: DB, p: OrgPrincipal):
    """Members with the INVIGILATOR role, for the assignment picker (Exam Admin)."""
    return invigilators.assignable(db, p)


@router.get("/exams/{exam_id}/invigilators", response_model=list[InvigilatorOut])
def list_invigilators(db: DB, p: OrgPrincipal, exam_id: UUID):
    return invigilators.list_assignments(db, p, exam_id)


@router.post("/exams/{exam_id}/invigilators", response_model=InvigilatorOut, status_code=status.HTTP_201_CREATED)
def assign_invigilator(db: DB, p: OrgPrincipal, exam_id: UUID, body: AssignIn):
    return invigilators.assign(db, p, exam_id, body.user_id)


@router.delete("/exams/{exam_id}/invigilators/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def unassign_invigilator(db: DB, p: OrgPrincipal, exam_id: UUID, user_id: UUID):
    invigilators.unassign(db, p, exam_id, user_id)


# ------------------------------------------------------------------ monitoring
@router.get("/exams/{exam_id}/attempts", response_model=ExamAttemptsOut)
def exam_attempts(db: DB, p: OrgPrincipal, exam_id: UUID, status_: str | None = Query(None, alias="status")):
    """Live Monitoring: every confirmed candidate with status, connection and remaining time."""
    return attempts.exam_attempts(db, p, exam_id, status_)


@router.get("/exams/{exam_id}/reentry", response_model=list[dict])
def reentry_list(db: DB, p: OrgPrincipal, exam_id: UUID):
    """Interrupted Sessions & Re-entry Requests."""
    return attempts.waiting_list(db, p, exam_id)


@router.get("/attempts/{attempt_id}", response_model=AttemptDetailOut)
def attempt_detail(db: DB, p: OrgPrincipal, attempt_id: UUID):
    return attempts.attempt_detail(db, p, attempt_id)


# ------------------------------------------------------------------ single-attempt actions
@router.post("/attempts/{attempt_id}/warning", response_model=AttemptActionOut)
def send_warning(db: DB, p: OrgPrincipal, attempt_id: UUID, body: WarningIn):
    return attempts.warning(db, p, attempt_id, body.message)


@router.post("/attempts/{attempt_id}/pause", response_model=AttemptActionOut)
def pause(db: DB, p: OrgPrincipal, attempt_id: UUID, body: PauseIn):
    return attempts.pause(db, p, attempt_id, body.reason, body.timer_mode, body.expected_state_version)


@router.post("/attempts/{attempt_id}/resume", response_model=AttemptActionOut)
def resume(db: DB, p: OrgPrincipal, attempt_id: UUID, body: ResumeIn):
    return attempts.resume(db, p, attempt_id, body.reason, body.expected_state_version)


@router.post("/attempts/{attempt_id}/add-time", response_model=AttemptActionOut)
def add_time(db: DB, p: OrgPrincipal, attempt_id: UUID, body: AddTimeIn):
    return attempts.add_time(db, p, attempt_id, body.minutes, body.reason, body.expected_state_version)


@router.post("/attempts/{attempt_id}/force-submit", response_model=AttemptActionOut)
def force_submit(db: DB, p: OrgPrincipal, attempt_id: UUID, body: ForceSubmitIn):
    return attempts.force_submit(db, p, attempt_id, body.reason, body.expected_state_version)


@router.post("/attempts/{attempt_id}/terminate", response_model=AttemptActionOut)
def terminate(db: DB, p: OrgPrincipal, attempt_id: UUID, body: TerminateIn):
    return attempts.terminate(db, p, attempt_id, body.reason, body.reason_category, body.expected_state_version)


@router.post("/attempts/{attempt_id}/reentry/allow", response_model=AttemptActionOut)
def allow_reentry(db: DB, p: OrgPrincipal, attempt_id: UUID, body: AllowReentryIn):
    return attempts.allow_reentry(db, p, attempt_id, body.reason, body.expected_state_version)


@router.post("/attempts/{attempt_id}/reentry/reject", response_model=AttemptActionOut)
def reject_reentry(db: DB, p: OrgPrincipal, attempt_id: UUID, body: RejectReentryIn):
    return attempts.reject_reentry(db, p, attempt_id, body.reason, body.reason_category,
                                   body.expected_state_version)


@router.post("/attempts/{attempt_id}/reopen", response_model=AttemptActionOut)
def reopen(db: DB, p: OrgPrincipal, attempt_id: UUID, body: ReopenIn):
    return attempts.reopen(db, p, attempt_id, body.deadline, body.reason, body.expected_state_version)


@router.post("/attempts/{attempt_id}/reinstate", response_model=AttemptActionOut)
def reinstate(db: DB, p: OrgPrincipal, attempt_id: UUID, body: ReopenIn):
    return attempts.reinstate(db, p, attempt_id, body.deadline, body.reason, body.expected_state_version)


@router.post("/attempts/{attempt_id}/identity/approve")
def identity_approve(db: DB, p: OrgPrincipal, attempt_id: UUID, body: IdentityReviewIn):
    return attempts.review_identity(db, p, attempt_id, True, body.reason)


@router.post("/attempts/{attempt_id}/identity/reject")
def identity_reject(db: DB, p: OrgPrincipal, attempt_id: UUID, body: IdentityReviewIn):
    return attempts.review_identity(db, p, attempt_id, False, body.reason)


# ------------------------------------------------------------------ whole-exam actions
@router.post("/exams/{exam_id}/bulk")
def bulk_action(db: DB, p: OrgPrincipal, exam_id: UUID, body: BulkIn):
    return attempts.bulk(db, p, exam_id, body.action, body.attempt_ids, reason=body.reason, message=body.message,
                         minutes=body.minutes, timer_mode=body.timer_mode, reason_category=body.reason_category,
                         confirm_exam_code=body.confirm_exam_code)


@router.post("/exams/{exam_id}/extend")
def extend_exam(db: DB, p: OrgPrincipal, exam_id: UUID, body: ExtendIn):
    return lifecycle.extend(db, p, exam_id, body.minutes, body.reason)


@router.post("/exams/{exam_id}/finalize")
def finalize_exam(db: DB, p: OrgPrincipal, exam_id: UUID, body: FinalizeIn):
    return lifecycle.finalize(db, p, exam_id, body.reason)
