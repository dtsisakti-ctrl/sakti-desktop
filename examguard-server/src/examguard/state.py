"""Attempt state machine (PRD §10).

``TRANSITIONS`` is the single source of truth: every status change goes through ``apply()``,
which validates the move, bumps ``state_version`` by exactly one, writes a StateTransition row
and an audit-log entry, all in the caller's transaction. The caller must hold a row lock on the
attempt (see ``lock_attempt``), so two invigilators acting at once are serialized.

A database trigger additionally rejects any status/deadline change that does not bump
``state_version`` by one (migrations/sql/0002_state_engine.sql).
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import audit, clock
from .errors import AppError, conflict, invalid, not_found
from .models import Attempt, StateTransition

# ------------------------------------------------------------------ statuses
NOT_STARTED, ACTIVE, PAUSED, INTERRUPTED = "NOT_STARTED", "ACTIVE", "PAUSED", "INTERRUPTED"
WAITING, REOPENED, REINSTATED = "WAITING_FOR_INVIGILATOR", "REOPENED", "REINSTATED"
SUBMITTED, EXPIRED, TERMINATED, NO_SHOW, FINALIZED = "SUBMITTED", "EXPIRED", "TERMINATED", "NO_SHOW", "FINALIZED"

ALL_STATUSES = (NOT_STARTED, ACTIVE, PAUSED, INTERRUPTED, WAITING, REOPENED, REINSTATED,
                SUBMITTED, EXPIRED, TERMINATED, NO_SHOW, FINALIZED)
ENDED = frozenset({SUBMITTED, EXPIRED, TERMINATED, NO_SHOW})     # final, not yet locked
FINAL = ENDED | {FINALIZED}
LIVE = frozenset({ACTIVE, PAUSED, INTERRUPTED, WAITING})          # a client session exists
HAS_DEADLINE = LIVE | {REOPENED, REINSTATED}                      # deadline is running/defined

REASON_CATEGORIES = ("TECHNICAL", "ADMINISTRATIVE", "DISCIPLINARY")


@dataclass(frozen=True)
class Rule:
    sources: frozenset[str]
    target: str | None          # None = status unchanged (deadline update)
    actor: str                  # documentation only: who may trigger it (PRD §10.3 "Aktor")


# PRD §10.3. Keys are triggers; anything not listed here is INVALID_TRANSITION.
TRANSITIONS: dict[str, Rule] = {
    "START":            Rule(frozenset({NOT_STARTED}), ACTIVE, "candidate"),
    "RELAUNCH":         Rule(frozenset({REOPENED, REINSTATED}), ACTIVE, "candidate"),
    "NO_SHOW":          Rule(frozenset({NOT_STARTED}), NO_SHOW, "system"),
    "PAUSE":            Rule(frozenset({ACTIVE}), PAUSED, "invigilator"),
    "RESUME":           Rule(frozenset({PAUSED}), ACTIVE, "invigilator"),
    "INTERRUPT":        Rule(frozenset({ACTIVE}), INTERRUPTED, "system"),
    "AUTO_RESUME":      Rule(frozenset({INTERRUPTED}), ACTIVE, "system"),
    # INTERRUPTED -> WAITING is PRD §10.3. ACTIVE -> WAITING covers PRD §18: a second device
    # registering while the first is still considered alive always needs approval.
    "REQUIRE_APPROVAL": Rule(frozenset({INTERRUPTED, ACTIVE}), WAITING, "system"),
    "ALLOW_REENTRY":    Rule(frozenset({WAITING}), ACTIVE, "invigilator"),
    "REJECT_REENTRY":   Rule(frozenset({WAITING}), TERMINATED, "invigilator"),
    "SUBMIT":           Rule(frozenset({ACTIVE}), SUBMITTED, "candidate"),
    "FORCE_SUBMIT":     Rule(LIVE, SUBMITTED, "invigilator"),
    "EXPIRE":           Rule(HAS_DEADLINE, EXPIRED, "system"),
    "FORCE_TERMINATE":  Rule(LIVE, TERMINATED, "invigilator"),
    "REOPEN":           Rule(frozenset({SUBMITTED, EXPIRED}), REOPENED, "exam_admin"),
    "REINSTATE":        Rule(frozenset({TERMINATED}), REINSTATED, "exam_admin"),
    "FINALIZE":         Rule(ENDED, FINALIZED, "exam_admin"),
    "UPDATE_DEADLINE":  Rule(HAS_DEADLINE, None, "invigilator"),
}

_UNSET: Any = object()


def target_of(trigger: str, current: str) -> str:
    rule = TRANSITIONS[trigger]
    return current if rule.target is None else rule.target


def is_allowed(trigger: str, current: str) -> bool:
    rule = TRANSITIONS.get(trigger)
    return rule is not None and current in rule.sources


def allowed_triggers(current: str) -> list[str]:
    return [t for t, r in TRANSITIONS.items() if current in r.sources]


# ------------------------------------------------------------------ locking
def lock_attempt(db: Session, attempt_id: UUID, *, org_id: UUID | None = None) -> Attempt:
    """Load an attempt with a row lock (SELECT ... FOR UPDATE OF attempts)."""
    q = select(Attempt).where(Attempt.id == attempt_id)
    if org_id is not None:
        q = q.where(Attempt.org_id == org_id)
    # populate_existing: if the attempt was already loaded in this session, refresh it with the
    # row as it is now that we hold the lock (otherwise a stale status could be validated).
    attempt = db.scalar(q.with_for_update(of=Attempt).execution_options(populate_existing=True))
    if attempt is None:
        raise not_found("attempt")
    return attempt


def check_version(attempt: Attempt, expected: int | None) -> None:
    """Optimistic check for Admin Web: the action was decided on a state that is still current."""
    if expected is not None and expected != attempt.state_version:
        raise conflict("STATE_CONFLICT", "attempt changed since you loaded it; reload and try again",
                       {"expected_state_version": expected, "state_version": attempt.state_version,
                        "status": attempt.status})


# ------------------------------------------------------------------ apply
def apply(
    db: Session,
    attempt: Attempt,
    trigger: str,
    *,
    actor_kind: str,
    actor_id: UUID | None,
    reason: str | None = None,
    reason_category: str | None = None,
    deadline: datetime | None = _UNSET,
    data: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> StateTransition:
    rule = TRANSITIONS.get(trigger)
    if rule is None or attempt.status not in rule.sources:
        raise conflict("INVALID_TRANSITION", f"{trigger} is not allowed from {attempt.status}",
                       {"status": attempt.status, "trigger": trigger,
                        "allowed": allowed_triggers(attempt.status)})
    to_status = attempt.status if rule.target is None else rule.target
    if to_status == TERMINATED:
        if reason_category not in REASON_CATEGORIES:
            raise invalid("REASON_CATEGORY_REQUIRED",
                          f"terminating an attempt requires reason_category in {list(REASON_CATEGORIES)}")
    elif reason_category is not None:
        raise invalid("REASON_CATEGORY_NOT_APPLICABLE", "reason_category is only used when terminating")

    now = now or clock.now()
    from_status, old_deadline = attempt.status, attempt.deadline
    attempt.status = to_status
    if deadline is not _UNSET:
        attempt.deadline = deadline
    if to_status == TERMINATED:
        attempt.termination_reason_category = reason_category
    attempt.state_version += 1
    attempt.updated_at = now

    st = StateTransition(
        attempt_id=attempt.id, state_version=attempt.state_version, from_status=from_status,
        to_status=to_status, trigger=trigger, actor_kind=actor_kind, actor_id=actor_id,
        reason=reason, reason_category=reason_category, old_deadline=old_deadline,
        new_deadline=attempt.deadline, data=data or {}, occurred_at=now,
    )
    db.add(st)
    db.flush()
    audit_data: dict[str, Any] = {"from": from_status, "to": to_status, "state_version": attempt.state_version}
    if reason:
        audit_data["reason"] = reason
    if reason_category:
        audit_data["reason_category"] = reason_category
    if old_deadline != attempt.deadline:
        audit_data["old_deadline"], audit_data["new_deadline"] = old_deadline, attempt.deadline
    if data:
        audit_data.update(data)
    audit.record(db, org_id=attempt.org_id, actor_kind=actor_kind, actor_id=actor_id,
                 action=f"attempt.{trigger.lower()}", target_type="attempt", target_id=attempt.id,
                 data=audit_data)
    from . import webhooks  # outbox row in the same transaction as the transition
    webhooks.enqueue(db, attempt, st)
    return st


def require(condition: bool, code: str, message: str, status: int = 409) -> None:
    if not condition:
        raise AppError(status, code, message)
