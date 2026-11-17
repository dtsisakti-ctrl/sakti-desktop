"""Attempt state machine (PRD §10.3): the full status × trigger matrix against the real database."""
from datetime import timedelta

import pytest
from sqlalchemy import text

from examguard import state
from examguard.db import new_session, set_context, transaction
from examguard.errors import AppError

from .conftest import NOW, owner_conn

W = "WAITING_FOR_INVIGILATOR"
LIVE = ("ACTIVE", "PAUSED", "INTERRUPTED", W)

# PRD §10.3 written out independently of examguard.state, so the two are checked against each other.
EXPECTED: dict[tuple[str, str], str] = {
    ("NOT_STARTED", "START"): "ACTIVE",
    ("NOT_STARTED", "NO_SHOW"): "NO_SHOW",
    ("ACTIVE", "PAUSE"): "PAUSED",
    ("PAUSED", "RESUME"): "ACTIVE",
    ("ACTIVE", "INTERRUPT"): "INTERRUPTED",
    ("INTERRUPTED", "AUTO_RESUME"): "ACTIVE",
    ("INTERRUPTED", "REQUIRE_APPROVAL"): W,
    ("ACTIVE", "REQUIRE_APPROVAL"): W,               # device change while active (PRD §18)
    (W, "ALLOW_REENTRY"): "ACTIVE",
    (W, "REJECT_REENTRY"): "TERMINATED",
    ("ACTIVE", "SUBMIT"): "SUBMITTED",
    ("SUBMITTED", "REOPEN"): "REOPENED",
    ("EXPIRED", "REOPEN"): "REOPENED",
    ("TERMINATED", "REINSTATE"): "REINSTATED",
    ("REOPENED", "RELAUNCH"): "ACTIVE",
    ("REINSTATED", "RELAUNCH"): "ACTIVE",
}
for s in LIVE:
    EXPECTED[(s, "FORCE_SUBMIT")] = "SUBMITTED"
    EXPECTED[(s, "FORCE_TERMINATE")] = "TERMINATED"
for s in LIVE + ("REOPENED", "REINSTATED"):
    EXPECTED[(s, "EXPIRE")] = "EXPIRED"
    EXPECTED[(s, "UPDATE_DEADLINE")] = s
for s in ("SUBMITTED", "EXPIRED", "TERMINATED", "NO_SHOW"):
    EXPECTED[(s, "FINALIZE")] = "FINALIZED"


def test_transition_table_matches_prd():
    actual = {(s, t): state.target_of(t, s) for t, r in state.TRANSITIONS.items() for s in r.sources}
    assert actual == EXPECTED


def _force(attempt_id, status):
    with owner_conn() as c:
        c.execute("UPDATE attempts SET status = %s, state_version = state_version + 1, "
                  "deadline = %s WHERE id = %s", (status, NOW + timedelta(days=8), attempt_id))


def test_every_status_trigger_pair_against_database(ex):
    attempt_id = ex.enroll("matrix@example.com")
    checked = 0
    for status in state.ALL_STATUSES:
        _force(attempt_id, status)
        for trigger in state.TRANSITIONS:
            db = new_session()
            db.begin()
            try:
                set_context(db, "system")
                a = state.lock_attempt(db, attempt_id)
                before = a.state_version
                cat = "TECHNICAL" if EXPECTED.get((status, trigger)) == "TERMINATED" else None
                if (status, trigger) in EXPECTED:
                    st = state.apply(db, a, trigger, actor_kind="system", actor_id=None, reason_category=cat)
                    assert a.status == EXPECTED[(status, trigger)], (status, trigger)
                    assert a.state_version == before + 1 and st.state_version == a.state_version
                    assert st.from_status == status and st.to_status == a.status
                else:
                    with pytest.raises(AppError) as e:
                        state.apply(db, a, trigger, actor_kind="system", actor_id=None)
                    assert e.value.code == "INVALID_TRANSITION", (status, trigger)
                checked += 1
            finally:
                db.rollback()
                db.close()
    assert checked == len(state.ALL_STATUSES) * len(state.TRANSITIONS)


def test_terminated_requires_reason_category(ex):
    attempt_id = ex.enroll("cat@example.com")
    _force(attempt_id, "ACTIVE")
    for trigger in ("FORCE_TERMINATE",):
        with pytest.raises(AppError) as e, transaction("system") as db:
            state.apply(db, state.lock_attempt(db, attempt_id), trigger, actor_kind="system", actor_id=None)
        assert e.value.code == "REASON_CATEGORY_REQUIRED"
    with pytest.raises(AppError) as e, transaction("system") as db:
        state.apply(db, state.lock_attempt(db, attempt_id), "PAUSE", actor_kind="system", actor_id=None,
                    reason_category="TECHNICAL")
    assert e.value.code == "REASON_CATEGORY_NOT_APPLICABLE"
    with transaction("system") as db:
        a = state.lock_attempt(db, attempt_id)
        state.apply(db, a, "FORCE_TERMINATE", actor_kind="system", actor_id=None, reason_category="DISCIPLINARY")
        assert a.termination_reason_category == "DISCIPLINARY"


def test_database_rejects_status_change_without_version_bump(ex):
    attempt_id = ex.enroll("guard@example.com")
    with pytest.raises(Exception) as e, transaction("system") as db:
        db.execute(text("UPDATE attempts SET status = 'ACTIVE' WHERE id = :i"), {"i": attempt_id})
    assert "state_version" in str(e.value)
    with pytest.raises(Exception), transaction("system") as db:
        db.execute(text("UPDATE attempts SET deadline = now(), state_version = state_version + 2 WHERE id = :i"),
                   {"i": attempt_id})


def test_transitions_are_append_only_for_runtime_role(ex):
    attempt_id = ex.enroll("append@example.com")
    _force(attempt_id, "ACTIVE")
    with transaction("system") as db:
        state.apply(db, state.lock_attempt(db, attempt_id), "PAUSE", actor_kind="system", actor_id=None)
    for sql in ("UPDATE state_transitions SET reason = 'x'", "DELETE FROM state_transitions"):
        with pytest.raises(Exception) as e, transaction("system") as db:
            db.execute(text(sql))
        assert "permission denied" in str(e.value)


def test_transitions_write_verifiable_audit_chain(ex, world):
    attempt_id = ex.enroll("audit@example.com")
    _force(attempt_id, "ACTIVE")
    with transaction("system") as db:
        a = state.lock_attempt(db, attempt_id)
        for t in ("PAUSE", "RESUME", "INTERRUPT", "AUTO_RESUME", "SUBMIT"):
            state.apply(db, a, t, actor_kind="system", actor_id=None)
    r = world.c.get("/api/v1/org/audit-log/verify", headers=ex.h())
    assert r.json()["ok"] is True
    actions = [e["action"] for e in world.c.get("/api/v1/org/audit-log?limit=10", headers=ex.h()).json()]
    assert actions[:5] == ["attempt.submit", "attempt.auto_resume", "attempt.interrupt",
                           "attempt.resume", "attempt.pause"]
