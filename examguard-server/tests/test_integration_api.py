"""Integration API (PRD §16.4–16.5), completion token and webhooks (§16.6)."""
import json
from datetime import timedelta

import pytest

from examguard import crypto, scheduler, webhooks
from examguard.db import transaction

from .conftest import Exam1b, at
from .refclient import RefClient


@pytest.fixture
def lms(world, root_key):
    ex = Exam1b(world)
    r = ex.post("/integrations", {"name": "LMS Kampus", "webhook_url": "https://lms.example.edu/hooks"}, ex.admin)
    assert r.status_code == 201, r.text
    cred = r.json()
    assert cred["secret"].startswith("egs_") and cred["client_id"].startswith("egi_")
    return ex, (cred["client_id"], cred["secret"]), cred, RefClient(world.c, crypto.public_raw(root_key))


def api(ex, cred, method, path, json_=None):
    return ex.w.c.request(method, f"/integration/v1{path}", json=json_, auth=cred)


def enroll(ex, cred, ref="NIM-001", email="mhs1@kampus.ac.id"):
    r = api(ex, cred, "POST", f"/exams/{ex.id}/candidates", {"email": email, "full_name": "Mahasiswa", "candidate_ref": ref})
    assert r.status_code == 201, r.text
    return r.json()


def test_management_is_org_admin_only(lms):
    ex, cred, out, _ = lms
    assert ex.get("/integrations", ex.ea).status_code == 403
    listed = ex.get("/integrations", ex.admin).json()
    assert listed[0]["client_id"] == cred[0] and listed[0]["secret"] is None
    assert ex.post("/integrations", {"name": "x", "webhook_url": "ftp://bad"}, ex.admin).status_code == 422


def test_credentials(lms):
    ex, cred, out, _ = lms
    assert api(ex, cred, "GET", "/exams").json()[0]["code"] == "EX1"
    assert api(ex, (cred[0], "egs_wrong"), "GET", "/exams").json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert ex.w.c.get("/integration/v1/exams").status_code == 401
    new = ex.post(f"/integrations/{out['id']}/rotate-secret", {}, ex.admin).json()["secret"]
    assert api(ex, cred, "GET", "/exams").status_code == 401
    assert api(ex, (cred[0], new), "GET", "/exams").status_code == 200
    ex.post(f"/integrations/{out['id']}/revoke", {}, ex.admin)
    assert api(ex, (cred[0], new), "GET", "/exams").status_code == 401


def test_register_is_idempotent_per_candidate_ref(lms):
    ex, cred, _, _ = lms
    a = enroll(ex, cred)
    assert a["created"] is True and a["launch"]["launch_url"].startswith("examguard://launch?t=")
    b = enroll(ex, cred)
    assert b["created"] is False and b["attempt_id"] == a["attempt_id"]
    assert b["launch"]["launch_token"] != a["launch"]["launch_token"]
    r = api(ex, cred, "POST", f"/exams/{ex.id}/candidates",
            {"email": "mhs1@kampus.ac.id", "full_name": "Mahasiswa", "candidate_ref": "NIM-999"})
    assert r.json()["error"]["code"] == "ALREADY_REGISTERED"
    at(ex.window_start)
    scheduler.tick()
    r = api(ex, cred, "POST", f"/exams/{ex.id}/candidates", {"email": "late@kampus.ac.id", "full_name": "L",
                                                             "candidate_ref": "NIM-002"})
    assert r.json()["error"]["code"] == "ENROLLMENT_CLOSED"


def test_other_org_is_invisible(lms, world):
    ex, cred, _, _ = lms
    at(ex.checkin_open - timedelta(days=1))
    other = Exam1b(world, org_slug="beta", code="B1")
    aid = other.enroll("x@example.com")
    assert api(ex, cred, "GET", f"/attempts/{aid}").status_code == 404
    assert api(ex, cred, "POST", f"/exams/{other.id}/candidates",
               {"email": "a@b.co", "full_name": "A", "candidate_ref": "R"}).status_code == 404


def test_level2_completion_flow(lms):
    ex, cred, _, rc = lms
    at(ex.checkin_open)
    reg = enroll(ex, cred)
    token = reg["launch"]["launch_token"]
    rc.launch(token)
    rc.register(token)
    at(ex.window_start)
    rc.start()
    aid = reg["attempt_id"]
    assert api(ex, cred, "GET", f"/attempts/{aid}").json()["status"] == "ACTIVE"
    # the LMS checks the attestation token before saving answers
    att = rc.call("POST", "/attestation").json()["token"]
    ks = rc.key_set()
    claims = crypto.jwt_decode(att, lambda k: ks[k]["x"] if ks.get(k, {}).get("use") == "token" else None)
    assert claims["candidate_ref"] == "NIM-001"
    r = api(ex, cred, "POST", f"/attempts/{aid}/completion")
    assert r.status_code == 200 and r.json()["status"] == "SUBMITTED"
    comp = crypto.jwt_decode(r.json()["completion_token"], lambda k: ks[k]["x"] if ks.get(k, {}).get("use") == "token" else None)
    assert comp["typ"] == "completion" and comp["attempt_id"] == aid and comp["device_session_id"] == rc.sid
    assert comp["exp"] - comp["iat"] == 600 and len(comp["nonce"]) >= 20
    # retry after a lost response: new token, no second transition
    again = api(ex, cred, "POST", f"/attempts/{aid}/completion").json()
    assert again["state_version"] == r.json()["state_version"]
    assert rc.state()["status"] == "SUBMITTED"
    transitions = [t["trigger"] for t in ex.detail(aid)["transitions"]]
    assert transitions == ["START", "SUBMIT"]
    res = api(ex, cred, "POST", f"/attempts/{aid}/result", {"score": 87.5, "max_score": 100, "passed": True})
    assert res.json()["result"]["score"] == 87.5


def test_completion_refused_when_not_active(lms):
    ex, cred, _, rc = lms
    at(ex.checkin_open)
    reg = enroll(ex, cred)
    t = reg["launch"]["launch_token"]
    rc.launch(t)
    rc.register(t)
    at(ex.window_start)
    rc.start()
    ex.post(f"/attempts/{reg['attempt_id']}/pause", {"reason": "cek meja"})
    r = api(ex, cred, "POST", f"/attempts/{reg['attempt_id']}/completion")
    assert r.status_code == 409 and r.json()["error"]["details"]["status"] == "PAUSED"
    assert api(ex, cred, "POST", f"/attempts/{reg['attempt_id']}/result", {"score": 1}).json()["error"]["code"] == \
        "ATTEMPT_NOT_FINAL"


def test_webhooks_signed_retried_and_idempotent(lms):
    ex, cred, out, rc = lms
    at(ex.checkin_open)
    reg = enroll(ex, cred)
    t = reg["launch"]["launch_token"]
    rc.launch(t)
    rc.register(t)
    at(ex.window_start)
    rc.start()
    ex.post(f"/attempts/{reg['attempt_id']}/add-time", {"minutes": 5, "reason": "kompensasi"})
    sent: list[tuple[str, bytes, dict]] = []
    responses = iter([503, 200, 200])

    def fake(url, body, headers):
        sent.append((url, body, headers))
        return next(responses)

    first = webhooks.deliver_due(send=fake)
    assert first == {"delivered": 1, "retry": 1, "failed": 0}
    url, body, headers = sent[0]
    payload = json.loads(body)
    assert url == "https://lms.example.edu/hooks" and payload["type"] == "attempt.started"
    assert payload["candidate_ref"] == "NIM-001" and headers["X-ExamGuard-Event-Id"] == payload["event_id"]
    assert webhooks.verify(rc.key_set(), headers["X-ExamGuard-Signature"], body)
    assert not webhooks.verify(rc.key_set(), headers["X-ExamGuard-Signature"], body.replace(b"NIM-001", b"NIM-002"))
    assert webhooks.deliver_due(send=fake) == {"delivered": 0, "retry": 0, "failed": 0}   # backoff not elapsed
    at(ex.window_start + timedelta(seconds=31))
    webhooks.deliver_due(send=fake)
    retried = [json.loads(b) for _, b, _ in sent]
    assert retried[-1]["event_id"] == retried[0]["event_id"] or retried[-1]["event_id"] == retried[1]["event_id"]
    log = ex.get(f"/integrations/{out['id']}/deliveries", ex.admin).json()
    assert {d["event_type"] for d in log} == {"attempt.started", "attempt.deadline_updated"}
    assert all(d["status"] == "DELIVERED" for d in log)


def test_webhooks_give_up_after_max_attempts(lms):
    ex, cred, out, rc = lms
    at(ex.checkin_open)
    reg = enroll(ex, cred)
    t = reg["launch"]["launch_token"]
    rc.launch(t)
    rc.register(t)
    at(ex.window_start)
    rc.start()

    def down(url, body, headers):
        raise ConnectionError("connection refused")

    now = ex.window_start
    for _ in range(webhooks.MAX_ATTEMPTS):
        webhooks.deliver_due(now=now, send=down)
        now += timedelta(hours=2)
        at(now)
    d = ex.get(f"/integrations/{out['id']}/deliveries", ex.admin).json()[0]
    assert d["status"] == "FAILED" and d["attempts"] == webhooks.MAX_ATTEMPTS
    assert "connection refused" in d["last_error"]


def test_no_webhook_without_url(lms):
    ex, cred, out, rc = lms
    ex.w.c.patch(f"/api/v1/org/integrations/{out['id']}", json={"clear_webhook": True}, headers=ex.h(ex.admin))
    aid = ex.enroll("plain@example.com")
    at(ex.window_start)
    ex.launch(aid)
    with transaction("system") as db:
        from sqlalchemy import func, select
        from examguard.models import WebhookDelivery
        assert db.scalar(select(func.count()).select_from(WebhookDelivery)) == 0
