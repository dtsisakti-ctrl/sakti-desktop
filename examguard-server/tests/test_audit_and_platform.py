"""Hash-chained audit log and platform administration."""
from sqlalchemy import text

from examguard import audit
from examguard.db import transaction

from .conftest import owner_conn


def test_org_actions_are_audited_in_order(client, world):
    oid = world.org("aud", admin="admin@aud.example.com", exam_admin="exams@aud.example.com")
    tok = world.staff_login("exams@aud.example.com")
    world.published_exam(tok, oid, code="A1")
    entries = client.get("/api/v1/org/audit-log", headers=world.h(tok, oid)).json()
    actions = [e["action"] for e in reversed(entries)]
    assert actions == ["member.added", "exam.created", "exam.published"]
    assert [e["seq"] for e in entries] == [3, 2, 1]
    assert client.get("/api/v1/org/audit-log/verify", headers=world.h(tok, oid)).json()["ok"] is True


def test_tampering_is_detected(world):
    oid = world.org("tamper", admin="admin@t.example.com", exam_admin="exams@t.example.com")
    tok = world.staff_login("exams@t.example.com")
    world.published_exam(tok, oid, code="T1")
    chain = audit.chain_key(oid)
    with owner_conn() as c:  # simulate a DBA editing history directly
        c.execute("UPDATE audit_log SET data = '{\"code\": \"FORGED\"}' WHERE chain_key = %s AND seq = 2", (chain,))
    with transaction("system") as db:
        r = audit.verify(db, chain)
    assert r == {"chain": chain, "ok": False, "checked": 2, "first_bad_seq": 2, "reason": "hash mismatch"}

    with owner_conn() as c:
        c.execute("DELETE FROM audit_log WHERE chain_key = %s AND seq = 2", (chain,))
    with transaction("system") as db:
        assert audit.verify(db, chain)["reason"] == "sequence gap"


def test_platform_org_lifecycle(client, world):
    root = world.platform_admin()
    r = client.post("/api/v1/platform/organizations",
                    json={"slug": "pt-baru", "name": "PT Baru", "admin_email": "boss@baru.example.com",
                          "admin_full_name": "Boss", "admin_password": "boss-password-1"},
                    headers=world.h(root))
    assert r.status_code == 201 and r.json()["can_publish_public"] is False
    oid = r.json()["id"]
    r = client.post("/api/v1/platform/organizations", json={"slug": "pt-baru", "name": "dup"},
                    headers=world.h(root))
    assert r.json()["error"]["code"] == "SLUG_TAKEN"
    r = client.patch(f"/api/v1/platform/organizations/{oid}", json={"can_publish_public": True},
                     headers=world.h(root))
    assert r.json()["can_publish_public"] is True
    boss = client.post("/api/v1/staff/auth/login", json={"email": "boss@baru.example.com", "password": "boss-password-1"})
    members = client.get("/api/v1/org/members", headers=world.h(boss.json()["token"], oid)).json()
    assert [(m["email"], m["role"]) for m in members] == [("boss@baru.example.com", "ORG_ADMIN")]
    assert client.get("/api/v1/platform/audit-log/verify", headers=world.h(root)).json()["ok"] is True


def test_last_org_admin_cannot_be_removed(client, world):
    oid = world.org("keep", admin="only@keep.example.com")
    tok = world.staff_login("only@keep.example.com")
    m = client.get("/api/v1/org/members", headers=world.h(tok, oid)).json()[0]
    r = client.delete(f"/api/v1/org/members/{m['membership_id']}", headers=world.h(tok, oid))
    assert r.status_code == 409 and r.json()["error"]["code"] == "LAST_ORG_ADMIN"
    r = client.post("/api/v1/org/members", json={"email": "second@keep.example.com", "role": "ORG_ADMIN",
                                                 "full_name": "Second", "initial_password": "second-pass-1"},
                    headers=world.h(tok, oid))
    assert r.status_code == 201
    assert client.delete(f"/api/v1/org/members/{m['membership_id']}", headers=world.h(tok, oid)).status_code == 204


def test_openapi_is_generated(client):
    spec = client.get("/openapi.json").json()
    assert "/api/v1/candidate/exams/{exam_id}/register" in spec["paths"]
