"""Webhooks Server → LMS (PRD §16.6).

Every attempt transition that an LMS cares about is queued in ``webhook_deliveries`` inside the
same transaction as the transition (outbox pattern), one row per ACTIVE integration of the
organization that has a webhook_url. The scheduler delivers due rows.

Signature: signed with the server's ``token`` key, so the LMS verifies it with the same key set it
already uses for attestation tokens — no shared secret to store or leak.

    X-ExamGuard-Signature: kid=<kid>, ts=<unix_ms>, sig=<base64url Ed25519(ts + "." + body)>
    X-ExamGuard-Event-Id:  <event_id>   (idempotency key; the same id is retried)
"""
import logging
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import clock, crypto, keys
from .db import transaction
from .models import Attempt, Enrollment, Integration, StateTransition, WebhookDelivery

log = logging.getLogger("examguard.webhooks")

# trigger -> webhook event type
EVENTS: dict[str, str] = {
    "START": "attempt.started", "RELAUNCH": "attempt.started",
    "PAUSE": "attempt.paused", "RESUME": "attempt.resumed",
    "UPDATE_DEADLINE": "attempt.deadline_updated",
    "SUBMIT": "attempt.submitted", "FORCE_SUBMIT": "attempt.submitted",
    "EXPIRE": "attempt.expired",
    "FORCE_TERMINATE": "attempt.terminated", "REJECT_REENTRY": "attempt.terminated",
    "REOPEN": "attempt.reopened", "REINSTATE": "attempt.reinstated",
}
BACKOFF = [timedelta(seconds=s) for s in (30, 60, 120, 300, 600, 1800, 3600, 3600, 3600)]
MAX_ATTEMPTS = len(BACKOFF) + 1
TIMEOUT_SECONDS = 5


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat().replace("+00:00", "Z") if dt else None


def enqueue(db: Session, attempt: Attempt, st: StateTransition) -> int:
    event_type = EVENTS.get(st.trigger)
    if event_type is None:
        return 0
    targets = list(db.scalars(select(Integration).where(
        Integration.org_id == attempt.org_id, Integration.status == "ACTIVE",
        Integration.webhook_url.is_not(None))))
    if not targets:
        return 0
    enr = db.get(Enrollment, attempt.enrollment_id)
    now = clock.now()
    for integ in targets:
        event_id = uuid4()
        payload = {"event_id": str(event_id), "type": event_type, "occurred_at": _iso(st.occurred_at),
                   "exam_id": str(enr.exam_id), "attempt_id": str(attempt.id),
                   "candidate_ref": enr.external_ref, "status": st.to_status,
                   "state_version": st.state_version, "deadline": _iso(attempt.deadline),
                   "reason_category": st.reason_category}
        db.add(WebhookDelivery(id=event_id, org_id=attempt.org_id, integration_id=integ.id,
                               attempt_id=attempt.id, event_type=event_type, payload=payload,
                               next_attempt_at=now, created_at=now))
    return len(targets)


def sign(db: Session, body: bytes, ts: int) -> str:
    kid, key = keys.signer(db, "token")
    return f"kid={kid}, ts={ts}, sig={crypto.sign(key, str(ts).encode() + b'.' + body)}"


def http_send(url: str, body: bytes, headers: dict[str, str]) -> int:
    req = urllib.request.Request(url, data=body, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:  # noqa: S310 — URL set by Org Admin
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code


Sender = Callable[[str, bytes, dict[str, str]], int]


def deliver_due(now: datetime | None = None, send: Sender = http_send, batch: int = 100) -> dict[str, int]:
    """Claim due deliveries (lease), send outside the transaction, record the outcome."""
    now = now or clock.now()
    claimed: list[tuple[UUID, str, bytes, dict[str, str]]] = []
    with transaction("system") as db:
        rows = db.execute(
            select(WebhookDelivery, Integration).join(Integration, Integration.id == WebhookDelivery.integration_id)
            .where(WebhookDelivery.status == "PENDING", WebhookDelivery.next_attempt_at <= now)
            .order_by(WebhookDelivery.created_at).limit(batch)
            .with_for_update(of=WebhookDelivery, skip_locked=True)).all()
        for d, integ in rows:
            if integ.status != "ACTIVE" or not integ.webhook_url:
                d.status, d.last_error = "FAILED", "integration revoked or webhook removed"
                continue
            d.next_attempt_at = now + timedelta(seconds=60)          # lease while sending
            body = crypto.dumps(d.payload).encode()
            ts = int(now.timestamp() * 1000)
            headers = {"Content-Type": "application/json", "User-Agent": "ExamGuard-Webhook/1",
                       "X-ExamGuard-Event-Id": str(d.id), "X-ExamGuard-Event": d.event_type,
                       "X-ExamGuard-Signature": sign(db, body, ts)}
            claimed.append((d.id, integ.webhook_url, body, headers))
    counts = {"delivered": 0, "retry": 0, "failed": 0}
    for did, url, body, headers in claimed:
        code, error = None, None
        try:
            code = send(url, body, headers)
        except Exception as e:  # network errors are retried
            error = f"{type(e).__name__}: {e}"[:500]
        with transaction("system") as db:
            d = db.get(WebhookDelivery, did)
            d.attempts += 1
            d.last_status_code, d.last_error = code, error
            if code is not None and 200 <= code < 300:
                d.status, d.delivered_at = "DELIVERED", clock.now()
                counts["delivered"] += 1
            elif d.attempts >= MAX_ATTEMPTS:
                d.status = "FAILED"
                counts["failed"] += 1
            else:
                d.next_attempt_at = clock.now() + BACKOFF[d.attempts - 1]
                counts["retry"] += 1
    return counts


def verify(key_set_keys: dict[str, dict[str, Any]], header: str, body: bytes) -> bool:
    """Reference verification for LMS developers (and tests)."""
    parts = dict(p.strip().split("=", 1) for p in header.split(","))
    k = key_set_keys.get(parts.get("kid", ""))
    return bool(k and k["use"] == "token" and k["status"] != "revoked"
                and crypto.verify(k["x"], parts["ts"].encode() + b"." + body, parts["sig"]))
