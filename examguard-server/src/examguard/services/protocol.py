"""ExamGuard client protocol, server side (PRD §12, §16.2, §17, §18).

Wraps the Phase 1b client flow (services/client_flow.py) with launch tokens, a Signed Exam Config,
EG-Sig request authentication, signed state and commands, event ingestion and attestation tokens.
All functions run in the ``system`` context after the device session has been authenticated, and
every query is scoped to the authenticated session's attempt.
"""
import hashlib
import json
import os
import re
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit, clock, crypto, event_catalog, keys, state
from ..config import get_settings
from ..errors import AppError, conflict, invalid, not_found
from ..models import (Attempt, Candidate, Command, DeviceSession, Enrollment, Event, Exam, Incident,
                      LaunchToken)
from . import client_flow, proctoring


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat().replace("+00:00", "Z") if dt else None


def _unauthorized(msg: str, code: str = "UNAUTHORIZED") -> AppError:
    return AppError(401, code, msg)


def _ctx(db: Session, attempt: Attempt) -> tuple[Enrollment, Exam]:
    enr = db.get(Enrollment, attempt.enrollment_id)
    return enr, db.get(Exam, enr.exam_id)


# ------------------------------------------------------------------ launch tokens (§12.1)
def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_launch_token(db: Session, cand: Candidate, enrollment_id: UUID, *,
                       enforce_window: bool = False) -> dict[str, Any]:
    """Single-use launch link. The Candidate Portal enforces the check-in window (PRD §28.4); the
    Integration API and the dev CLI issue links whenever the attempt can still run."""
    enr = db.scalar(select(Enrollment).where(Enrollment.id == enrollment_id, Enrollment.candidate_id == cand.id))
    if enr is None or enr.status != "CONFIRMED":
        raise not_found("enrollment")
    attempt = db.scalar(select(Attempt).where(Attempt.enrollment_id == enr.id))
    exam = db.get(Exam, enr.exam_id)
    now = clock.now()
    from .registration import launch_window
    ok, reason = launch_window(exam, attempt, now)
    if not ok and not enforce_window and reason in ("NOT_YET_OPEN", "LATE_START_CLOSED"):
        ok = True
    if not ok:
        if reason == "ENDED":
            raise conflict("ATTEMPT_ENDED", "this exam can no longer be launched")
        if reason == "EXAM_NOT_OPEN":
            raise conflict("EXAM_NOT_OPEN", f"exam is {exam.status}")
        if reason == "NOT_YET_OPEN":
            raise conflict("LAUNCH_NOT_YET_OPEN", "check-in has not opened yet", {"checkin_open": exam.checkin_open})
        raise conflict("LATE_START_CLOSED", "the latest start time has passed")
    token = crypto.b64u(os.urandom(32))
    expires = now + timedelta(minutes=get_settings().launch_token_minutes)
    db.add(LaunchToken(attempt_id=attempt.id, token_hash=_hash(token), created_at=now, expires_at=expires))
    db.flush()
    return {"launch_token": token, "launch_url": f"examguard://launch?t={token}", "expires_at": expires,
            "attempt_id": attempt.id}


def _redeem(db: Session, token: str, *, consume: bool) -> LaunchToken:
    row = db.scalar(select(LaunchToken).where(LaunchToken.token_hash == _hash(token)).with_for_update())
    now = clock.now()
    if row is None:
        raise _unauthorized("unknown launch token", "INVALID_LAUNCH_TOKEN")
    if row.used_at is not None:
        raise conflict("LAUNCH_TOKEN_USED", "this launch token was already used; request a new launch link")
    if row.expires_at <= now:
        raise _unauthorized("launch token expired; request a new launch link", "LAUNCH_TOKEN_EXPIRED")
    if consume:
        row.used_at = now
    return row


# ------------------------------------------------------------------ signed exam config (§12.3)
def config_hash(exam: Exam) -> str:
    stable = {"exam_id": str(exam.id), "exam_url": exam.exam_url, "allowed_origins": sorted(exam.allowed_origins or []),
              "policy": exam.policy, "integration_level": exam.integration_level,
              "min_client_version": get_settings().min_client_version}
    return "sha256:" + crypto.sha256_hex(crypto.dumps(stable).encode())


def server_endpoints() -> dict[str, str]:
    base = get_settings().public_base_url.rstrip("/")
    ws = "wss" + base[5:] if base.startswith("https") else "ws" + base[4:]
    return {"api": f"{base}/client/v1", "ws": f"{ws}/client/v1/ws",
            "key_set": f"{base}/.well-known/examguard-keys.json"}


def exam_config(db: Session, token: str) -> dict[str, str]:
    lt = _redeem(db, token, consume=False)
    attempt = db.get(Attempt, lt.attempt_id)
    enr, exam = _ctx(db, attempt)
    now = clock.now()
    s = get_settings()
    body = {
        "v": 1, "exam_id": str(exam.id), "exam_code": exam.code, "exam_name": exam.name,
        "attempt_id": str(attempt.id), "candidate_id": str(enr.candidate_id),
        "exam_url": exam.exam_url, "allowed_origins": exam.allowed_origins or [], "policy": exam.policy,
        "integration_level": exam.integration_level, "identity_check": exam.identity_check,
        "checkin_open": iso(exam.checkin_open), "window_start": iso(exam.window_start),
        "latest_start": iso(exam.latest_start), "window_end": iso(exam.window_end),
        "min_client_version": s.min_client_version, "server_endpoints": server_endpoints(),
        "issued_at": iso(now), "expires_at": iso(now + timedelta(minutes=s.config_ttl_minutes)),
        "config_hash": config_hash(exam),
        # §22 printed backup codes: the client only knows sha256(exam_id ":" CODE), never the codes
        "emergency_code_hashes": proctoring.active_code_hashes(db, exam.id),
    }
    kid, key = keys.signer(db, "config")
    return crypto.envelope(kid, key, body)


# ------------------------------------------------------------------ device session registration (§18)
def _version_tuple(v: str) -> tuple[int, ...]:
    if not re.fullmatch(r"\d+(\.\d+){0,3}", v or ""):
        raise invalid("INVALID_CLIENT_VERSION", "client_version must look like 1.2.3")
    return tuple(int(x) for x in v.split("."))


def register(db: Session, token: str, public_key: str, client_version: str, os_info: dict[str, Any],
             preflight: dict[str, Any]) -> dict[str, Any]:
    if _version_tuple(client_version) < _version_tuple(get_settings().min_client_version):
        raise AppError(426, "CLIENT_TOO_OLD", f"minimum client version is {get_settings().min_client_version}")
    try:
        crypto.load_public(public_key)
    except ValueError:
        raise invalid("INVALID_PUBLIC_KEY", "public_key must be a base64url Ed25519 public key (32 bytes)") from None
    lt = _redeem(db, token, consume=True)
    r = client_flow.register_device(db, lt.attempt_id, public_key=public_key, client_version=client_version,
                                    os_info={**os_info, "preflight": preflight})
    lt.used_by_device_session = r["device_session_id"]
    attempt = db.get(Attempt, lt.attempt_id)
    ds = db.get(DeviceSession, r["device_session_id"]) if r["device_session_id"] else None
    return {"device_session_id": r["device_session_id"], "device_status": r["device_status"],
            "attempt_unlock_secret": proctoring.unlock_secret(db, attempt),   # §22 challenge–response
            "state": signed_state(db, attempt, ds)}


# ------------------------------------------------------------------ EG-Sig authentication (§18)
_SIG_RE = re.compile(r"^EG-Sig\s+(.*)$", re.IGNORECASE)


def signing_input(method: str, path: str, ts: str, body: bytes) -> bytes:
    return f"{method.upper()}\n{path}\n{ts}\n{crypto.sha256_hex(body)}".encode()


def parse_authorization(header: str | None) -> dict[str, str]:
    m = _SIG_RE.match(header or "")
    if not m:
        raise _unauthorized("missing EG-Sig authorization")
    parts = dict(p.strip().split("=", 1) for p in m.group(1).split(",") if "=" in p)
    if not {"sid", "ts", "sig"} <= parts.keys():
        raise _unauthorized("EG-Sig needs sid, ts and sig")
    return parts


def authenticate(db: Session, *, sid: str, ts: str, sig: str, method: str, path: str, body: bytes,
                 attempt_id: UUID | None = None, allow_revoked: bool = False) -> DeviceSession:
    try:
        ts_ms, ds_id = int(ts), UUID(sid)
    except ValueError:
        raise _unauthorized("malformed EG-Sig") from None
    skew = abs(clock.now().timestamp() * 1000 - ts_ms) / 1000
    if skew > get_settings().request_clock_skew_seconds:
        raise _unauthorized("request timestamp outside the allowed window", "CLOCK_SKEW")
    ds = db.get(DeviceSession, ds_id)
    if ds is None or not ds.public_key or not crypto.verify(ds.public_key, signing_input(method, path, ts, body), sig):
        raise _unauthorized("invalid request signature", "INVALID_SIGNATURE")
    if ds.status == "REVOKED" and not allow_revoked:
        raise _unauthorized("device session revoked", "DEVICE_SESSION_REVOKED")
    if attempt_id is not None and ds.attempt_id != attempt_id:
        raise AppError(403, "FORBIDDEN", "device session does not belong to this attempt")
    return ds


# ------------------------------------------------------------------ signed state (§17.7)
def _pending_warning(db: Session, ds: DeviceSession | None) -> dict[str, Any] | None:
    if ds is None:
        return None
    cmd = db.scalars(select(Command).where(
        Command.device_session_id == ds.id, Command.type == "WARNING",
        Command.delivery_status.in_(("PENDING", "SENT"))).order_by(Command.issued_at.desc())).first()
    return {"command_id": str(cmd.id), "message": cmd.payload.get("message")} if cmd else None


def state_body(db: Session, attempt: Attempt, ds: DeviceSession | None) -> dict[str, Any]:
    enr, exam = _ctx(db, attempt)
    return {
        "v": 1, "attempt_id": str(attempt.id), "exam_id": str(exam.id), "candidate_id": str(enr.candidate_id),
        "device_session_id": str(ds.id) if ds else None, "device_status": ds.status if ds else None,
        "status": attempt.status, "state_version": attempt.state_version, "deadline": iso(attempt.deadline),
        "server_time": iso(clock.now()), "resume_allowed": attempt.status == state.ACTIVE,
        "pause_timer_mode": attempt.pause_timer_mode, "identity_status": attempt.identity_status,
        "window_start": iso(exam.window_start), "pending_warning": _pending_warning(db, ds),
    }


def signed_state(db: Session, attempt: Attempt, ds: DeviceSession | None) -> dict[str, str]:
    kid, key = keys.signer(db, "state")
    return crypto.envelope(kid, key, state_body(db, attempt, ds))


# ------------------------------------------------------------------ signed commands (§17.2–17.5)
def command_envelope(db: Session, cmd: Command) -> dict[str, str]:
    """Sign once; retransmissions are byte-identical so the client can dedupe by command_id."""
    if cmd.envelope is None:
        attempt = db.get(Attempt, cmd.attempt_id)
        enr, exam = _ctx(db, attempt)
        body = {"v": 1, "command_id": str(cmd.id), "type": cmd.type, "exam_id": str(exam.id),
                "attempt_id": str(attempt.id), "candidate_id": str(enr.candidate_id),
                "device_session_id": str(cmd.device_session_id), "state_version": cmd.state_version,
                "issued_at": iso(cmd.issued_at), "expires_at": iso(cmd.expires_at),
                "nonce": crypto.b64u(os.urandom(16)), "payload": cmd.payload}
        kid, key = keys.signer(db, "command")
        cmd.envelope = crypto.dumps(crypto.envelope(kid, key, body))
    return json.loads(cmd.envelope)


def deliverable_commands(db: Session, ds: DeviceSession) -> list[dict[str, str]]:
    now = clock.now()
    rows = db.scalars(select(Command).where(
        Command.device_session_id == ds.id, Command.delivery_status.in_(("PENDING", "SENT")),
        Command.expires_at > now).order_by(Command.issued_at, Command.state_version)).all()
    out = []
    for cmd in rows:
        out.append(command_envelope(db, cmd))
        if cmd.delivery_status == "PENDING":
            cmd.delivery_status, cmd.delivered_at = "SENT", now
    return out


def ack(db: Session, ds: DeviceSession, command_id: UUID, result: str, reason: str | None) -> dict[str, Any]:
    cmd = db.scalar(select(Command).where(Command.id == command_id, Command.device_session_id == ds.id))
    if cmd is None:
        raise not_found("command")
    if cmd.delivery_status in ("PENDING", "SENT"):
        cmd.delivery_status, cmd.ack_reason = result, reason
        cmd.delivered_at = cmd.delivered_at or clock.now()
    return {"command_id": cmd.id, "delivery_status": cmd.delivery_status}


# ------------------------------------------------------------------ heartbeat (§17.6)
def heartbeat(db: Session, ds: DeviceSession, seq: int, last_state_version: int | None,
              health: dict[str, Any], cause: str | None = None) -> dict[str, Any]:
    r = client_flow.heartbeat(db, ds.id, seq, cause=cause)
    if health:
        ds.os_info = {**(ds.os_info or {}), "health": health}
    return {"server_time": iso(clock.now()), "status": r["status"], "state_version": r["state_version"],
            "device_status": r["device_status"], "stale": r["stale"],
            "sync_required": last_state_version is not None and r["state_version"] > last_state_version}


# ------------------------------------------------------------------ events & incidents (§15, §17.8)
def ingest_events(db: Session, ds: DeviceSession, events: list[dict[str, Any]]) -> dict[str, Any]:
    attempt = db.get(Attempt, ds.attempt_id)
    _, exam = _ctx(db, attempt)
    seqs = [e["seq"] for e in events]
    ids = [e["event_id"] for e in events]
    known_seq = set(db.scalars(select(Event.seq).where(Event.device_session_id == ds.id, Event.seq.in_(seqs))))
    known_id = set(db.scalars(select(Event.id).where(Event.id.in_(ids))))
    now = clock.now()
    accepted, duplicates, incidents = 0, 0, 0
    for e in sorted(events, key=lambda x: x["seq"]):
        if e["seq"] in known_seq or e["event_id"] in known_id:
            duplicates += 1
            continue
        severity, makes_incident = event_catalog.classify(e["type"], exam.policy or {})
        ev = Event(id=e["event_id"], attempt_id=attempt.id, device_session_id=ds.id, seq=e["seq"],
                   type=e["type"], phase=e["phase"], started_at=e["started_at"], ended_at=e.get("ended_at"),
                   confidence=e.get("confidence"), metadata_=e.get("metadata") or {},
                   evidence_ref=e.get("evidence_ref"), severity=severity, received_at=now)
        if makes_incident:
            inc, created = _incident_for(db, attempt, ev)
            ev.incident_id = inc.id
            incidents += created
        db.add(ev)
        if ev.type == "EMERGENCY_UNLOCK_USED":
            db.flush()
            proctoring.on_unlock_event(db, attempt, ev)
        known_seq.add(e["seq"])
        known_id.add(e["event_id"])
        accepted += 1
    db.flush()
    return {"accepted": accepted, "duplicates": duplicates, "incidents_created": incidents}


def _incident_for(db: Session, attempt: Attempt, ev: Event) -> tuple[Incident, int]:
    if ev.phase == "CLOSE":
        open_inc = db.scalars(select(Incident).where(
            Incident.attempt_id == attempt.id, Incident.type == ev.type, Incident.ended_at.is_(None))
            .order_by(Incident.started_at.desc())).first()
        if open_inc is not None:
            open_inc.ended_at = ev.ended_at or ev.started_at
            open_inc.event_count += 1
            return open_inc, 0
    ended = ev.started_at if ev.phase == "INSTANT" else (ev.ended_at if ev.phase == "CLOSE" else None)
    inc = Incident(attempt_id=attempt.id, type=ev.type, severity=ev.severity, started_at=ev.started_at,
                   ended_at=ended, data={"confidence": ev.confidence, "metadata": ev.metadata_,
                                         "evidence_ref": ev.evidence_ref})
    db.add(inc)
    db.flush()
    return inc, 1


# ------------------------------------------------------------------ attestation token (§16.2)
def attestation(db: Session, ds: DeviceSession) -> dict[str, Any]:
    attempt = db.get(Attempt, ds.attempt_id)
    enr, exam = _ctx(db, attempt)
    if ds.status != "ACTIVE" or attempt.status not in state.LIVE:
        raise conflict("ATTESTATION_UNAVAILABLE", f"no attestation while attempt is {attempt.status}")
    now = clock.now()
    ttl = get_settings().attestation_ttl_seconds
    aud = "{0.scheme}://{0.netloc}".format(urlsplit(exam.exam_url)) if exam.exam_url else None
    claims = {"iss": get_settings().public_base_url, "aud": aud, "exam_id": str(exam.id),
              "attempt_id": str(attempt.id), "candidate_ref": getattr(enr, "external_ref", None),
              "device_session_id": str(ds.id), "attempt_status": attempt.status,
              "state_version": attempt.state_version, "config_hash": config_hash(exam),
              "iat": int(now.timestamp()), "exp": int(now.timestamp()) + ttl}
    kid, key = keys.signer(db, "token")
    return {"token": crypto.jwt_encode(kid, key, claims), "expires_at": iso(now + timedelta(seconds=ttl))}


def audit_client(db: Session, ds: DeviceSession, action: str, data: dict[str, Any] | None = None) -> None:
    attempt = db.get(Attempt, ds.attempt_id)
    enr, _ = _ctx(db, attempt)
    audit.record(db, org_id=attempt.org_id, actor_kind="candidate", actor_id=enr.candidate_id, action=action,
                 target_type="attempt", target_id=attempt.id, data={"device_session_id": ds.id, **(data or {})})
