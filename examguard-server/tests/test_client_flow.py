"""Launch, start, heartbeat, interruption and re-entry (PRD §12.2, §17.6, §18, §20)."""
from datetime import timedelta
from uuid import UUID

import pytest

from examguard.errors import AppError
from examguard.services import client_flow

from .conftest import Exam1b, at


def err(fn, *a, **kw) -> str:
    with pytest.raises(AppError) as e:
        fn(*a, **kw)
    return e.value.code


def test_launch_window_and_deadline(ex):
    aid = ex.enroll("a@example.com")
    at(ex.checkin_open - timedelta(minutes=1))
    assert err(ex.register, aid) == "CHECKIN_NOT_OPEN"
    at(ex.checkin_open)
    ds = ex.register(aid)["device_session_id"]
    assert err(ex.call, client_flow.start, aid, ds) == "START_NOT_YET_ALLOWED"
    at(ex.window_start + timedelta(minutes=20))
    st = ex.call(client_flow.start, aid, ds)
    assert st["status"] == "ACTIVE" and st["state_version"] == 1
    # FIXED_END, 2 h window, 90 min: starting 20 min late still ends at start + 90 (< window_end)
    assert st["deadline"] == ex.window_start + timedelta(minutes=110)
    assert ex.get(f"/exams/{ex.id}").json()["status"] == "RUNNING"   # promoted inline, no scheduler


def test_late_start_refused(ex):
    aid = ex.enroll("late@example.com")
    at(ex.window_start)
    ds = ex.register(aid)["device_session_id"]
    at(ex.latest_start + timedelta(seconds=1))
    assert err(ex.call, client_flow.start, aid, ds) == "LATE_START_CLOSED"
    assert err(ex.register, aid) == "LATE_START_CLOSED"


def test_accommodation_in_initial_deadline(ex):
    aid = ex.enroll("acc@example.com", accommodation=30)
    at(ex.window_start)
    ex.launch(aid)
    assert ex.attempt(aid).deadline == ex.window_start + timedelta(minutes=120)


def test_accommodation_change_after_start_does_not_move_deadline(ex):
    """PRD v0.3.1 §11.3 / Q12."""
    aid = ex.enroll("q12@example.com")
    at(ex.window_start)
    ex.launch(aid)
    before = ex.attempt(aid)
    enr = ex.detail(aid)["enrollment_id"]
    r = ex.w.c.patch(f"/api/v1/org/enrollments/{enr}", json={"time_accommodation_minutes": 45}, headers=ex.h())
    assert r.status_code == 200
    after = ex.attempt(aid)
    assert after.deadline == before.deadline and after.state_version == before.state_version


def test_identity_check_gate(world):
    ex = Exam1b(world, org_slug="idc", identity_check="MANUAL")
    aid = ex.enroll("id@example.com")
    at(ex.checkin_open)
    ds = ex.register(aid)["device_session_id"]
    ex.call(client_flow.submit_identity, aid)
    assert err(ex.call, client_flow.submit_identity, aid) == "IDENTITY_ALREADY_SUBMITTED"
    at(ex.window_start)
    assert err(ex.call, client_flow.start, aid, ds) == "IDENTITY_NOT_APPROVED"
    # three rejections, then the candidate must be handled in person
    for i in range(3):
        r = ex.post(f"/attempts/{aid}/identity/reject", {"reason": "foto buram"})
        assert r.status_code == 200 and r.json()["retries_left"] == 2 - i
        if i < 2:
            ex.call(client_flow.submit_identity, aid)
    assert err(ex.call, client_flow.submit_identity, aid) == "IDENTITY_RETRY_LIMIT"
    assert ex.post(f"/attempts/{aid}/identity/reject", {}).json()["error"]["code"] == "IDENTITY_NOT_PENDING"


def test_identity_approved_then_start(world):
    ex = Exam1b(world, org_slug="idc2", identity_check="MANUAL")
    aid = ex.enroll("id2@example.com")
    at(ex.checkin_open)
    ds = ex.register(aid)["device_session_id"]
    ex.call(client_flow.submit_identity, aid)
    assert ex.post(f"/attempts/{aid}/identity/reject", {}).status_code == 422   # reason required
    assert ex.post(f"/attempts/{aid}/identity/approve", {}).json()["identity_status"] == "APPROVED"
    at(ex.window_start)
    assert ex.call(client_flow.start, aid, ds)["status"] == "ACTIVE"


def test_heartbeat_replay_is_ignored(ex):
    aid = ex.enroll("hb@example.com")
    at(ex.window_start)
    ds = ex.launch(aid)
    assert ex.heartbeat(ds, 5)["stale"] is False
    assert ex.heartbeat(ds, 5)["stale"] is True
    assert ex.heartbeat(ds, 3)["stale"] is True


def _interrupt(ex, aid, ds, silent: timedelta):
    """Go silent for `silent`, let the scheduler notice, then reconnect with the same device."""
    from examguard import scheduler
    t0 = ex.window_start + timedelta(minutes=5)
    at(t0)
    ex.heartbeat(ds, 1)
    at(t0 + timedelta(seconds=61))
    assert scheduler.tick()["interrupted"] == 1
    assert ex.attempt(aid).status == "INTERRUPTED"
    at(t0 + silent)
    return ex.heartbeat(ds, 2, cause="NETWORK_FAILURE")


def test_short_gap_auto_resumes(ex):
    aid = ex.enroll("short@example.com")
    at(ex.window_start)
    ds = ex.launch(aid)
    r = _interrupt(ex, aid, ds, timedelta(minutes=6, seconds=14))
    assert r["status"] == "ACTIVE"
    rows = ex.get(f"/exams/{ex.id}/reentry").json()
    assert rows[0]["outcome"] == "AUTO_RESUMED" and rows[0]["gap_seconds"] == 374
    assert rows[0]["cause"] == "NETWORK_FAILURE"


def test_long_gap_needs_approval_then_allowed(ex):
    aid = ex.enroll("long@example.com")
    at(ex.window_start)
    ds = ex.launch(aid)
    r = _interrupt(ex, aid, ds, timedelta(minutes=14, seconds=18))
    assert r["status"] == "WAITING_FOR_INVIGILATOR"
    assert ex.get(f"/exams/{ex.id}/reentry").json()[0]["gap_seconds"] == 858
    d = ex.detail(aid)
    assert {"allow_reentry", "reject_reentry"} <= set(d["available_actions"])
    r = ex.post(f"/attempts/{aid}/reentry/allow", {"reason": "listrik padam", "expected_state_version": d["state_version"]})
    assert r.status_code == 200 and r.json()["status"] == "ACTIVE"
    assert ex.detail(aid)["commands"][0]["type"] == "ALLOW_REENTRY"


def test_reject_reentry_terminates_with_category(ex):
    aid = ex.enroll("rej@example.com")
    at(ex.window_start)
    ds = ex.launch(aid)
    _interrupt(ex, aid, ds, timedelta(minutes=20))
    assert ex.post(f"/attempts/{aid}/reentry/reject", {"reason": "tidak kembali"}).status_code == 422
    r = ex.post(f"/attempts/{aid}/reentry/reject", {"reason": "tidak kembali", "reason_category": "TECHNICAL"})
    assert r.json()["status"] == "TERMINATED"
    a = ex.attempt(aid)
    assert a.termination_reason_category == "TECHNICAL"


def test_reconnect_after_deadline_expires(ex):
    aid = ex.enroll("exp@example.com")
    at(ex.window_start)
    ds = ex.launch(aid)
    at(ex.window_start + timedelta(seconds=10))
    ex.heartbeat(ds, 1)
    # silent until after the deadline; no scheduler tick in between
    at(ex.window_start + timedelta(minutes=95))
    r = ex.heartbeat(ds, 2)
    assert r["status"] == "EXPIRED"
    triggers = [t["trigger"] for t in ex.detail(aid)["transitions"]]
    assert triggers == ["START", "INTERRUPT", "EXPIRE"]


def test_heartbeat_detects_gap_when_scheduler_lagged(ex):
    aid = ex.enroll("lag@example.com")
    at(ex.window_start)
    ds = ex.launch(aid)
    at(ex.window_start + timedelta(minutes=3))
    assert ex.heartbeat(ds, 1)["status"] == "ACTIVE"
    triggers = [t["trigger"] for t in ex.detail(aid)["transitions"]]
    assert triggers == ["START", "INTERRUPT", "AUTO_RESUME"]


def test_device_change_requires_approval(ex):
    aid = ex.enroll("dev@example.com")
    at(ex.window_start)
    old = ex.launch(aid)
    at(ex.window_start + timedelta(minutes=5))
    r = ex.register(aid, client_version="0.2.0")
    new = r["device_session_id"]
    assert r["device_status"] == "PENDING_APPROVAL" and r["status"] == "WAITING_FOR_INVIGILATOR"
    # a third device replaces the pending one
    newer = ex.register(aid)["device_session_id"]
    ex.post(f"/attempts/{aid}/reentry/allow", {"reason": "laptop rusak"})
    devices = {UUID(d["id"]): d for d in ex.detail(aid)["device_sessions"]}
    assert devices[old]["status"] == "REVOKED" and devices[new]["status"] == "REVOKED"
    assert devices[newer]["status"] == "ACTIVE"
    assert err(ex.heartbeat, old, 10) == "DEVICE_SESSION_REVOKED"


def test_register_while_paused_is_refused(ex):
    aid = ex.enroll("p@example.com")
    at(ex.window_start)
    ex.launch(aid)
    ex.post(f"/attempts/{aid}/pause", {"reason": "cek ruangan"})
    assert err(ex.register, aid) == "ATTEMPT_PAUSED"


def test_manual_finish_submits(ex):
    aid = ex.enroll("done@example.com")
    at(ex.window_start)
    ex.launch(aid)
    assert ex.call(client_flow.submit, aid)["status"] == "SUBMITTED"
    assert err(ex.call, client_flow.submit, aid) == "INVALID_TRANSITION"
    assert err(ex.register, aid) == "ATTEMPT_ENDED"


def test_waiting_in_checkin_is_not_an_interruption(ex):
    """Registered at check-in, started 30 minutes later: the first heartbeat must not count as a gap."""
    aid = ex.enroll("early@example.com")
    at(ex.checkin_open)
    ds = ex.register(aid)["device_session_id"]
    at(ex.window_start)
    ex.call(client_flow.start, aid, ds)
    at(ex.window_start + timedelta(seconds=10))
    assert ex.heartbeat(ds, 1)["status"] == "ACTIVE"
