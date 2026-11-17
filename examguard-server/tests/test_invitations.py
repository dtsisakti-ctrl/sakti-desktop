"""Organization invitations for PRIVATE exams."""
from datetime import timedelta

import pytest

from examguard import clock

from .conftest import NOW


@pytest.fixture
def company(world):
    oid = world.org("company", admin="hr@company.example.com", exam_admin="exams@company.example.com")
    tok = world.staff_login("exams@company.example.com")
    exam = world.published_exam(tok, oid, code="REKRUT", visibility="PRIVATE", capacity=10)
    return oid, tok, exam


def invite(client, world, tok, oid, exam_id, emails, **kw):
    return client.post(f"/api/v1/org/exams/{exam_id}/invitations", json={"emails": emails, **kw},
                       headers=world.h(tok, oid))


def test_invite_and_accept(client, world, company):
    oid, tok, exam = company
    r = invite(client, world, tok, oid, exam["id"], ["Andi@Mail.example.com", "andi@mail.example.com", "sari@mail.example.com"])
    assert r.status_code == 201
    assert len(r.json()["created"]) == 2 and r.json()["skipped"][0]["reason"] == "duplicate in request"
    again = invite(client, world, tok, oid, exam["id"], ["sari@mail.example.com"]).json()
    assert again["skipped"] == [{"email": "sari@mail.example.com", "reason": "already invited"}]

    cand = world.candidate("andi@mail.example.com")
    token = world.outbox_token("Andi@Mail.example.com", "invitation")
    r = client.post("/api/v1/candidate/invitations/accept", json={"token": token}, headers=world.h(cand))
    assert r.status_code == 201
    mine = client.get("/api/v1/candidate/enrollments", headers=world.h(cand)).json()
    assert mine[0]["exam"]["code"] == "REKRUT" and mine[0]["source"] == "INVITED"
    # token cannot be reused
    r = client.post("/api/v1/candidate/invitations/accept", json={"token": token}, headers=world.h(cand))
    assert r.json()["error"]["code"] == "INVALID_TOKEN"
    # invited candidates cannot cancel on their own
    r = client.post(f"/api/v1/candidate/enrollments/{mine[0]['id']}/cancel", headers=world.h(cand))
    assert r.status_code == 403


def test_invitation_bound_to_email(client, world, company):
    oid, tok, exam = company
    invite(client, world, tok, oid, exam["id"], ["target@mail.example.com"])
    token = world.outbox_token("target@mail.example.com", "invitation")
    intruder = world.candidate("intruder@mail.example.com")
    r = client.post("/api/v1/candidate/invitations/accept", json={"token": token}, headers=world.h(intruder))
    assert r.status_code == 403 and r.json()["error"]["code"] == "INVITATION_EMAIL_MISMATCH"


def test_revoked_and_expired_invitations(client, world, company):
    oid, tok, exam = company
    created = invite(client, world, tok, oid, exam["id"], ["rev@mail.example.com"], expires_in_days=1).json()["created"]
    rev_token = world.outbox_token("rev@mail.example.com", "invitation")
    client.post(f"/api/v1/org/invitations/{created[0]['id']}/revoke", headers=world.h(tok, oid))
    cand = world.candidate("rev@mail.example.com")
    r = client.post("/api/v1/candidate/invitations/accept", json={"token": rev_token}, headers=world.h(cand))
    assert r.json()["error"]["code"] == "INVALID_TOKEN"

    invite(client, world, tok, oid, exam["id"], ["rev@mail.example.com"], expires_in_days=1)
    new_token = world.outbox_token("rev@mail.example.com", "invitation")
    clock.set_now(NOW + timedelta(days=2))
    cand = world.candidate_login("rev@mail.example.com")
    r = client.post("/api/v1/candidate/invitations/accept", json={"token": new_token}, headers=world.h(cand))
    assert r.json()["error"]["code"] == "INVALID_TOKEN"


def test_org_manages_enrollment(client, world, company):
    oid, tok, exam = company
    invite(client, world, tok, oid, exam["id"], ["emp@mail.example.com"])
    cand = world.candidate("emp@mail.example.com", name="Karyawan")
    client.post("/api/v1/candidate/invitations/accept",
                json={"token": world.outbox_token("emp@mail.example.com", "invitation")}, headers=world.h(cand))
    rows = client.get(f"/api/v1/org/exams/{exam['id']}/enrollments", headers=world.h(tok, oid)).json()
    assert rows[0]["candidate_name"] == "Karyawan"
    enr = rows[0]["id"]
    r = client.patch(f"/api/v1/org/enrollments/{enr}", json={"time_accommodation_minutes": 15},
                     headers=world.h(tok, oid))
    assert r.json()["time_accommodation_minutes"] == 15
    r = client.post(f"/api/v1/org/enrollments/{enr}/cancel", json={"reason": "withdrawn by HR"},
                    headers=world.h(tok, oid))
    assert r.json()["status"] == "CANCELLED"
    # once enrolled, already-enrolled emails are skipped on re-invite only while CONFIRMED
    assert invite(client, world, tok, oid, exam["id"], ["emp@mail.example.com"]).json()["created"]


def test_accept_requires_published_exam(client, world):
    oid = world.org("draft-co", admin="hr@draft.example.com", exam_admin="ex@draft.example.com")
    tok = world.staff_login("ex@draft.example.com")
    eid = client.post("/api/v1/org/exams", json=world.exam_body(code="D1"), headers=world.h(tok, oid)).json()["id"]
    invite(client, world, tok, oid, eid, ["early@mail.example.com"])
    cand = world.candidate("early@mail.example.com")
    r = client.post("/api/v1/candidate/invitations/accept",
                    json={"token": world.outbox_token("early@mail.example.com", "invitation")}, headers=world.h(cand))
    assert r.status_code == 409 and r.json()["error"]["code"] == "EXAM_NOT_OPEN"
