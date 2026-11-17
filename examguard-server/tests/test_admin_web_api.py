"""Endpoints added for the Admin Web (Phase 3a) and serving the built UI."""
from datetime import timedelta

from examguard import crypto
from examguard.config import get_settings

from .conftest import Exam1b, at
from .refclient import RefClient
from .test_protocol import link


def test_dashboard_counts_and_invigilator_scope(world, root_key):
    ex = Exam1b(world)
    a1, a2 = ex.enroll("a@example.com"), ex.enroll("b@example.com")
    ex.enroll("c@example.com")
    at(ex.window_start)
    ex.launch(a1)
    ex.launch(a2)
    ex.post(f"/attempts/{a2}/pause", {"reason": "cek meja"})
    d = ex.get("/dashboard").json()
    row = d["exams"][0]
    assert (row["code"], row["status"], row["enrolled"], row["paused"]) == ("EX1", "RUNNING", 3, 1)
    assert row["online"] == 2 and d["totals"]["running_exams"] == 1
    inv_id, inv = ex.add_staff("inv@acme.example.com")
    assert ex.get("/dashboard", ex.as_(inv)).json()["exams"] == []
    ex.post(f"/exams/{ex.id}/invigilators", {"user_id": str(inv_id)})
    assert [e["code"] for e in ex.get("/dashboard", ex.as_(inv)).json()["exams"]] == ["EX1"]


def test_assignable_invigilators_requires_assign(world):
    ex = Exam1b(world)
    _, inv = ex.add_staff("inv@acme.example.com")
    rows = ex.get("/invigilators").json()
    assert [r["email"] for r in rows] == ["inv@acme.example.com"]
    assert ex.get("/invigilators", ex.as_(inv)).status_code == 403


def test_rows_and_detail_include_incidents_events_health(world, root_key):
    ex = Exam1b(world)
    aid = ex.enroll("cand@example.com")
    rc = RefClient(world.c, crypto.public_raw(root_key))
    at(ex.checkin_open)
    t = link(ex)
    rc.launch(t)
    rc.register(t)
    at(ex.window_start)
    rc.start()
    rc.heartbeat(health={"lockdown_ok": True, "camera_ok": False})
    rc.call("POST", "/events", {"events": [rc.event("MULTIPLE_PERSON", confidence=0.8), rc.event("NAVIGATION_BLOCKED")]})
    v = ex.get(f"/exams/{ex.id}/attempts").json()
    row = v["attempts"][0]
    assert row["open_incidents"] == 1 and row["health"]["camera_ok"] is False and row["client_version"] == "0.2.0"
    assert v["summary"]["OPEN_INCIDENTS"] == 1
    d = ex.detail(aid)
    assert {e["type"] for e in d["events"]} == {"MULTIPLE_PERSON", "NAVIGATION_BLOCKED"}
    person = next(e for e in d["events"] if e["type"] == "MULTIPLE_PERSON")
    assert person["severity"] == "HIGH" and person["incident_status"] == "OPEN"


def test_web_ui_served_with_spa_fallback(client, tmp_path):
    get_settings().web_ui_dir = str(tmp_path)
    try:
        assert client.get("/admin/").status_code == 503              # not built yet
        assert client.get("/").status_code == 503
        (tmp_path / "index.html").write_text("<p>landing</p>")
        for app in ("admin", "portal"):
            (tmp_path / app).mkdir()
            (tmp_path / app / "index.html").write_text(f"<div id={app}></div>")
        (tmp_path / "assets").mkdir()
        (tmp_path / "assets" / "app-1.js").write_text("console.log(1)")
        assert "landing" in client.get("/").text
        assert client.get("/portal", follow_redirects=False).headers["location"] == "/portal/"
        r = client.get("/admin/exams/123/live")
        assert r.status_code == 200 and "id=admin" in r.text and r.headers["cache-control"] == "no-cache"
        r = client.get("/portal/reset-password?token=abc")
        assert r.status_code == 200 and "id=portal" in r.text
        js = client.get("/assets/app-1.js")
        assert js.text == "console.log(1)" and "immutable" in js.headers["cache-control"]
        assert client.get("/assets/missing.js").status_code == 404
        # an encoded traversal reaches the handler as "../.."; it must fall back to index.html
        r = client.get("/admin/%2e%2e/%2e%2e/%2e%2e/etc/passwd")
        assert r.status_code in (200, 404) and "root:" not in r.text
        assert client.get("/assets/%2e%2e/%2e%2e/etc/passwd").status_code == 404
    finally:
        get_settings().web_ui_dir = None


def test_detail_lists_the_candidates_incidents_open_first(world, root_key):
    """Candidate panel (§27.6): what the incidents are, when, how long, and their review status."""
    from datetime import timedelta
    ex = Exam1b(world)
    aid = ex.enroll("cand@example.com")
    other = ex.enroll("other@example.com")
    rc = RefClient(world.c, crypto.public_raw(root_key))
    at(ex.checkin_open)
    t = link(ex)
    rc.launch(t)
    rc.register(t)
    at(ex.window_start)
    rc.start()
    t0 = ex.window_start + timedelta(minutes=1)
    rc.call("POST", "/events", {"events": [
        rc.event("FACE_MISSING", phase="OPEN", started_at=t0.isoformat()),
        rc.event("FACE_MISSING", phase="CLOSE", started_at=t0.isoformat(),
                 ended_at=(t0 + timedelta(seconds=42)).isoformat()),
        rc.event("FOCUS_LOST", started_at=(t0 + timedelta(minutes=2)).isoformat()),
    ]})
    first = ex.detail(aid)["incidents"]
    assert [i["type"] for i in first] == ["FOCUS_LOST", "FACE_MISSING"]          # newest first
    face = first[1]
    assert face["event_count"] == 2 and face["status"] == "OPEN"
    assert face["started_at"].startswith(t0.isoformat()[:19])
    from datetime import datetime
    dur = datetime.fromisoformat(face["ended_at"]) - datetime.fromisoformat(face["started_at"])
    assert dur == timedelta(seconds=42)
    r = world.c.post(f"/api/v1/org/incidents/{first[0]['id']}/review", headers=ex.h(),
                     json={"status": "DISMISSED", "note": "kedip"})
    assert r.status_code == 200, r.text
    after = ex.detail(aid)["incidents"]
    assert [i["status"] for i in after] == ["OPEN", "DISMISSED"]                 # open first
    assert after[1]["review_note"] == "kedip"
    assert ex.detail(other)["incidents"] == []
