"""Accounts, sessions and email verification (staff and candidates)."""
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from .. import audit, clock, emailer
from ..config import get_settings
from ..db import elevated
from ..errors import AppError, conflict, invalid
from ..models import AuthSession, Candidate, OneTimeToken, User
from ..security import hash_password, new_token, token_hash, verify_password

UNAUTHORIZED = AppError(401, "UNAUTHORIZED", "missing, invalid or expired session")


def check_password_strength(password: str) -> None:
    min_len = get_settings().min_password_length
    if len(password) < min_len:
        raise invalid("WEAK_PASSWORD", f"password must be at least {min_len} characters")


def _issue_email_verification(db: Session, cand: Candidate) -> None:
    token = new_token()
    with elevated(db):
        db.add(OneTimeToken(
            token_hash=token_hash(token), purpose="EMAIL_VERIFY", subject_id=cand.id,
            expires_at=clock.now() + timedelta(hours=get_settings().email_verify_hours),
        ))
    emailer.enqueue(db, cand.email, "candidate_verify_email", name=cand.full_name, token=token)


def signup_candidate(db: Session, email: str, password: str, full_name: str) -> Candidate:
    check_password_strength(password)
    with elevated(db):
        exists = db.scalar(select(Candidate.id).where(func.lower(Candidate.email) == email.lower()))
        if exists:
            raise conflict("EMAIL_ALREADY_REGISTERED", "an account with this email already exists")
        cand = Candidate(email=email, full_name=full_name.strip(), password_hash=hash_password(password))
        db.add(cand)
        db.flush()
        audit.record(db, org_id=None, actor_kind="candidate", actor_id=cand.id,
                     action="candidate.signed_up", target_type="candidate", target_id=cand.id)
    _issue_email_verification(db, cand)
    return cand


def resend_verification(db: Session, email: str) -> None:
    """Always succeeds from the caller's view, to avoid account enumeration."""
    with elevated(db):
        cand = db.scalar(select(Candidate).where(func.lower(Candidate.email) == email.lower()))
    if cand and cand.email_verified_at is None:
        _issue_email_verification(db, cand)


def verify_email(db: Session, token: str) -> None:
    now = clock.now()
    with elevated(db):
        ott = db.scalar(select(OneTimeToken).where(
            OneTimeToken.token_hash == token_hash(token), OneTimeToken.purpose == "EMAIL_VERIFY"))
        if ott is None or ott.used_at is not None or ott.expires_at <= now:
            raise invalid("INVALID_TOKEN", "verification token is invalid or expired")
        ott.used_at = now
        cand = db.get(Candidate, ott.subject_id)
        if cand.email_verified_at is None:
            cand.email_verified_at = now
        audit.record(db, org_id=None, actor_kind="candidate", actor_id=cand.id,
                     action="candidate.email_verified", target_type="candidate", target_id=cand.id)


def request_password_reset(db: Session, email: str) -> None:
    """Candidate 'forgot password' (PRD §28.1). Always succeeds from the caller's view (no enumeration)."""
    with elevated(db):
        cand = db.scalar(select(Candidate).where(func.lower(Candidate.email) == email.lower()))
        if cand is None or not cand.is_active:
            return
        minutes = get_settings().password_reset_minutes
        token = new_token()
        db.add(OneTimeToken(token_hash=token_hash(token), purpose="PASSWORD_RESET", subject_id=cand.id,
                            expires_at=clock.now() + timedelta(minutes=minutes)))
        audit.record(db, org_id=None, actor_kind="candidate", actor_id=cand.id,
                     action="candidate.password_reset_requested", target_type="candidate", target_id=cand.id)
    emailer.enqueue(db, cand.email, "candidate_password_reset", name=cand.full_name, token=token, minutes=minutes)


def _set_password(db: Session, cand: Candidate, new_password: str, now: datetime, *,
                  keep_session: str | None = None) -> None:
    """New password; every other session of the account is signed out."""
    check_password_strength(new_password)
    cand.password_hash = hash_password(new_password)
    q = update(AuthSession).where(AuthSession.subject_kind == "CANDIDATE", AuthSession.subject_id == cand.id,
                                  AuthSession.revoked_at.is_(None))
    if keep_session:
        q = q.where(AuthSession.token_hash != token_hash(keep_session))
    db.execute(q.values(revoked_at=now))


def reset_password(db: Session, token: str, new_password: str) -> None:
    now = clock.now()
    check_password_strength(new_password)
    with elevated(db):
        ott = db.scalar(select(OneTimeToken).where(
            OneTimeToken.token_hash == token_hash(token), OneTimeToken.purpose == "PASSWORD_RESET")
            .with_for_update())
        if ott is None or ott.used_at is not None or ott.expires_at <= now:
            raise invalid("INVALID_TOKEN", "reset link is invalid, used or expired")
        cand = db.get(Candidate, ott.subject_id)
        ott.used_at = now
        # older unused reset links stop working as well
        db.execute(update(OneTimeToken).where(OneTimeToken.purpose == "PASSWORD_RESET",
                                              OneTimeToken.subject_id == cand.id, OneTimeToken.used_at.is_(None))
                   .values(used_at=now))
        _set_password(db, cand, new_password, now)
        if cand.email_verified_at is None:
            cand.email_verified_at = now          # the link proves the mailbox belongs to the candidate
        audit.record(db, org_id=None, actor_kind="candidate", actor_id=cand.id,
                     action="candidate.password_reset", target_type="candidate", target_id=cand.id)


def change_password(db: Session, cand_id: UUID, current: str, new_password: str, session_token: str) -> None:
    now = clock.now()
    with elevated(db):
        cand = db.get(Candidate, cand_id)
        if not verify_password(current, cand.password_hash):
            raise AppError(403, "WRONG_PASSWORD", "current password is incorrect")
        _set_password(db, cand, new_password, now, keep_session=session_token)
        audit.record(db, org_id=None, actor_kind="candidate", actor_id=cand.id,
                     action="candidate.password_changed", target_type="candidate", target_id=cand.id)


def update_profile(db: Session, cand_id: UUID, full_name: str) -> Candidate:
    with elevated(db):
        cand = db.get(Candidate, cand_id)
        old = cand.full_name
        cand.full_name = full_name.strip()
        audit.record(db, org_id=None, actor_kind="candidate", actor_id=cand.id,
                     action="candidate.profile_updated", target_type="candidate", target_id=cand.id,
                     data={"full_name": {"from": old, "to": cand.full_name}})
        db.flush()
        return cand


def login(db: Session, kind: str, email: str, password: str) -> tuple[str, datetime]:
    model = User if kind == "STAFF" else Candidate
    with elevated(db):
        subject = db.scalar(select(model).where(func.lower(model.email) == email.lower()))
        ok = verify_password(password, subject.password_hash if subject else None)
        if not ok or not subject.is_active:
            raise AppError(401, "INVALID_CREDENTIALS", "email or password is incorrect")
        hours = get_settings().staff_session_hours if kind == "STAFF" else get_settings().candidate_session_hours
        token = new_token()
        expires = clock.now() + timedelta(hours=hours)
        db.add(AuthSession(token_hash=token_hash(token), subject_kind=kind,
                           subject_id=subject.id, expires_at=expires))
    return token, expires


def resolve_session(db: Session, token: str | None, kind: str) -> UUID:
    if not token:
        raise UNAUTHORIZED
    with elevated(db):
        sess = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash(token)))
    if (sess is None or sess.subject_kind != kind or sess.revoked_at is not None
            or sess.expires_at <= clock.now()):
        raise UNAUTHORIZED
    return sess.subject_id


def logout(db: Session, token: str) -> None:
    with elevated(db):
        db.execute(update(AuthSession).where(AuthSession.token_hash == token_hash(token))
                   .values(revoked_at=clock.now()))
