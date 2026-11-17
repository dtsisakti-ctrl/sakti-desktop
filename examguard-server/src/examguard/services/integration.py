"""Integration API LMS → Server (PRD §16.4, §16.5) and its management by the Org Admin.

Credentials: ``client_id`` + ``secret`` (HTTP Basic). The secret is 256 random bits and is shown
once; only its SHA-256 is stored. Each integration is bound to one organization, and every query
below is filtered by that organization.
"""
import hashlib
import hmac
import os
from datetime import timedelta
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit, clock, crypto, keys, sessions, state
from ..config import get_settings
from ..errors import AppError, conflict, invalid, not_found
from ..models import Attempt, Candidate, Enrollment, Exam, Integration, WebhookDelivery
from ..principal import Principal
from ..security import hash_password
from . import client_flow, protocol
from .registration import _create_enrollment

COMPLETION_TTL = timedelta(minutes=10)


def _sha(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def _check_url(url: str | None) -> str | None:
    if not url:
        return None
    parts = urlsplit(url)
    if parts.scheme not in ("https", "http") or not parts.netloc:
        raise invalid("INVALID_WEBHOOK_URL", "webhook_url must be an absolute http(s) URL")
    if parts.scheme != "https" and not get_settings().is_dev:
        raise invalid("INVALID_WEBHOOK_URL", "webhook_url must use https")
    return url


# ------------------------------------------------------------------ management (Org Admin)
def to_out(i: Integration) -> dict[str, Any]:
    return {"id": i.id, "name": i.name, "client_id": i.client_id, "webhook_url": i.webhook_url,
            "status": i.status, "created_at": i.created_at, "last_used_at": i.last_used_at}


def create(db: Session, p: Principal, name: str, webhook_url: str | None) -> dict[str, Any]:
    secret = "egs_" + crypto.b64u(os.urandom(32))
    row = Integration(org_id=p.org_id, name=name, client_id="egi_" + crypto.b64u(os.urandom(9)),
                      secret_hash=_sha(secret), webhook_url=_check_url(webhook_url), created_by=p.id)
    db.add(row)
    db.flush()
    db.refresh(row)
    audit.record(db, org_id=p.org_id, actor_kind=p.actor_kind, actor_id=p.id, action="integration.created",
                 target_type="integration", target_id=row.id, data={"name": name, "client_id": row.client_id})
    return {**to_out(row), "secret": secret}


def _own(db: Session, p: Principal, integration_id: UUID) -> Integration:
    row = db.scalar(select(Integration).where(Integration.id == integration_id, Integration.org_id == p.org_id))
    if row is None:
        raise not_found("integration")
    return row


def list_for(db: Session, p: Principal) -> list[dict[str, Any]]:
    return [to_out(i) for i in db.scalars(select(Integration).where(Integration.org_id == p.org_id)
                                          .order_by(Integration.created_at))]


def update(db: Session, p: Principal, integration_id: UUID, name: str | None, webhook_url: str | None,
           clear_webhook: bool) -> dict[str, Any]:
    row = _own(db, p, integration_id)
    if name:
        row.name = name
    if clear_webhook:
        row.webhook_url = None
    elif webhook_url is not None:
        row.webhook_url = _check_url(webhook_url)
    audit.record(db, org_id=p.org_id, actor_kind=p.actor_kind, actor_id=p.id, action="integration.updated",
                 target_type="integration", target_id=row.id, data={"name": row.name, "webhook_url": row.webhook_url})
    return to_out(row)


def rotate_secret(db: Session, p: Principal, integration_id: UUID) -> dict[str, Any]:
    row = _own(db, p, integration_id)
    if row.status != "ACTIVE":
        raise conflict("INTEGRATION_REVOKED", "integration is revoked")
    secret = "egs_" + crypto.b64u(os.urandom(32))
    row.secret_hash = _sha(secret)
    audit.record(db, org_id=p.org_id, actor_kind=p.actor_kind, actor_id=p.id, action="integration.secret_rotated",
                 target_type="integration", target_id=row.id)
    return {**to_out(row), "secret": secret}


def revoke(db: Session, p: Principal, integration_id: UUID) -> dict[str, Any]:
    row = _own(db, p, integration_id)
    row.status = "REVOKED"
    audit.record(db, org_id=p.org_id, actor_kind=p.actor_kind, actor_id=p.id, action="integration.revoked",
                 target_type="integration", target_id=row.id)
    return to_out(row)


def deliveries(db: Session, p: Principal, integration_id: UUID, limit: int = 50) -> list[dict[str, Any]]:
    _own(db, p, integration_id)
    rows = db.scalars(select(WebhookDelivery).where(WebhookDelivery.integration_id == integration_id)
                      .order_by(WebhookDelivery.created_at.desc()).limit(limit))
    return [{"event_id": d.id, "event_type": d.event_type, "status": d.status, "attempts": d.attempts,
             "last_status_code": d.last_status_code, "last_error": d.last_error, "created_at": d.created_at,
             "delivered_at": d.delivered_at, "next_attempt_at": d.next_attempt_at, "payload": d.payload}
            for d in rows]


# ------------------------------------------------------------------ authentication (LMS)
def authenticate(db: Session, client_id: str | None, secret: str | None) -> Integration:
    row = db.scalar(select(Integration).where(Integration.client_id == (client_id or "")))
    # compare even when the row is missing, so timing does not reveal valid client ids
    expected = row.secret_hash if row else _sha("x")
    if not (row and hmac.compare_digest(expected, _sha(secret or "")) and row.status == "ACTIVE"):
        raise AppError(401, "INVALID_CREDENTIALS", "invalid or revoked integration credentials")
    row.last_used_at = clock.now()
    return row


def _audit(db: Session, integ: Integration, action: str, target_type: str, target_id: UUID,
           data: dict[str, Any] | None = None) -> None:
    audit.record(db, org_id=integ.org_id, actor_kind="integration", actor_id=integ.id, action=action,
                 target_type=target_type, target_id=target_id, data=data)


def _exam(db: Session, integ: Integration, exam_id: UUID) -> Exam:
    exam = db.scalar(select(Exam).where(Exam.id == exam_id, Exam.org_id == integ.org_id))
    if exam is None:
        raise not_found("exam")
    return exam


def _attempt(db: Session, integ: Integration, attempt_id: UUID) -> tuple[Attempt, Enrollment]:
    attempt = db.scalar(select(Attempt).where(Attempt.id == attempt_id, Attempt.org_id == integ.org_id))
    if attempt is None:
        raise not_found("attempt")
    return attempt, db.get(Enrollment, attempt.enrollment_id)


# ------------------------------------------------------------------ LMS endpoints
def list_exams(db: Session, integ: Integration) -> list[dict[str, Any]]:
    rows = db.scalars(select(Exam).where(Exam.org_id == integ.org_id, Exam.status != "CANCELLED")
                      .order_by(Exam.window_start))
    return [{"exam_id": e.id, "code": e.code, "name": e.name, "status": e.status, "window_start": e.window_start,
             "window_end": e.window_end, "latest_start": e.latest_start, "integration_level": e.integration_level}
            for e in rows]


def attempt_view(db: Session, integ: Integration, attempt_id: UUID) -> dict[str, Any]:
    attempt, enr = _attempt(db, integ, attempt_id)
    return {"attempt_id": attempt.id, "exam_id": enr.exam_id, "enrollment_id": enr.id,
            "candidate_ref": enr.external_ref, "status": attempt.status, "state_version": attempt.state_version,
            "deadline": attempt.deadline, "started_at": attempt.started_at, "ended_at": attempt.ended_at,
            "server_time": clock.now(), "result": attempt.result}


def _link(db: Session, cand: Candidate, enr: Enrollment) -> dict[str, Any] | None:
    try:
        r = protocol.issue_launch_token(db, cand, enr.id)
    except AppError as e:
        if e.code in ("EXAM_NOT_OPEN", "ATTEMPT_ENDED"):
            return None      # e.g. exam still DRAFT: ask for a link later via /attempts/{id}/launch
        raise
    return {"launch_url": r["launch_url"], "launch_token": r["launch_token"], "expires_at": r["expires_at"]}


def register_candidate(db: Session, integ: Integration, exam_id: UUID, *, email: str, full_name: str,
                       external_ref: str, accommodation: int) -> dict[str, Any]:
    exam = _exam(db, integ, exam_id)
    if exam.status not in ("DRAFT", "READY"):     # PRD Q13: no new enrollments once RUNNING
        raise conflict("ENROLLMENT_CLOSED", f"exam is {exam.status}")
    enr = db.scalar(select(Enrollment).where(Enrollment.exam_id == exam.id, Enrollment.external_ref == external_ref,
                                             Enrollment.status == "CONFIRMED"))
    created = False
    if enr is None:
        cand = db.scalar(select(Candidate).where(func.lower(Candidate.email) == email.lower()))
        if cand is None:
            # LMS candidates launch through links; a random password keeps the portal login closed
            cand = Candidate(email=email, full_name=full_name, password_hash=hash_password(crypto.b64u(os.urandom(24))),
                             email_verified_at=clock.now())
            db.add(cand)
            db.flush()
        existing = db.scalar(select(Enrollment).where(Enrollment.exam_id == exam.id, Enrollment.candidate_id == cand.id,
                                                      Enrollment.status == "CONFIRMED"))
        if existing is not None:
            if existing.external_ref not in (None, external_ref):
                raise conflict("ALREADY_REGISTERED", "this email is enrolled under another candidate_ref")
            enr = existing
            enr.external_ref = external_ref
        else:
            enr = _create_enrollment(db, exam, cand, "API")
            enr.external_ref, enr.integration_id = external_ref, integ.id
            created = True
        enr.time_accommodation_minutes = accommodation
        _audit(db, integ, "integration.candidate_registered", "enrollment", enr.id,
               {"external_ref": external_ref, "created": created})
    cand = db.get(Candidate, enr.candidate_id)
    attempt = db.scalar(select(Attempt).where(Attempt.enrollment_id == enr.id))
    return {"enrollment_id": enr.id, "attempt_id": attempt.id, "candidate_id": cand.id,
            "candidate_ref": enr.external_ref, "created": created, "launch": _link(db, cand, enr)}


def launch_link(db: Session, integ: Integration, attempt_id: UUID) -> dict[str, Any]:
    _, enr = _attempt(db, integ, attempt_id)
    link = _link(db, db.get(Candidate, enr.candidate_id), enr)
    if link is None:
        raise conflict("NOT_LAUNCHABLE", "the exam is not open or the attempt has ended")
    return link


def _completion_token(db: Session, attempt: Attempt, enr: Enrollment) -> dict[str, Any]:
    """Signed proof for the client that the LMS saved the final answers (PRD §16.5)."""
    now = clock.now()
    ds = sessions.active(db, attempt.id)
    claims = {"typ": "completion", "iss": get_settings().public_base_url, "aud": "examguard-client",
              "exam_id": str(enr.exam_id), "attempt_id": str(attempt.id),
              "device_session_id": str(ds.id) if ds else None, "state_version": attempt.state_version,
              "nonce": crypto.b64u(os.urandom(16)), "iat": int(now.timestamp()),
              "exp": int((now + COMPLETION_TTL).timestamp())}
    kid, key = keys.signer(db, "token")
    return {"completion_token": crypto.jwt_encode(kid, key, claims), "expires_at": now + COMPLETION_TTL,
            "status": attempt.status, "state_version": attempt.state_version}


def completion(db: Session, integ: Integration, attempt_id: UUID) -> dict[str, Any]:
    attempt, enr = _attempt(db, integ, attempt_id)
    attempt = state.lock_attempt(db, attempt.id)
    if attempt.status == state.ACTIVE:
        client_flow.submit(db, attempt.id, actor_kind="integration", actor_id=integ.id, source="LMS_COMPLETION")
    elif attempt.status != state.SUBMITTED:
        raise conflict("ATTEMPT_NOT_ACTIVE", f"attempt is {attempt.status}; answers must not be accepted",
                       {"status": attempt.status, "state_version": attempt.state_version})
    # SUBMITTED already (retry after a lost response): issue a fresh token, no second transition.
    return _completion_token(db, attempt, enr)


def save_result(db: Session, integ: Integration, attempt_id: UUID, result: dict[str, Any]) -> dict[str, Any]:
    attempt, _ = _attempt(db, integ, attempt_id)
    if attempt.status not in state.FINAL:
        raise conflict("ATTEMPT_NOT_FINAL", f"attempt is {attempt.status}")
    attempt.result, attempt.result_at = result, clock.now()
    _audit(db, integ, "integration.result_saved", "attempt", attempt.id, {"keys": sorted(result)})
    return {"attempt_id": attempt.id, "result": attempt.result, "result_at": attempt.result_at}
