"""Check-in photos (PRD §12.5, §27.13), emergency unlock (§22) and incident review (§27.8)."""
import base64
import binascii
import hashlib
import hmac
import os
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import access, audit, clock, commands, crypto, permissions as P, state, storage
from ..config import get_settings
from ..errors import conflict, invalid, not_found
from ..models import (Attempt, BackupCode, Candidate, DeviceSession, Enrollment, Event, Exam, IdentityPhoto,
                      Incident)
from ..principal import Principal
from . import client_flow

_MAGIC = {"image/jpeg": (b"\xff\xd8\xff",), "image/png": (b"\x89PNG\r\n\x1a\n",), "image/webp": (b"RIFF",)}


# ------------------------------------------------------------------ identity photos
def _decode_image(b64: str, content_type: str, label: str) -> bytes:
    try:
        data = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError):
        raise invalid("INVALID_IMAGE", f"{label} is not valid base64") from None
    if not data or len(data) > get_settings().identity_photo_max_bytes:
        raise invalid("IMAGE_TOO_LARGE", f"{label} must be 1 byte – {get_settings().identity_photo_max_bytes} bytes")
    if not data.startswith(_MAGIC[content_type]):
        raise invalid("INVALID_IMAGE", f"{label} is not a {content_type} file")
    return data


def submit_photos(db: Session, ds: DeviceSession, selfie_b64: str, id_card_b64: str, content_type: str) -> None:
    """Client uploads selfie + ID card; the attempt enters the Check-in Queue (PENDING)."""
    if ds.status != "ACTIVE":
        raise conflict("DEVICE_NOT_ACTIVE", "only the active device can submit the identity check")
    photos = {"SELFIE": _decode_image(selfie_b64, content_type, "selfie"),
              "ID_CARD": _decode_image(id_card_b64, content_type, "id_card")}
    client_flow.submit_identity(db, ds.attempt_id)        # status/retry rules; raises if not allowed
    attempt = db.get(Attempt, ds.attempt_id)
    submission = attempt.identity_rejections + 1
    store = storage.get_storage()
    now = clock.now()
    for kind, data in photos.items():
        key = f"identity/{attempt.org_id}/{attempt.id}/{submission}-{kind.lower()}-{uuid4().hex}.bin"
        store.put(key, data)
        db.add(IdentityPhoto(attempt_id=attempt.id, submission=submission, kind=kind, storage_key=key,
                             content_type=content_type, size_bytes=len(data),
                             sha256=hashlib.sha256(data).hexdigest(), created_at=now))
    db.flush()


def checkin_queue(db: Session, p: Principal, exam_id: UUID) -> list[dict[str, Any]]:
    exam = access.require_exam(db, p, exam_id, P.IDENTITY)
    rows = db.execute(select(Attempt, Candidate).join(Enrollment, Enrollment.id == Attempt.enrollment_id)
                      .join(Candidate, Candidate.id == Enrollment.candidate_id)
                      .where(Enrollment.exam_id == exam.id, Attempt.identity_status == "PENDING")
                      .order_by(Attempt.updated_at)).all()
    out = []
    for a, c in rows:
        submission = a.identity_rejections + 1
        photos = db.scalars(select(IdentityPhoto).where(IdentityPhoto.attempt_id == a.id,
                                                        IdentityPhoto.submission == submission))
        out.append({"attempt_id": a.id, "candidate_name": c.full_name, "candidate_email": c.email,
                    "submission": submission, "retries_left": 3 - a.identity_rejections,
                    "photos": [{"id": ph.id, "kind": ph.kind, "url": f"/api/v1/org/identity-photos/{ph.id}",
                                "created_at": ph.created_at} for ph in photos]})
    return out


def photo(db: Session, p: Principal, photo_id: UUID) -> tuple[bytes, str]:
    ph = db.scalar(select(IdentityPhoto).where(IdentityPhoto.id == photo_id, IdentityPhoto.org_id == p.org_id))
    if ph is None:
        raise not_found("photo")
    exam_id = access.exam_id_of_attempt(db, p.org_id, ph.attempt_id)
    access.require_exam(db, p, exam_id, P.IDENTITY)
    audit.record(db, org_id=p.org_id, actor_kind=p.actor_kind, actor_id=p.id, action="identity.photo_viewed",
                 target_type="attempt", target_id=ph.attempt_id, data={"photo_id": ph.id, "kind": ph.kind})
    return storage.get_storage().get(ph.storage_key), ph.content_type


# ------------------------------------------------------------------ emergency unlock (§22)
def unlock_secret(db: Session, attempt: Attempt) -> str:
    """Per-attempt secret, given to the client at registration and kept sealed on the server."""
    kek = get_settings().kek
    if attempt.unlock_secret_enc is None:
        secret = crypto.b64u(os.urandom(32))
        attempt.unlock_secret_enc = crypto.seal(kek, secret.encode(), f"unlock:{attempt.id}".encode())
        return secret
    return crypto.unseal(kek, attempt.unlock_secret_enc, f"unlock:{attempt.id}".encode()).decode()


def challenge_response(secret: str, challenge: str) -> str:
    """response = trunc(HMAC-SHA256(secret, challenge)) as 8 decimal digits."""
    mac = hmac.new(secret.encode(), challenge.upper().encode(), hashlib.sha256).digest()
    return f"{int.from_bytes(mac[:4], 'big') % 100_000_000:08d}"


def unlock_response(db: Session, p: Principal, attempt_id: UUID, challenge: str, reason: str) -> dict[str, Any]:
    exam_id = access.exam_id_of_attempt(db, p.org_id, attempt_id)
    access.require_exam(db, p, exam_id, P.CONTROL)
    attempt = db.get(Attempt, attempt_id)
    if attempt.unlock_secret_enc is None:
        raise conflict("NO_UNLOCK_SECRET", "the client never registered for this attempt")
    audit.record(db, org_id=p.org_id, actor_kind=p.actor_kind, actor_id=p.id, action="attempt.unlock_response_issued",
                 target_type="attempt", target_id=attempt.id, data={"challenge": challenge.upper(), "reason": reason})
    return {"attempt_id": attempt.id, "challenge": challenge.upper(),
            "response": challenge_response(unlock_secret(db, attempt), challenge)}


def online_unlock(db: Session, p: Principal, attempt_id: UUID, reason: str) -> dict[str, Any]:
    exam_id = access.exam_id_of_attempt(db, p.org_id, attempt_id)
    access.require_exam(db, p, exam_id, P.CONTROL)
    attempt = state.lock_attempt(db, attempt_id, org_id=p.org_id)
    if attempt.status not in state.LIVE:
        raise conflict("INVALID_STATE", f"attempt is {attempt.status}")
    cmd = commands.issue(db, attempt, "EMERGENCY_UNLOCK", {"reason": reason}, issued_by=p.id)
    audit.record(db, org_id=p.org_id, actor_kind=p.actor_kind, actor_id=p.id, action="attempt.emergency_unlock_sent",
                 target_type="attempt", target_id=attempt.id, data={"reason": reason, "command_id": cmd.id})
    return {"attempt_id": attempt.id, "command_id": cmd.id, "status": attempt.status}


def code_hash(exam_id: UUID, code: str) -> str:
    return hashlib.sha256(f"{exam_id}:{code.upper().replace('-', '')}".encode()).hexdigest()


def create_backup_codes(db: Session, p: Principal, exam_id: UUID, count: int) -> dict[str, Any]:
    exam = access.require_exam(db, p, exam_id, P.CONTROL)
    if exam.status not in ("READY", "RUNNING"):
        raise conflict("INVALID_STATE", f"exam is {exam.status}")
    batch, now, codes = uuid4(), clock.now(), []
    for _ in range(count):
        code = base64.b32encode(os.urandom(7)).decode().rstrip("=")[:10]      # ~50 bits
        codes.append(f"{code[:5]}-{code[5:]}")
        db.add(BackupCode(exam_id=exam.id, batch_id=batch, code_hash=code_hash(exam.id, code),
                          created_by=p.id, created_at=now))
    audit.record(db, org_id=exam.org_id, actor_kind=p.actor_kind, actor_id=p.id, action="exam.backup_codes_created",
                 target_type="exam", target_id=exam.id, data={"batch_id": batch, "count": count})
    return {"exam_id": exam.id, "batch_id": batch, "codes": codes,
            "note": "shown once; clients launched before now do not know these codes"}


def active_code_hashes(db: Session, exam_id: UUID) -> list[str]:
    return list(db.scalars(select(BackupCode.code_hash).where(BackupCode.exam_id == exam_id,
                                                              BackupCode.used_at.is_(None))))


def on_unlock_event(db: Session, attempt: Attempt, ev: Event) -> None:
    """EMERGENCY_UNLOCK_USED from the client: mark a backup code used and stop the attempt clock
    from being considered monitored (attempt → INTERRUPTED until the invigilator decides, §22)."""
    h = (ev.metadata_ or {}).get("code_hash")
    if h:
        code = db.scalar(select(BackupCode).where(BackupCode.code_hash == h, BackupCode.used_at.is_(None)))
        if code is not None:
            code.used_at, code.used_by_attempt = ev.started_at, attempt.id
    locked = state.lock_attempt(db, attempt.id)
    if locked.status == state.ACTIVE:
        state.apply(db, locked, "INTERRUPT", actor_kind="system", actor_id=None,
                    data={"cause": "EMERGENCY_UNLOCK", "method": (ev.metadata_ or {}).get("method")})


# ------------------------------------------------------------------ incidents (§27.8)
def _incident_out(inc: Incident, cand: Candidate | None = None) -> dict[str, Any]:
    return {"id": inc.id, "attempt_id": inc.attempt_id, "type": inc.type, "severity": inc.severity,
            "status": inc.status, "started_at": inc.started_at, "ended_at": inc.ended_at,
            "event_count": inc.event_count, "data": inc.data, "reviewed_by": inc.reviewed_by,
            "reviewed_at": inc.reviewed_at, "review_note": inc.review_note,
            **({"candidate_name": cand.full_name} if cand else {})}


_SEV_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INFO": 3}


def list_incidents(db: Session, p: Principal, exam_id: UUID, status: str | None, severity: str | None,
                   attempt_id: UUID | None) -> list[dict[str, Any]]:
    exam = access.require_exam(db, p, exam_id, P.MONITOR)
    q = (select(Incident, Candidate).join(Attempt, Attempt.id == Incident.attempt_id)
         .join(Enrollment, Enrollment.id == Attempt.enrollment_id)
         .join(Candidate, Candidate.id == Enrollment.candidate_id).where(Enrollment.exam_id == exam.id))
    if status:
        q = q.where(Incident.status == status)
    if severity:
        q = q.where(Incident.severity == severity)
    if attempt_id:
        q = q.where(Incident.attempt_id == attempt_id)
    rows = [_incident_out(i, c) for i, c in db.execute(q).all()]
    rows.sort(key=lambda r: (r["status"] != "OPEN", _SEV_ORDER.get(r["severity"], 9), r["started_at"]))
    return rows


def _incident(db: Session, p: Principal, incident_id: UUID, permission: str) -> Incident:
    inc = db.scalar(select(Incident).where(Incident.id == incident_id, Incident.org_id == p.org_id))
    if inc is None:
        raise not_found("incident")
    access.require_exam(db, p, access.exam_id_of_attempt(db, p.org_id, inc.attempt_id), permission)
    return inc


def incident_detail(db: Session, p: Principal, incident_id: UUID) -> dict[str, Any]:
    inc = _incident(db, p, incident_id, P.MONITOR)
    events = db.scalars(select(Event).where(Event.incident_id == inc.id).order_by(Event.seq))
    return {**_incident_out(inc), "events": [
        {"event_id": e.id, "seq": e.seq, "type": e.type, "phase": e.phase, "started_at": e.started_at,
         "ended_at": e.ended_at, "confidence": e.confidence, "metadata": e.metadata_, "evidence_ref": e.evidence_ref}
        for e in events]}


def review_incident(db: Session, p: Principal, incident_id: UUID, status: str, note: str | None) -> dict[str, Any]:
    inc = _incident(db, p, incident_id, P.CONTROL)
    inc.status, inc.review_note, inc.reviewed_by, inc.reviewed_at = status, note, p.id, clock.now()
    audit.record(db, org_id=p.org_id, actor_kind=p.actor_kind, actor_id=p.id, action="incident.reviewed",
                 target_type="incident", target_id=inc.id, data={"status": status, "note": note})
    return _incident_out(inc)


def exam_of(db: Session, attempt: Attempt) -> Exam:
    return db.get(Exam, db.get(Enrollment, attempt.enrollment_id).exam_id)
