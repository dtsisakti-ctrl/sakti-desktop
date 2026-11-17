"""Command outbox (PRD §17.4).

Phase 1b records every client-facing command in the ``commands`` table with the attempt's
``state_version`` at issue time. Phase 1c signs them (§17.2) and pushes them over WSS;
until then they stay PENDING and are visible in the Candidate Detail view.
"""
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import clock
from .models import Attempt, Command, DeviceSession

COMMAND_TTL = timedelta(minutes=5)


def target_session(db: Session, attempt_id: UUID, *, pending: bool = False) -> DeviceSession | None:
    status = "PENDING_APPROVAL" if pending else "ACTIVE"
    return db.scalar(select(DeviceSession).where(DeviceSession.attempt_id == attempt_id,
                                                 DeviceSession.status == status))


def issue(db: Session, attempt: Attempt, type_: str, payload: dict[str, Any], *,
          issued_by: UUID | None, session: DeviceSession | None = None,
          to_pending: bool = False) -> Command:
    now = clock.now()
    session = session or target_session(db, attempt.id, pending=to_pending)
    cmd = Command(attempt_id=attempt.id, device_session_id=session.id if session else None,
                  type=type_, payload=_jsonable(payload), state_version=attempt.state_version,
                  issued_by=issued_by, issued_at=now, expires_at=now + COMMAND_TTL,
                  delivery_status="PENDING")
    db.add(cmd)
    db.flush()
    return cmd


def _jsonable(payload: dict[str, Any]) -> dict[str, Any]:
    return {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in payload.items()}
