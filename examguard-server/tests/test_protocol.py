"""Client protocol (PRD §12, §16.2, §17, §18, §19) through the HTTP API, using the reference client."""
from datetime import timedelta

import pytest

from examguard import crypto, keys
from examguard.config import get_settings
from examguard.db import transaction

from .conftest import PASSWORD, Exam1b, at
from .refclient import RefClient


@pytest.fixture
def pc(world, root_key):
    """A published exam, one enrolled candidate and a reference client that trusts the root key."""
    ex = Exam1b(world)
    aid = ex.enroll("cand@example.com")
    return ex, aid, RefClient(world.c, crypto.public_raw(root_key)), root_key


def link(ex, email="cand@example.com") -> str:
    c = ex.w.c
    tok = c.post("/api/v1/candidate/auth/login", json={"email": email, "password": PASSWORD}).json()["token"]
    enr = c.get("/api/v1/candidate/enrollments", headers={"Authorization": f"Bearer {tok}"}).json()[0]["id"]
    r = c.post(f"/api/v1/candidate/enrollments/{enr}/launch", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200, r.text
    assert r.json()["launch_url"].startswith("examguard://launch?t=")
    return r.json()["launch_token"]


def started(ex, rc) -> None:
    at(ex.checkin_open)
    t = link(ex)
    rc.launch(t)
    assert rc.register(t).status_code == 201
    at(ex.window_start)
    assert rc.start().status_code == 200


# ------------------------------------------------------------------ keys
def test_key_set_is_root_signed_and_per_use(pc, world):
    ex, aid, rc, root = pc
    ks = rc.key_set()
    assert {k["use"] for k in ks.values()} == {"command", "state", "config", "token"}
    assert all(kid.endswith("." + k["use"]) for kid, k in ks.items())
    env = world.c.get("/.well-known/examguard-keys.json").json()
    assert env["kid"] == keys.root_kid(crypto.public_raw(root))
    forged = {**env, "body": env["body"].replace('"active"', '"revoked"', 1)}
    assert crypto.open_envelope(forged, crypto.public_raw(root)) is None
    assert crypto.open_envelope(env, crypto.public_raw(crypto.new_private_key())) is None


def test_revoked_key_is_published_as_revoked(pc):
    ex, aid, rc, root = pc
    with transaction("system") as db:
        base = next(iter(rc.key_set())).rsplit(".", 1)[0]
        keys.set_status(db, base, "REVOKED")
        keys.publish(db, root)
        keys.create_server_key(db)
        keys.publish(db, root)
    ks = rc.key_set()
    assert {k["status"] for kid, k in ks.items() if kid.startswith(base)} == {"revoked"}
    at(ex.checkin_open)
    config_env = rc.http.post("/client/v1/launch", json={"launch_token": link(ex)}).json()["config"]
    assert not config_env["kid"].startswith(base)          # signed with the new key
    assert rc.open(config_env, "config")["attempt_id"] == str(aid)


# ------------------------------------------------------------------ launch & registration
def test_launch_config_and_single_use_token(pc):
    ex, aid, rc, _ = pc
    at(ex.checkin_open)
    t = link(ex)
    cfg = rc.launch(t)
    assert cfg["exam_url"] == "https://exam.example.edu/run" and cfg["attempt_id"] == str(aid)
    assert cfg["config_hash"].startswith("sha256:") and cfg["server_endpoints"]["ws"].startswith("ws")
    assert rc.launch(t)["attempt_id"] == str(aid)          # launch does not consume the token
    r = rc.register(t)
    assert r.status_code == 201 and r.json()["device_status"] == "ACTIVE"
    st = rc.open(r.json()["state"], "state")
    assert st["status"] == "NOT_STARTED" and st["device_session_id"] == rc.sid
    again = RefClient(rc.http, rc.root_public).register(t)
    assert again.status_code == 409 and again.json()["error"]["code"] == "LAUNCH_TOKEN_USED"


def test_launch_token_errors(pc):
    ex, aid, rc, _ = pc
    at(ex.checkin_open)
    t = link(ex)
    assert rc.register(t, version="0.0.9").json()["error"]["code"] == "CLIENT_TOO_OLD"
    bad = rc.http.post("/client/v1/device-sessions", json={"launch_token": t, "public_key": "A" * 40,
                                                            "client_version": "0.2.0"})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "INVALID_PUBLIC_KEY"
    assert rc.http.post("/client/v1/launch", json={"launch_token": "x" * 43}).json()["error"]["code"] == \
        "INVALID_LAUNCH_TOKEN"
    at(ex.checkin_open + timedelta(minutes=16))
    assert rc.http.post("/client/v1/launch", json={"launch_token": t}).json()["error"]["code"] == \
        "LAUNCH_TOKEN_EXPIRED"


def test_launch_link_only_for_own_live_enrollment(pc, world):
    ex, aid, rc, _ = pc
    ex.enroll("other@example.com")
    c = world.c
    at(ex.checkin_open)
    tok = c.post("/api/v1/candidate/auth/login", json={"email": "other@example.com", "password": PASSWORD}).json()["token"]
    link(ex)                                                  # the first candidate can get a link
    enr_of_first = ex.detail(aid)["enrollment_id"]
    r = c.post(f"/api/v1/candidate/enrollments/{enr_of_first}/launch", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 404


# ------------------------------------------------------------------ EG-Sig
def test_eg_sig_rejections(pc):
    ex, aid, rc, _ = pc
    at(ex.checkin_open)
    t = link(ex)
    rc.launch(t)
    rc.register(t)
    assert rc.call("GET", "/state").status_code == 200
    path = f"/client/v1/attempts/{aid}/state"
    assert rc.http.get(path).json()["error"]["code"] == "UNAUTHORIZED"
    old = int((ex.checkin_open - timedelta(seconds=61)).timestamp() * 1000)
    assert rc.call("GET", "/state", ts=old).json()["error"]["code"] == "CLOCK_SKEW"
    other = RefClient(rc.http, rc.root_public)
    other.sid, other.attempt_id = rc.sid, rc.attempt_id       # right sid, wrong key
    assert other.call("GET", "/state").json()["error"]["code"] == "INVALID_SIGNATURE"
    # signature over one body, a different body sent
    hdr = rc.auth("POST", f"/client/v1/attempts/{aid}/heartbeat", b'{"seq": 1}')
    r = rc.http.post(f"/client/v1/attempts/{aid}/heartbeat", content=b'{"seq": 999}',
                     headers={"Authorization": hdr, "Content-Type": "application/json"})
    assert r.json()["error"]["code"] == "INVALID_SIGNATURE"
    aid2 = ex.enroll("second@example.com")
    r = rc.http.get(f"/client/v1/attempts/{aid2}/state",
                    headers={"Authorization": rc.auth("GET", f"/client/v1/attempts/{aid2}/state")})
    assert r.status_code == 403


# ------------------------------------------------------------------ full flow
def test_start_heartbeat_finish(pc):
    ex, aid, rc, _ = pc
    started(ex, rc)
    st = rc.state()
    assert st["status"] == "ACTIVE" and st["state_version"] == 1 and st["resume_allowed"] is True
    assert st["deadline"] == (ex.window_start + timedelta(minutes=90)).isoformat().replace("+00:00", "Z")
    hb = rc.heartbeat(last_state_version=0, health={"lockdown_ok": True}).json()
    assert hb["status"] == "ACTIVE" and hb["sync_required"] is True
    assert rc.call("POST", "/finish").status_code == 200
    assert rc.state()["status"] == "SUBMITTED"


def test_signed_commands_http_fallback(pc):
    ex, aid, rc, _ = pc
    started(ex, rc)
    ex.post(f"/attempts/{aid}/pause", {"reason": "cek meja", "timer_mode": "PAUSE_TIMER"})
    envs = rc.call("GET", "/commands").json()["commands"]
    assert len(envs) == 1
    body = rc.open(envs[0], "command")
    assert body["type"] == "PAUSE_EXAM" and body["state_version"] == 2
    assert body["attempt_id"] == str(aid) and body["device_session_id"] == rc.sid
    assert body["payload"] == {"reason": "cek meja", "timer_mode": "PAUSE_TIMER"} and len(body["nonce"]) >= 20
    assert rc.call("GET", "/commands").json()["commands"] == envs   # retransmission is byte-identical
    r = rc.call("POST", f"/commands/{body['command_id']}/ack", {"result": "APPLIED"})
    assert r.json()["delivery_status"] == "APPLIED"
    assert rc.call("GET", "/commands").json()["commands"] == []
    assert ex.detail(aid)["commands"][0]["delivery_status"] == "APPLIED"


def test_pending_warning_in_state(pc):
    ex, aid, rc, _ = pc
    started(ex, rc)
    ex.post(f"/attempts/{aid}/warning", {"message": "Harap menghadap kamera"})
    assert rc.state()["pending_warning"]["message"] == "Harap menghadap kamera"


# ------------------------------------------------------------------ events & incidents
def test_events_idempotent_and_incidents(pc, world):
    ex, aid, rc, _ = pc
    started(ex, rc)
    t0 = ex.window_start + timedelta(minutes=2)
    batch = [rc.event("MULTIPLE_PERSON", "OPEN", started_at=t0.isoformat(), confidence=0.94),
             rc.event("NAVIGATION_BLOCKED", metadata={"url": "https://evil.example"}),
             rc.event("SOMETHING_NEW"),
             rc.event("MULTIPLE_PERSON", "CLOSE", started_at=t0.isoformat(),
                      ended_at=(t0 + timedelta(seconds=40)).isoformat())]
    r = rc.call("POST", "/events", {"events": batch}).json()
    assert r == {"accepted": 4, "duplicates": 0, "incidents_created": 1}
    assert rc.call("POST", "/events", {"events": batch}).json()["duplicates"] == 4
    from sqlalchemy import select
    from examguard.models import Event, Incident
    with transaction("system") as db:
        incs = list(db.scalars(select(Incident).where(Incident.attempt_id == aid)))
        sev = {e.type: e.severity for e in db.scalars(select(Event).where(Event.attempt_id == aid))}
    assert len(incs) == 1 and incs[0].severity == "HIGH" and incs[0].event_count == 2
    assert incs[0].ended_at == t0 + timedelta(seconds=40)
    assert sev == {"MULTIPLE_PERSON": "HIGH", "NAVIGATION_BLOCKED": "LOW", "SOMETHING_NEW": "INFO"}


def test_revoked_device_can_still_flush_events(pc):
    ex, aid, rc, _ = pc
    started(ex, rc)
    second = RefClient(rc.http, rc.root_public)
    t = link(ex)
    second.launch(t)
    assert second.register(t).json()["device_status"] == "PENDING_APPROVAL"
    ex.post(f"/attempts/{aid}/reentry/allow", {"reason": "laptop rusak"})
    assert rc.call("GET", "/state").json()["error"]["code"] == "DEVICE_SESSION_REVOKED"
    r = rc.call("POST", "/events", {"events": [rc.event("FOCUS_LOST")]})
    assert r.status_code == 200 and r.json()["accepted"] == 1
    assert second.state()["status"] == "ACTIVE"


def test_unmonitored_interruption_incident(pc):
    from examguard import scheduler
    ex, aid, rc, _ = pc
    started(ex, rc)
    at(ex.window_start + timedelta(seconds=90))
    scheduler.tick()
    at(ex.window_start + timedelta(minutes=3))
    assert rc.heartbeat(recovery_cause="CLIENT_CRASH").json()["status"] == "ACTIVE"
    from sqlalchemy import select
    from examguard.models import Incident
    with transaction("system") as db:
        inc = db.scalar(select(Incident).where(Incident.attempt_id == aid))
    assert inc.type == "UNMONITORED_INTERRUPTION" and inc.data["cause"] == "CLIENT_CRASH"
    assert inc.data["gap_seconds"] == 180


# ------------------------------------------------------------------ attestation
def test_attestation_token(pc):
    ex, aid, rc, _ = pc
    at(ex.checkin_open)
    t = link(ex)
    rc.launch(t)
    rc.register(t)
    assert rc.call("POST", "/attestation").json()["error"]["code"] == "ATTESTATION_UNAVAILABLE"
    at(ex.window_start)
    rc.start()
    tok = rc.call("POST", "/attestation").json()["token"]
    ks = rc.key_set()
    claims = crypto.jwt_decode(tok, lambda kid: ks[kid]["x"] if kid in ks and ks[kid]["use"] == "token" else None)
    assert claims["aud"] == "https://exam.example.edu" and claims["attempt_status"] == "ACTIVE"
    assert claims["attempt_id"] == str(aid) and claims["device_session_id"] == rc.sid
    assert claims["exp"] - claims["iat"] == 300
    assert crypto.jwt_decode(tok[:-4] + "AAAA", lambda kid: ks[kid]["x"]) is None


# ------------------------------------------------------------------ websocket
def test_websocket_push_heartbeat_ack(pc):
    ex, aid, rc, _ = pc
    get_settings().ws_poll_seconds = 0.05
    started(ex, rc)
    with rc.http.websocket_connect(rc.ws_url()) as ws:
        first = ws.receive_json()
        assert first["type"] == "STATE" and rc.open(first["envelope"], "state")["status"] == "ACTIVE"
        ws.send_json(rc.ws_heartbeat(last_state_version=1))
        hb = ws.receive_json()
        assert hb["type"] == "HEARTBEAT_ACK" and hb["sync_required"] is False
        ex.post(f"/attempts/{aid}/add-time", {"minutes": 10, "reason": "kompensasi"})
        msgs = [ws.receive_json(), ws.receive_json()]
        cmd = next(m for m in msgs if m["type"] == "COMMAND")
        body = rc.open(cmd["envelope"], "command")
        assert body["type"] == "UPDATE_DEADLINE"
        assert any(m["type"] == "STATE" and rc.open(m["envelope"], "state")["state_version"] == 2 for m in msgs)
        ws.send_json({"type": "ACK", "command_id": body["command_id"], "result": "APPLIED"})
        assert ws.receive_json() == {"type": "ACK_OK", "command_id": body["command_id"], "delivery_status": "APPLIED"}
        forged = rc.ws_heartbeat()
        forged["sig"] = crypto.sign(crypto.new_private_key(), forged["body"].encode())
        ws.send_json(forged)
        assert ws.receive_json() == {"type": "ERROR", "code": "INVALID_SIGNATURE"}
        ex.post(f"/attempts/{aid}/terminate", {"reason": "joki", "reason_category": "DISCIPLINARY"})
        seen = [ws.receive_json(), ws.receive_json()]
        states = [rc.open(m["envelope"], "state")["status"] for m in seen if m["type"] == "STATE"]
        assert states == ["TERMINATED"]
    get_settings().ws_poll_seconds = 1.0


def test_websocket_rejects_bad_signature_and_revoked(pc):
    from starlette.websockets import WebSocketDisconnect
    ex, aid, rc, _ = pc
    get_settings().ws_poll_seconds = 0.05
    started(ex, rc)
    good = rc.ws_url()
    with pytest.raises(WebSocketDisconnect) as e:
        with rc.http.websocket_connect(good.replace("sig=", "sig=AA")):
            pass
    assert e.value.code == 4401
    with rc.http.websocket_connect(good) as ws:
        ws.receive_json()
        second = RefClient(rc.http, rc.root_public)
        t = link(ex)
        second.launch(t)
        second.register(t)
        ex.post(f"/attempts/{aid}/reentry/allow", {"reason": "laptop rusak"})
        msgs = []
        while True:
            m = ws.receive_json()
            msgs.append(m["type"])
            if m["type"] == "REVOKED":
                break
        assert msgs[-1] == "REVOKED"
    get_settings().ws_poll_seconds = 1.0


def test_error_details_with_datetimes_are_json(pc):
    """Regression: START_NOT_YET_ALLOWED carries window_start (a datetime) and must be a 409, not a 500."""
    ex, aid, rc, _ = pc
    at(ex.checkin_open)
    t = link(ex)
    rc.launch(t)
    rc.register(t)
    r = rc.start()
    assert r.status_code == 409 and r.json()["error"]["code"] == "START_NOT_YET_ALLOWED"
    assert r.json()["error"]["details"]["window_start"].startswith(ex.window_start.date().isoformat())
