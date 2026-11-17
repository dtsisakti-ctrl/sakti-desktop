"""Candidate-facing API (Candidate Portal backend) and the public catalog."""
from uuid import UUID

from fastapi import APIRouter, Query, status

from ..schemas import (CandidateEnrollmentOut, LaunchLinkOut, CandidateOut, CandidateSignupIn, CatalogExamOut,
                       InvitationPreviewOut, LoginIn, MoveIn, PasswordChangeIn, PasswordResetIn, ProfileIn, RegisterIn,
                       ResendVerificationIn, SessionOut, TokenIn)
from ..services import auth, protocol, registration
from .deps import DB, CurrentCandidate, Token

public = APIRouter(prefix="/api/v1/public", tags=["public"])
router = APIRouter(prefix="/api/v1/candidate", tags=["candidate"])


@public.get("/exams", response_model=list[CatalogExamOut])
def public_catalog(db: DB, series: str | None = Query(default=None, max_length=100)):
    """Public exams with registration not yet closed (anonymous)."""
    return registration.catalog(db, series)


@public.post("/invitations/preview", response_model=InvitationPreviewOut)
def invitation_preview(db: DB, body: TokenIn):
    """Exam and addressee of an invitation link, so the portal can show it before sign-in (anonymous)."""
    return registration.invitation_preview(db, body.token)


@router.post("/auth/signup", response_model=CandidateOut, status_code=status.HTTP_201_CREATED)
def signup(db: DB, body: CandidateSignupIn):
    return auth.signup_candidate(db, body.email, body.password, body.full_name)


@router.post("/auth/resend-verification", status_code=status.HTTP_202_ACCEPTED)
def resend_verification(db: DB, body: ResendVerificationIn):
    auth.resend_verification(db, body.email)
    return {"status": "accepted"}


@router.post("/auth/verify-email")
def verify_email(db: DB, body: TokenIn):
    auth.verify_email(db, body.token)
    return {"status": "verified"}


@router.post("/auth/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
def password_reset_request(db: DB, body: ResendVerificationIn):
    """Sends a reset link if the account exists; the answer is the same either way."""
    auth.request_password_reset(db, body.email)
    return {"status": "accepted"}


@router.post("/auth/password-reset/confirm")
def password_reset_confirm(db: DB, body: PasswordResetIn):
    """Sets the new password and signs out every session of the account."""
    auth.reset_password(db, body.token, body.password)
    return {"status": "password_changed"}


@router.post("/auth/login", response_model=SessionOut)
def login(db: DB, body: LoginIn):
    token, expires = auth.login(db, "CANDIDATE", body.email, body.password)
    return {"token": token, "kind": "CANDIDATE", "expires_at": expires}


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(db: DB, cand: CurrentCandidate, token: Token):
    auth.logout(db, token)


@router.get("/me", response_model=CandidateOut)
def me(cand: CurrentCandidate):
    return cand


@router.patch("/me", response_model=CandidateOut)
def update_me(db: DB, cand: CurrentCandidate, body: ProfileIn):
    """Name as on the identity document (shown to invigilators and in the check-in queue)."""
    return auth.update_profile(db, cand.id, body.full_name)


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(db: DB, cand: CurrentCandidate, token: Token, body: PasswordChangeIn):
    """Other sessions are signed out; this one stays."""
    auth.change_password(db, cand.id, body.current_password, body.new_password, token)


@router.get("/enrollments", response_model=list[CandidateEnrollmentOut])
def my_enrollments(db: DB, cand: CurrentCandidate):
    return registration.my_enrollments(db, cand)


@router.post("/exams/{exam_id}/register", status_code=status.HTTP_201_CREATED)
def register(db: DB, cand: CurrentCandidate, exam_id: UUID, body: RegisterIn):
    enr = registration.register(db, cand, exam_id, body.access_code)
    return {"enrollment_id": enr.id, "status": enr.status}


@router.post("/enrollments/{enrollment_id}/cancel")
def cancel(db: DB, cand: CurrentCandidate, enrollment_id: UUID):
    enr = registration.cancel_own(db, cand, enrollment_id)
    return {"enrollment_id": enr.id, "status": enr.status}


@router.post("/enrollments/{enrollment_id}/move", status_code=status.HTTP_201_CREATED)
def move(db: DB, cand: CurrentCandidate, enrollment_id: UUID, body: MoveIn):
    enr = registration.move_own(db, cand, enrollment_id, body.target_exam_id, body.access_code)
    return {"enrollment_id": enr.id, "exam_id": enr.exam_id, "status": enr.status}


@router.post("/invitations/accept", status_code=status.HTTP_201_CREATED)
def accept_invitation(db: DB, cand: CurrentCandidate, body: TokenIn):
    enr = registration.accept_invitation(db, cand, body.token)
    return {"enrollment_id": enr.id, "exam_id": enr.exam_id, "status": enr.status}


@router.post("/enrollments/{enrollment_id}/launch", response_model=LaunchLinkOut)
def launch_link(db: DB, cand: CurrentCandidate, enrollment_id: UUID):
    """Single-use launch link for the ExamGuard Client (valid 15 minutes, PRD §12.1).

    Only from check-in opening until the latest start time, or while the attempt is running (relaunch)."""
    return protocol.issue_launch_token(db, cand, enrollment_id, enforce_window=True)
