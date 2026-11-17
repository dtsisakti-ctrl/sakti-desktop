"""Append-only, hash-chained audit log (writes go through eg_audit_append in SQL)."""
import json
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


def record(
    db: Session,
    *,
    org_id: UUID | None,
    actor_kind: str,
    actor_id: UUID | None,
    action: str,
    target_type: str | None = None,
    target_id: str | UUID | None = None,
    data: dict[str, Any] | None = None,
) -> int:
    db.flush()
    return db.execute(
        text(
            "SELECT eg_audit_append(:org, :ak, :aid, :act, :tt, :tid, CAST(:data AS jsonb))"
        ),
        {
            "org": org_id,
            "ak": actor_kind,
            "aid": actor_id,
            "act": action,
            "tt": target_type,
            "tid": None if target_id is None else str(target_id),
            "data": json.dumps(data or {}, default=str),
        },
    ).scalar_one()


def chain_key(org_id: UUID | None) -> str:
    return "platform" if org_id is None else f"org:{org_id}"


def verify(db: Session, chain: str) -> dict[str, Any]:
    row = db.execute(
        text("SELECT ok, checked, first_bad_seq, reason FROM eg_audit_verify(:c)"), {"c": chain}
    ).one()
    return {"chain": chain, "ok": row.ok, "checked": row.checked,
            "first_bad_seq": row.first_bad_seq, "reason": row.reason}
