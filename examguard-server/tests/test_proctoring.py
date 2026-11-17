"""Identity photos (PRD §12.5), emergency unlock (§22) and incident review (§27.8)."""
import base64
import os
from pathlib import Path

import pytest

from examguard import crypto
from examguard.config import get_settings
from examguard.services import proctoring

from .conftest import Exam1b, at
from .refclient import RefClient
from .test_protocol import link

JPEG = b"\xff\xd8\xff\xe0" + os.urandom(2000)


@pytest.fixture
def px(world, root_key, tmp_path):
    get_settings().storage_dir = str(tmp_path / "blobs")
    ex = Exam1b(world, identity_check="MANUAL")
    aid = ex.enroll("cand@example.com")
    rc = RefClient(world.c, crypto.public_raw(root_key))
    at(ex.checkin_open)
    t = link(ex)
    rc.launch(t)
    reg = rc.register(t).json()
    yield ex, aid, rc, reg, tmp_path
    get_settings().storage_dir = ".examguard/storage"


def photos(img=JPEG):
    b = base64.b64encode(img).decode()
    return {"content_type": "image/jpeg", "selfie": b, "id_card": b}


def test_identity_photos_encrypted_and_reviewable(px):
    ex, aid, rc, reg, tmp = px
    assert rc.call("POST", "/identity", {**photos(), "selfie": "!!!notbase64!!!"}).json()["error"]["code"] == "INVALID_IMAGE"
    assert rc.call("POST", "/identity", photos(b"GIF89a" + os.urandom(50))).json()["error"]["code"] == "INVALID_IMAGE"
    r = rc.call("POST", "/identity", photos())
    assert r.status_code == 200 and rc.open(r.json(), "state")["identity_status"] == "PENDING"
    files = list(Path(tmp, "blobs").rglob("*.bin"))
    assert len(files) == 2 and all(JPEG[:50] not in f.read_bytes() for f in files)   # encrypted at rest
    q = ex.get(f"/exams/{ex.id}/checkin-queue").json()
    assert q[0]["attempt_id"] == str(aid) and {p["kind"] for p in q[0]["photos"]} == {"SELFIE", "ID_CARD"}
    img = ex.w.c.get(q[0]["photos"][0]["url"], headers=ex.h())
    assert img.status_code == 200 and img.content == JPEG and img.headers["content-type"] == "image/jpeg"
    audit = [e["action"] for e in ex.w.c.get("/api/v1/org/audit-log?limit=3", headers=ex.h()).json()]
    assert "identity.photo_viewed" in audit
    # reject → resubmit as submission 2 → approve → start
    ex.post(f"/attempts/{aid}/identity/reject", {"reason": "foto buram"})
    assert rc.call("POST", "/identity", photos()).status_code == 200
    assert ex.get(f"/exams/{ex.id}/checkin-queue").json()[0]["submission"] == 2
    ex.post(f"/attempts/{aid}/identity/approve", {})
    at(ex.window_start)
    assert rc.open(rc.start().json(), "state")["status"] == "ACTIVE"


def test_photos_need_assignment(px):
    ex, aid, rc, reg, _ = px
    rc.call("POST", "/identity", photos())
    url = ex.get(f"/exams/{ex.id}/checkin-queue").json()[0]["photos"][0]["url"]
    _, inv = ex.add_staff("inv@acme.example.com")
    assert ex.w.c.get(url, headers=ex.h(ex.as_(inv))).status_code == 403


def test_challenge_response(px):
    ex, aid, rc, reg, _ = px
    secret = reg["attempt_unlock_secret"]
    assert len(crypto.unb64u(secret)) == 32
    r = ex.post(f"/attempts/{aid}/unlock-response", {"challenge": "abcd2345", "reason": "server mati"})
    assert r.json()["response"] == proctoring.challenge_response(secret, "ABCD2345")
    assert len(r.json()["response"]) == 8 and r.json()["response"].isdigit()
    assert ex.post(f"/attempts/{aid}/unlock-response", {"challenge": "abc", "reason": "x" * 5}).status_code == 422
    # a new device gets the same secret (one secret per attempt)
    second = RefClient(rc.http, rc.root_public)
    t = link(ex)
    second.launch(t)
    assert second.register(t).json()["attempt_unlock_secret"] == secret


def test_online_unlock_command(world, root_key):
    ex = Exam1b(world)
    aid = ex.enroll("cand@example.com")
    rc = RefClient(world.c, crypto.public_raw(root_key))
    at(ex.checkin_open)
    t = link(ex)
    rc.launch(t)
    rc.register(t)
    at(ex.window_start)
    rc.start()
    assert ex.post(f"/attempts/{aid}/emergency-unlock", {"reason": "komputer hang"}).status_code == 200
    body = rc.open(rc.call("GET", "/commands").json()["commands"][0], "command")
    assert body["type"] == "EMERGENCY_UNLOCK" and body["payload"] == {"reason": "komputer hang"}


def test_backup_codes_offline_verification_and_use(world, root_key):
    ex = Exam1b(world)
    aid = ex.enroll("cand@example.com")
    codes = ex.post(f"/exams/{ex.id}/backup-codes", {"count": 5}).json()["codes"]
    assert len(codes) == 5 and all(len(c) == 11 and c[5] == "-" for c in codes)
    rc = RefClient(world.c, crypto.public_raw(root_key))
    at(ex.checkin_open)
    t = link(ex)
    cfg = rc.launch(t)
    typed = codes[2].lower()                              # the client normalises what the invigilator types
    h = proctoring.code_hash(ex.id, typed)
    assert h in cfg["emergency_code_hashes"] and len(cfg["emergency_code_hashes"]) == 5
    rc.register(t)
    at(ex.window_start)
    rc.start()
    ev = rc.event("EMERGENCY_UNLOCK_USED", metadata={"method": "BACKUP_CODE", "code_hash": h})
    assert rc.call("POST", "/events", {"events": [ev]}).json()["incidents_created"] == 1
    assert ex.attempt(aid).status == "INTERRUPTED"
    assert h not in RefClient(world.c, rc.root_public).launch(link(ex))["emergency_code_hashes"]
    inc = ex.get(f"/exams/{ex.id}/incidents").json()
    assert inc[0]["type"] == "EMERGENCY_UNLOCK_USED" and inc[0]["severity"] == "HIGH"


def test_incident_list_detail_review(world, root_key):
    ex = Exam1b(world)
    ex.enroll("cand@example.com")
    rc = RefClient(world.c, crypto.public_raw(root_key))
    at(ex.checkin_open)
    t = link(ex)
    rc.launch(t)
    rc.register(t)
    at(ex.window_start)
    rc.start()
    rc.call("POST", "/events", {"events": [rc.event("FOCUS_LOST"), rc.event("MULTIPLE_PERSON", confidence=0.9),
                                           rc.event("NAVIGATION_BLOCKED")]})
    rows = ex.get(f"/exams/{ex.id}/incidents").json()
    assert [r["severity"] for r in rows] == ["HIGH", "MEDIUM"] and rows[0]["candidate_name"] == "Peserta"
    d = ex.get(f"/incidents/{rows[0]['id']}").json()
    assert d["events"][0]["type"] == "MULTIPLE_PERSON" and d["events"][0]["confidence"] == pytest.approx(0.9)
    assert ex.post(f"/incidents/{rows[0]['id']}/review", {"status": "DISMISSED"}, ex.admin).status_code == 403
    r = ex.post(f"/incidents/{rows[0]['id']}/review", {"status": "REVIEWED", "note": "kakak peserta lewat"})
    assert r.json()["status"] == "REVIEWED"
    assert [x["status"] for x in ex.get(f"/exams/{ex.id}/incidents").json()] == ["OPEN", "REVIEWED"]
    assert ex.get(f"/exams/{ex.id}/incidents?status=OPEN").json()[0]["type"] == "FOCUS_LOST"
    at(ex.checkin_open)
    other = Exam1b(world, org_slug="beta", code="B1")
    assert other.get(f"/incidents/{rows[0]['id']}").status_code == 404
