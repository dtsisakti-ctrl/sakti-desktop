"""Time-driven transitions (PRD §9, §10.3, §17.6)."""
from datetime import timedelta

import psycopg

from examguard import scheduler

from .conftest import APP_URL, Exam1b, at


def status(ex, aid):
    return ex.attempt(aid).status


def test_ready_to_running_at_window_start(ex):
    at(ex.window_start - timedelta(seconds=1))
    assert scheduler.tick()["running"] == 0
    at(ex.window_start)
    assert scheduler.tick()["running"] == 1
    assert ex.get(f"/exams/{ex.id}").json()["status"] == "RUNNING"
    assert scheduler.tick()["running"] == 0   # idempotent


def test_no_show_after_latest_start(ex):
    aid = ex.enroll("ns@example.com")
    at(ex.latest_start)
    scheduler.tick()
    assert status(ex, aid) == "NOT_STARTED"   # exactly at latest_start a start is still allowed
    at(ex.latest_start + timedelta(seconds=1))
    assert scheduler.tick()["no_show"] == 1
    assert status(ex, aid) == "NO_SHOW"


def test_expire_at_deadline(ex):
    aid = ex.enroll("e@example.com")
    at(ex.window_start)
    ds = ex.launch(aid)
    deadline = ex.attempt(aid).deadline
    for i, t in enumerate(range(0, 90 * 60, 50), start=1):   # keep heartbeating
        at(ex.window_start + timedelta(seconds=t))
        ex.heartbeat(ds, i)
    at(deadline - timedelta(seconds=1))
    assert scheduler.tick()["expired"] == 0
    at(deadline)
    assert scheduler.tick()["expired"] == 1
    assert status(ex, aid) == "EXPIRED"


def test_pause_timer_freezes_expiry_but_keep_running_does_not(ex):
    a1, a2 = ex.enroll("k@example.com"), ex.enroll("p@example.com")
    at(ex.window_start)
    ex.launch(a1), ex.launch(a2)
    at(ex.window_start + timedelta(minutes=80))
    ex.post(f"/attempts/{a1}/pause", {"reason": "cek", "timer_mode": "KEEP_RUNNING"})
    ex.post(f"/attempts/{a2}/pause", {"reason": "cek", "timer_mode": "PAUSE_TIMER"})
    at(ex.window_start + timedelta(minutes=100))
    assert scheduler.tick()["expired"] == 1
    assert status(ex, a1) == "EXPIRED" and status(ex, a2) == "PAUSED"
    r = ex.post(f"/attempts/{a2}/resume", {"reason": "lanjut"}).json()
    assert r["status"] == "ACTIVE"
    assert ex.attempt(a2).deadline == ex.window_start + timedelta(minutes=110)   # +20 min paused


def test_interrupt_uses_exam_level_threshold(ex):
    r = ex.w.c.patch(f"/api/v1/org/exams/{ex.id}/settings", headers=ex.h(),
                     json={"overrides": {"interruption_threshold_seconds": 120}})
    assert r.status_code == 200, r.text
    aid = ex.enroll("i@example.com")
    at(ex.window_start)
    ex.launch(aid)
    at(ex.window_start + timedelta(seconds=90))
    assert scheduler.tick()["interrupted"] == 0
    at(ex.window_start + timedelta(seconds=121))
    assert scheduler.tick()["interrupted"] == 1
    assert status(ex, aid) == "INTERRUPTED"


def test_close_when_all_final_and_start_window_over(ex):
    a1, _ = ex.enroll("c1@example.com"), ex.enroll("c2@example.com")
    at(ex.window_start)
    ex.launch(a1)
    from examguard.services import client_flow
    ex.call(client_flow.submit, a1)
    scheduler.tick()
    assert ex.get(f"/exams/{ex.id}").json()["status"] == "RUNNING"   # a2 may still start
    at(ex.latest_start + timedelta(seconds=1))
    counts = scheduler.tick()
    assert counts["no_show"] == 1 and counts["closed"] == 1
    assert ex.get(f"/exams/{ex.id}").json()["status"] == "CLOSED"


def test_exam_without_enrollments_closes(ex):
    at(ex.latest_start + timedelta(seconds=1))
    c = scheduler.tick()
    assert c["running"] == 1 and c["closed"] == 1


def test_locked_rows_are_skipped_not_waited_on(ex):
    aid = ex.enroll("lock@example.com")
    at(ex.latest_start + timedelta(seconds=1))
    # Another transaction (e.g. a staff action) holds the attempt row.
    with psycopg.connect(APP_URL.replace("+psycopg", "")) as other:
        other.execute("SELECT set_config('app.ctx', 'system', true)")
        other.execute("SELECT 1 FROM attempts WHERE id = %s FOR UPDATE", (aid,))
        assert scheduler.tick()["no_show"] == 0
        assert status(ex, aid) == "NOT_STARTED"
        other.rollback()
    assert scheduler.tick()["no_show"] == 1


def test_tick_is_tenant_wide(world):
    a = Exam1b(world, org_slug="org-a", code="A1")
    b = Exam1b(world, org_slug="org-b", code="B1")
    x, y = a.enroll("x@example.com"), b.enroll("y@example.com")
    at(a.latest_start + timedelta(seconds=1))
    assert scheduler.tick()["no_show"] == 2
    assert status(a, x) == status(b, y) == "NO_SHOW"
    assert world.c.get("/api/v1/org/audit-log/verify", headers=a.h()).json()["ok"]
    assert world.c.get("/api/v1/org/audit-log/verify", headers=b.h()).json()["ok"]
