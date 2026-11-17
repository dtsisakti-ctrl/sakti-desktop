"""Invigilator / Exam Admin actions (PRD §10.3, §11.3–11.4, §27.6–27.10)."""
import threading
from datetime import timedelta

from examguard import scheduler
from examguard.services import client_flow

from .conftest import at


def running(ex, n=1, prefix="c"):
    ids = [ex.enroll(f"{prefix}{i}@example.com") for i in range(n)]
    at(ex.window_start)
    for a in ids:
        ex.launch(a)
    at(ex.window_start + timedelta(seconds=30))
    return ids


def test_pause_keep_running_leaves_deadline(ex):
    (a,) = running(ex)
    d0 = ex.attempt(a).deadline
    r = ex.post(f"/attempts/{a}/pause", {"reason": "cek meja"}).json()
    assert r["status"] == "PAUSED" and r["state_version"] == 2
    at(ex.window_start + timedelta(minutes=10))
    r = ex.post(f"/attempts/{a}/resume", {"reason": "lanjut"}).json()
    assert r["status"] == "ACTIVE" and r["deadline"] == d0.isoformat().replace("+00:00", "Z")
    cmds = [c["type"] for c in ex.detail(a)["commands"]]
    assert cmds == ["RESUME_EXAM", "PAUSE_EXAM"]


def test_resume_after_keep_running_deadline_passed_expires(ex):
    (a,) = running(ex)
    ex.post(f"/attempts/{a}/pause", {"reason": "cek"})
    at(ex.attempt(a).deadline + timedelta(seconds=1))   # scheduler did not run
    r = ex.post(f"/attempts/{a}/resume", {"reason": "lanjut"}).json()
    assert r["status"] == "EXPIRED"


def test_add_time_sends_absolute_deadline(ex):
    (a,) = running(ex)
    d0 = ex.attempt(a).deadline
    r = ex.post(f"/attempts/{a}/add-time", {"minutes": 15, "reason": "Technical compensation"})
    assert r.status_code == 200, r.text
    a1 = ex.attempt(a)
    assert a1.deadline == d0 + timedelta(minutes=15) and a1.status == "ACTIVE" and a1.state_version == 2
    cmd = ex.detail(a)["commands"][0]
    assert cmd["type"] == "UPDATE_DEADLINE" and cmd["state_version"] == 2
    assert cmd["payload"]["deadline"] == a1.deadline.isoformat()
    t = ex.detail(a)["transitions"][-1]
    assert t["trigger"] == "UPDATE_DEADLINE" and t["from_status"] == t["to_status"] == "ACTIVE"


def test_add_time_can_pass_window_end(ex):
    (a,) = running(ex)
    ex.post(f"/attempts/{a}/add-time", {"minutes": 300, "reason": "akomodasi khusus"})
    assert ex.attempt(a).deadline > ex.window_end


def test_expected_state_version_conflict(ex):
    (a,) = running(ex)
    assert ex.post(f"/attempts/{a}/pause", {"reason": "cek", "expected_state_version": 1}).status_code == 200
    r = ex.post(f"/attempts/{a}/add-time", {"minutes": 5, "reason": "komp", "expected_state_version": 1})
    assert r.status_code == 409 and r.json()["error"]["code"] == "STATE_CONFLICT"


def test_invalid_transition_is_409(ex):
    (a,) = running(ex)
    r = ex.post(f"/attempts/{a}/resume", {"reason": "lanjut"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "INVALID_TRANSITION"
    assert "PAUSE" in r.json()["error"]["details"]["allowed"]


def test_terminate_requires_category_and_keeps_it(ex):
    (a,) = running(ex)
    assert ex.post(f"/attempts/{a}/terminate", {"reason": "joki"}).status_code == 422
    r = ex.post(f"/attempts/{a}/terminate", {"reason": "joki", "reason_category": "DISCIPLINARY"})
    assert r.json()["status"] == "TERMINATED"
    d = ex.detail(a)
    assert d["termination_reason_category"] == "DISCIPLINARY"
    assert d["available_actions"] == ["reinstate"]


def test_force_submit_from_waiting(ex):
    (a,) = running(ex)
    ex.register(a)                           # second device -> WAITING
    r = ex.post(f"/attempts/{a}/force-submit", {"reason": "waktu hampir habis"})
    assert r.json()["status"] == "SUBMITTED"
    cmd = ex.detail(a)["commands"][0]
    pending = [d for d in ex.detail(a)["device_sessions"] if d["status"] == "PENDING_APPROVAL"][0]
    assert cmd["type"] == "FORCE_SUBMIT" and cmd["device_session_id"] == pending["id"]


def test_reopen_revives_closed_exam_and_relaunch(ex):
    (a,) = running(ex)
    ex.call(client_flow.submit, a)
    at(ex.latest_start + timedelta(minutes=1))
    scheduler.tick()
    assert ex.get(f"/exams/{ex.id}").json()["status"] == "CLOSED"
    past = (ex.latest_start - timedelta(minutes=1)).isoformat()
    assert ex.post(f"/attempts/{a}/reopen", {"reason": "soal error", "deadline": past}).status_code == 422
    new_deadline = ex.latest_start + timedelta(minutes=40)
    r = ex.post(f"/attempts/{a}/reopen", {"reason": "soal error", "deadline": new_deadline.isoformat()})
    assert r.json()["status"] == "REOPENED"
    assert ex.get(f"/exams/{ex.id}").json()["status"] == "RUNNING"
    assert ex.attempt(a).reopen_count == 1
    assert all(d["status"] == "REVOKED" for d in ex.detail(a)["device_sessions"])
    st = ex.register(a)
    assert st["status"] == "ACTIVE" and st["deadline"] == new_deadline
    # still running: not closed until the attempt ends again
    at(new_deadline + timedelta(seconds=1))
    c = scheduler.tick()
    assert c["expired"] == 1 and c["closed"] == 1


def test_reinstate_then_relaunch_after_deadline_expires(ex):
    (a,) = running(ex)
    ex.post(f"/attempts/{a}/terminate", {"reason": "salah orang", "reason_category": "ADMINISTRATIVE"})
    d = ex.window_start + timedelta(minutes=30)
    r = ex.post(f"/attempts/{a}/reinstate", {"reason": "keliru", "deadline": d.isoformat()})
    assert r.json()["status"] == "REINSTATED"
    at_ = ex.attempt(a)
    assert at_.reinstate_count == 1 and at_.termination_reason_category is None
    at(d + timedelta(seconds=1))
    assert ex.register(a)["status"] == "EXPIRED"


def test_finalize(ex):
    a, b = running(ex, 2)
    assert ex.post(f"/exams/{ex.id}/finalize", {}).json()["error"]["code"] == "INVALID_TRANSITION"
    ex.call(client_flow.submit, a)
    ex.post(f"/attempts/{b}/terminate", {"reason": "koneksi", "reason_category": "TECHNICAL"})
    at(ex.latest_start + timedelta(seconds=1))
    scheduler.tick()
    r = ex.post(f"/exams/{ex.id}/finalize", {"reason": "nilai final"})
    assert r.json() == {"exam_id": str(ex.id), "status": "FINALIZED", "attempts_finalized": 2}
    assert (ex.attempt(a).status, ex.attempt(a).final_status) == ("FINALIZED", "SUBMITTED")
    assert ex.attempt(b).final_status == "TERMINATED"
    r = ex.post(f"/attempts/{b}/reinstate", {"reason": "keliru", "deadline": (ex.window_end).isoformat()})
    assert r.json()["error"]["code"] == "INVALID_TRANSITION"


def test_extend_whole_exam(ex):
    a, b = running(ex, 2)
    late = ex.enroll("late@example.com")
    ex.post(f"/attempts/{b}/pause", {"reason": "cek", "timer_mode": "PAUSE_TIMER"})
    d_a, d_b = ex.attempt(a).deadline, ex.attempt(b).deadline
    r = ex.post(f"/exams/{ex.id}/extend", {"minutes": 10, "reason": "server gangguan"}).json()
    assert r["attempts_updated"] == 2 and r["extension_minutes"] == 10
    assert ex.attempt(a).deadline == d_a + timedelta(minutes=10)
    assert ex.attempt(b).deadline == d_b + timedelta(minutes=10)
    at(ex.latest_start)
    ex.launch(late)   # FIXED_END: min(start+90, window_end) + 10
    assert ex.attempt(late).deadline == ex.window_end + timedelta(minutes=10)


def test_bulk_actions(ex):
    a, b, c = (str(x) for x in running(ex, 3))
    ex.post(f"/attempts/{c}/pause", {"reason": "cek"})
    r = ex.post(f"/exams/{ex.id}/bulk", {"action": "PAUSE", "attempt_ids": [a, b, c], "reason": "gangguan"}).json()
    assert r["succeeded"] == 2 and r["failed"] == 1
    assert [x["error"] for x in r["results"] if not x["ok"]] == ["INVALID_TRANSITION"]
    r = ex.post(f"/exams/{ex.id}/bulk", {"action": "ADD_TIME", "minutes": 5, "attempt_ids": [a, b, c],
                                         "reason": "kompensasi"}).json()
    assert r["succeeded"] == 3
    body = {"action": "TERMINATE", "attempt_ids": [a, b], "reason": "batal", "reason_category": "ADMINISTRATIVE"}
    assert ex.post(f"/exams/{ex.id}/bulk", body).json()["error"]["code"] == "CONFIRMATION_REQUIRED"
    r = ex.post(f"/exams/{ex.id}/bulk", {**body, "confirm_exam_code": "EX1"}).json()
    assert r["succeeded"] == 2
    actions = [e["action"] for e in ex.w.c.get("/api/v1/org/audit-log?limit=5", headers=ex.h()).json()]
    assert actions[0] == "bulk.completed" and "bulk.started" in actions


def test_warning_command(ex):
    (a,) = running(ex)
    r = ex.post(f"/attempts/{a}/warning", {"message": "Harap menghadap kamera"})
    assert r.json()["state_version"] == 1   # no state change
    assert ex.detail(a)["commands"][0]["payload"] == {"message": "Harap menghadap kamera"}


def test_concurrent_actions_are_serialized(ex):
    (a,) = running(ex)
    codes: list[int] = []
    barrier = threading.Barrier(4)

    def act():
        barrier.wait()
        codes.append(ex.post(f"/attempts/{a}/pause", {"reason": "bersamaan"}).status_code)

    threads = [threading.Thread(target=act) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(codes) == [200, 409, 409, 409]
    assert ex.attempt(a).state_version == 2


def test_live_monitoring_view(ex):
    a, b = running(ex, 2)
    ex.enroll("waiting@example.com")
    ex.post(f"/attempts/{b}/pause", {"reason": "cek", "timer_mode": "PAUSE_TIMER"})
    at(ex.window_start + timedelta(minutes=5))
    ex.heartbeat(next(d["id"] for d in ex.detail(a)["device_sessions"]), 1)
    v = ex.get(f"/exams/{ex.id}/attempts").json()
    s = v["summary"]
    assert (s["ACTIVE"], s["PAUSED"], s["NOT_STARTED"], s["ONLINE"], s["OFFLINE"]) == (1, 1, 1, 1, 1)
    rows = {r["candidate_email"]: r for r in v["attempts"]}
    assert rows["c0@example.com"]["remaining_seconds"] == 85 * 60
    assert rows["c1@example.com"]["remaining_seconds"] == 89 * 60 + 30   # frozen at pause time


def test_invitations_blocked_once_running(ex):
    """PRD v0.3.1 §8.4 / Q13."""
    at(ex.window_start)
    scheduler.tick()
    r = ex.post(f"/exams/{ex.id}/invitations", {"emails": ["baru@example.com"]})
    assert r.status_code == 409
