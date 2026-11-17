"""Disconnect detection (PRD v0.3.5 §17.6, Q25-Q26): one moment for OFFLINE and INTERRUPTED.

- The client's WebSocket closes (crash, app closed, Ctrl+C): INTERRUPTED and OFFLINE at once.
- Silent loss (cable pulled, no TCP close): both after the exam's interruption threshold (default 30 s).
- Any signed request from the active device is proof of life and resumes the attempt.
- A gap shorter than 10 s does not open an UNMONITORED_INTERRUPTION incident.
"""
from datetime import timedelta

import time

import pytest
from sqlalchemy import select

from examguard import crypto, scheduler, settings_service
from examguard.config import get_settings
from examguard.db import transaction
from examguard.models import Incident, StateTransition

from .conftest import Exam1b, at
from .refclient import RefClient
from .test_protocol import started


@pytest.fixture
def pc(world, root_key):
    ex = Exam1b(world)
    aid = ex.enroll("cand@example.com")
    get_settings().ws_poll_seconds = 0.05
    yield ex, aid, RefClient(world.c, crypto.public_raw(root_key))
    get_settings().ws_poll_seconds = 1.0


def _incidents(aid):
    with transaction("system") as db:
        return list(db.scalars(select(Incident).where(Incident.attempt_id == aid,
                                                      Incident.type == "UNMONITORED_INTERRUPTION")))


def _last_transition(aid):
    with transaction("system") as db:
        return db.scalar(select(StateTransition).where(StateTransition.attempt_id == aid)
                         .order_by(StateTransition.state_version.desc()).limit(1))


def _closed(ex, aid, ws, *, expect="INTERRUPTED") -> dict:
    """The client closes its socket; the server reacts within a moment (well under the 2 s poll)."""
    ws.close()
    deadline = time.monotonic() + 3
    while True:
        d = ex.detail(aid)
        if d["connection_status"] == "OFFLINE" and d["status"] == expect or time.monotonic() > deadline:
            return d
        time.sleep(0.02)


def _connect_and_close(ex, aid, rc, *, expect="INTERRUPTED") -> dict:
    with rc.http.websocket_connect(rc.ws_url()) as ws:
        while ws.receive_json()["type"] != "STATE":
            pass
        ws.send_json(rc.ws_heartbeat())
        while ws.receive_json()["type"] != "HEARTBEAT_ACK":
            pass
        return _closed(ex, aid, ws, expect=expect)


def test_platform_default_threshold_is_30_seconds(world):
    with transaction("system") as db:
        assert settings_service.platform(db)["defaults"]["interruption_threshold_seconds"] == 30


def test_closed_connection_interrupts_at_once(pc):
    ex, aid, rc = pc
    started(ex, rc)
    d = _connect_and_close(ex, aid, rc)
    assert d["status"] == "INTERRUPTED" and d["connection_status"] == "OFFLINE"
    t = _last_transition(aid)
    assert t.trigger == "INTERRUPT" and t.data["detected"] == "connection_closed"
    row = next(r for r in ex.get(f"/exams/{ex.id}/attempts").json()["attempts"] if r["attempt_id"] == str(aid))
    assert row["status"] == "INTERRUPTED" and row["connection_status"] == "OFFLINE"


def test_short_reconnect_resumes_without_incident(pc):
    ex, aid, rc = pc
    started(ex, rc)
    _connect_and_close(ex, aid, rc)
    at(ex.window_start + timedelta(seconds=5))
    assert rc.state()["status"] == "ACTIVE"          # the signed sync before reconnecting is proof of life
    t = _last_transition(aid)
    assert t.trigger == "AUTO_RESUME" and t.data["gap_seconds"] == 5
    assert _incidents(aid) == []
    assert ex.detail(aid)["connection_status"] == "ONLINE"


def test_longer_gap_opens_incident(pc):
    ex, aid, rc = pc
    started(ex, rc)
    _connect_and_close(ex, aid, rc)
    at(ex.window_start + timedelta(seconds=45))
    assert rc.heartbeat(recovery_cause="CLIENT_CRASH").json()["status"] == "ACTIVE"
    [inc] = _incidents(aid)
    assert inc.data["gap_seconds"] == 45 and inc.data["cause"] == "CLIENT_CRASH"


def test_finish_after_closed_connection(pc):
    ex, aid, rc = pc
    started(ex, rc)
    _connect_and_close(ex, aid, rc)
    assert rc.call("POST", "/finish").status_code == 200
    assert rc.state()["status"] == "SUBMITTED"


def test_old_socket_closing_after_newer_heartbeat_changes_nothing(pc):
    ex, aid, rc = pc
    started(ex, rc)
    with rc.http.websocket_connect(rc.ws_url()) as old:
        old.receive_json()
        with rc.http.websocket_connect(rc.ws_url()) as new:
            new.receive_json()
            new.send_json(rc.ws_heartbeat())
            assert new.receive_json()["type"] == "HEARTBEAT_ACK"
            old.close()
            time.sleep(0.3)
            assert ex.detail(aid)["status"] == "ACTIVE"   # the client is heartbeating on the newer socket
            new.send_json(rc.ws_heartbeat())
            while new.receive_json()["type"] != "HEARTBEAT_ACK":
                pass
            assert _closed(ex, aid, new)["status"] == "INTERRUPTED"   # the last connection closed


def test_paused_attempt_shows_offline_but_stays_paused(pc):
    ex, aid, rc = pc
    started(ex, rc)
    ex.post(f"/attempts/{aid}/pause", {"reason": "cek meja"})
    d = _connect_and_close(ex, aid, rc, expect="PAUSED")
    assert d["status"] == "PAUSED" and d["connection_status"] == "OFFLINE"
    rc.state()
    assert ex.detail(aid)["connection_status"] == "ONLINE"


def test_silent_loss_offline_and_interrupted_together(pc):
    ex, aid, rc = pc
    started(ex, rc)
    rc.heartbeat()
    at(ex.window_start + timedelta(seconds=29))
    scheduler.tick()
    d = ex.detail(aid)
    assert d["status"] == "ACTIVE" and d["connection_status"] == "ONLINE"
    at(ex.window_start + timedelta(seconds=31))
    d = ex.detail(aid)
    assert d["connection_status"] == "OFFLINE"
    scheduler.tick()
    assert ex.detail(aid)["status"] == "INTERRUPTED"
    dash = ex.get("/dashboard").json()
    assert dash["totals"]["online"] == 0 and dash["totals"]["interrupted"] == 1


def test_offline_follows_exam_threshold(pc):
    ex, aid, rc = pc
    r = ex.w.c.patch(f"/api/v1/org/exams/{ex.id}/settings", headers=ex.h(),
                     json={"overrides": {"interruption_threshold_seconds": 120}})
    assert r.status_code == 200, r.text
    started(ex, rc)
    at(ex.window_start + timedelta(seconds=90))
    assert ex.detail(aid)["connection_status"] == "ONLINE"
    at(ex.window_start + timedelta(seconds=121))
    assert ex.detail(aid)["connection_status"] == "OFFLINE"

