"""Device session bookkeeping shared by staff actions, the client flow and the scheduler (PRD §18)."""
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import clock
from .models import DeviceSession

OFFLINE_AFTER = timedelta(seconds=30)   # default when the exam's threshold is not known (PRD §17.6)


def active(db: Session, attempt_id: UUID) -> DeviceSession | None:
    return db.scalar(select(DeviceSession).where(DeviceSession.attempt_id == attempt_id,
                                                 DeviceSession.status == "ACTIVE"))


def pending(db: Session, attempt_id: UUID) -> DeviceSession | None:
    return db.scalar(select(DeviceSession).where(DeviceSession.attempt_id == attempt_id,
                                                 DeviceSession.status == "PENDING_APPROVAL"))


def revoke(db: Session, ds: DeviceSession, reason: str) -> None:
    ds.status, ds.revoked_at, ds.revoke_reason = "REVOKED", clock.now(), reason
    db.flush()


def revoke_all(db: Session, attempt_id: UUID, reason: str) -> int:
    rows = list(db.scalars(select(DeviceSession).where(DeviceSession.attempt_id == attempt_id,
                                                       DeviceSession.status != "REVOKED")))
    for ds in rows:
        revoke(db, ds, reason)
    return len(rows)


def promote_pending(db: Session, attempt_id: UUID) -> DeviceSession | None:
    """Approved device change: revoke the old ACTIVE session, then activate the pending one."""
    new = pending(db, attempt_id)
    if new is None:
        return None
    old = active(db, attempt_id)
    if old is not None:
        revoke(db, old, "REPLACED_BY_APPROVED_DEVICE")
    new.status, new.activated_at = "ACTIVE", clock.now()
    db.flush()
    return new


def last_seen(ds: DeviceSession | None) -> datetime | None:
    """Last proof of life: a heartbeat or any signed request (or activation)."""
    if ds is None:
        return None
    return ds.last_heartbeat_at or ds.activated_at or ds.created_at


def closed_since_seen(ds: DeviceSession | None) -> bool:
    """The client's connection closed and no proof of life came since (crash, app closed, Ctrl+C).

    Any later heartbeat or signed request clears connection_closed_at (client_flow._alive).
    """
    return bool(ds and ds.connection_closed_at)


def offline_threshold(db, exam) -> int:
    """Seconds without heartbeat before OFFLINE; equal to the exam's interruption threshold."""
    from . import settings_service
    from .models import Organization
    return settings_service.value(db, db.get(Organization, exam.org_id), "interruption_threshold_seconds", exam)


def connection_status(ds: DeviceSession | None, now: datetime, threshold_seconds: int | None = None) -> str:
    """OFFLINE as soon as the connection closed, or after `threshold_seconds` without heartbeat.

    The threshold is the exam's interruption_threshold_seconds, so OFFLINE and INTERRUPTED appear
    together (PRD v0.3.5 Q25).
    """
    if ds is None or closed_since_seen(ds):
        return "OFFLINE"
    seen = last_seen(ds)
    limit = timedelta(seconds=threshold_seconds) if threshold_seconds else OFFLINE_AFTER
    return "ONLINE" if seen is not None and now - seen <= limit else "OFFLINE"
