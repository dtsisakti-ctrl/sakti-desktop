"""Public catalog, self-registration, capacity, cancel and move (PRD §8.3–8.4)."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from sqlalchemy import select

from examguard import clock
from examguard.db import transaction
from examguard.errors import AppError
from examguard.models import Candidate, Exam
from examguard.services import registration

from .conftest import NOW


@pytest.fixture
def pub(world):
    oid = world.org("public-test", public=True, admin="a@pub.example.com", exam_admin="e@pub.example.com")
    return oid, world.staff_login("e@pub.example.com")


def reg(client, world, tok, exam_id, **body):
    return client.post(f"/api/v1/candidate/exams/{exam_id}/register", json=body, headers=world.h(tok))


def test_catalog_shows_only_public_ready_exams(client, world, pub):
    oid, tok = pub
    world.published_exam(tok, oid, code="EPT-A", visibility="PUBLIC", series="EPT", capacity=2)
    world.published_exam(tok, oid, code="PRIV", visibility="PRIVATE")
    client.post("/api/v1/org/exams", json=world.exam_body(code="DRAFT", visibility="PUBLIC"),
                headers=world.h(tok, oid))
    cat = client.get("/api/v1/public/exams").json()
    assert [e["code"] for e in cat] == ["EPT-A"]
    assert cat[0]["registration_status"] == "OPEN" and cat[0]["seats_left"] == 2
    assert cat[0]["org_name"] == "PUBLIC-TEST"


def test_register_happy_path(client, world, pub):
    oid, tok = pub
    exam = world.published_exam(tok, oid, code="E1", visibility="PUBLIC")
    cand = world.candidate("r@mail.example.com")
    r = reg(client, world, cand, exam["id"])
    assert r.status_code == 201
    mine = client.get("/api/v1/candidate/enrollments", headers=world.h(cand)).json()
    assert mine[0]["attempt_status"] == "NOT_STARTED" and mine[0]["exam"]["code"] == "E1"
    assert "registration_confirmed" in world.outbox("r@mail.example.com")
    assert reg(client, world, cand, exam["id"]).json()["error"]["code"] == "ALREADY_REGISTERED"
    staff_view = client.get(f"/api/v1/org/exams/{exam['id']}/enrollments", headers=world.h(tok, oid)).json()
    assert staff_view[0]["candidate_email"] == "r@mail.example.com"


def test_register_rules(client, world, pub):
    oid, tok = pub
    exam = world.published_exam(tok, oid, code="E2", visibility="PUBLIC", access_code="open-sesame")
    priv = world.published_exam(tok, oid, code="E3", visibility="PRIVATE")
    unverified = world.candidate("u@mail.example.com", verify=False)
    assert reg(client, world, unverified, exam["id"]).json()["error"]["code"] == "EMAIL_NOT_VERIFIED"
    cand = world.candidate("v@mail.example.com")
    assert reg(client, world, cand, exam["id"]).json()["error"]["code"] == "INVALID_ACCESS_CODE"
    assert reg(client, world, cand, exam["id"], access_code="wrong-code").status_code == 403
    assert reg(client, world, cand, exam["id"], access_code="open-sesame").status_code == 201
    assert reg(client, world, cand, priv["id"]).status_code == 404  # private exams are invisible


def test_registration_window(client, world, pub):
    oid, tok = pub
    exam = world.published_exam(tok, oid, code="W1", visibility="PUBLIC",
                                 registration_open=(NOW + timedelta(days=1)).isoformat())
    cand = world.candidate("w@mail.example.com")
    r = reg(client, world, cand, exam["id"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "REGISTRATION_CLOSED"
    clock.set_now(NOW + timedelta(days=2))
    cand = world.candidate_login("w@mail.example.com")  # sessions last 24h
    assert reg(client, world, cand, exam["id"]).status_code == 201
    clock.set_now(NOW + timedelta(days=6, hours=1))  # after registration_close (start - 1 day)
    other = world.candidate("w2@mail.example.com")
    assert reg(client, world, other, exam["id"]).json()["error"]["code"] == "REGISTRATION_CLOSED"


def test_capacity_and_cancel_releases_seat(client, world, pub):
    oid, tok = pub
    exam = world.published_exam(tok, oid, code="CAP", visibility="PUBLIC", capacity=1)
    a, b = world.candidate("a@mail.example.com"), world.candidate("b@mail.example.com")
    enr = reg(client, world, a, exam["id"]).json()["enrollment_id"]
    assert reg(client, world, b, exam["id"]).json()["error"]["code"] == "EXAM_FULL"
    assert client.post(f"/api/v1/candidate/enrollments/{enr}/cancel", headers=world.h(a)).status_code == 200
    assert reg(client, world, b, exam["id"]).status_code == 201
    # cancelling again is rejected, and the cancelled candidate can re-register only if a seat frees up
    r = client.post(f"/api/v1/candidate/enrollments/{enr}/cancel", headers=world.h(a))
    assert r.json()["error"]["code"] == "ENROLLMENT_NOT_ACTIVE"


def test_cancel_after_registration_close_is_rejected(client, world, pub):
    oid, tok = pub
    exam = world.published_exam(tok, oid, code="LATE", visibility="PUBLIC")
    cand = world.candidate("l@mail.example.com")
    enr = reg(client, world, cand, exam["id"]).json()["enrollment_id"]
    clock.set_now(NOW + timedelta(days=6, hours=12))
    cand = world.candidate_login("l@mail.example.com")
    r = client.post(f"/api/v1/candidate/enrollments/{enr}/cancel", headers=world.h(cand))
    assert r.status_code == 409 and r.json()["error"]["code"] == "REGISTRATION_CLOSED"


def test_move_within_series_only(client, world, pub):
    oid, tok = pub
    a = world.published_exam(tok, oid, code="EPT-A", visibility="PUBLIC", series="EPT", capacity=5)
    b = world.published_exam(tok, oid, code="EPT-B", visibility="PUBLIC", series="EPT",
                             start_in=timedelta(days=14), capacity=5)
    other = world.published_exam(tok, oid, code="TOEIC-A", visibility="PUBLIC", series="TOEIC")
    cand = world.candidate("m@mail.example.com")
    enr = reg(client, world, cand, a["id"]).json()["enrollment_id"]
    r = client.post(f"/api/v1/candidate/enrollments/{enr}/move", json={"target_exam_id": other["id"]},
                    headers=world.h(cand))
    assert r.json()["error"]["code"] == "NOT_SAME_SERIES"
    r = client.post(f"/api/v1/candidate/enrollments/{enr}/move", json={"target_exam_id": b["id"]},
                    headers=world.h(cand))
    assert r.status_code == 201 and r.json()["exam_id"] == b["id"]
    exams = {e["code"]: e for e in client.get("/api/v1/org/exams", headers=world.h(tok, oid)).json()}
    assert exams["EPT-A"]["registered_count"] == 0 and exams["EPT-B"]["registered_count"] == 1
    statuses = sorted(e["status"] for e in client.get("/api/v1/candidate/enrollments",
                                                      headers=world.h(cand)).json())
    assert statuses == ["CANCELLED", "CONFIRMED"]


def test_candidate_cannot_touch_someone_elses_enrollment(client, world, pub):
    oid, tok = pub
    exam = world.published_exam(tok, oid, code="OWN", visibility="PUBLIC")
    a, b = world.candidate("own-a@mail.example.com"), world.candidate("own-b@mail.example.com")
    enr = reg(client, world, a, exam["id"]).json()["enrollment_id"]
    assert client.post(f"/api/v1/candidate/enrollments/{enr}/cancel", headers=world.h(b)).status_code == 404


def test_concurrent_registration_never_exceeds_capacity(client, world, pub):
    oid, tok = pub
    exam = world.published_exam(tok, oid, code="RUSH", visibility="PUBLIC", capacity=5)
    for i in range(20):
        world.candidate(f"rush{i}@mail.example.com")
    with transaction("system") as db:
        cand_ids = [c.id for c in db.scalars(select(Candidate))]

    def attempt(cid):
        try:
            with transaction("candidate", candidate_id=cid) as db:
                registration.register(db, db.get(Candidate, cid), exam["id"], None)
            return "ok"
        except AppError as e:
            return e.code

    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(attempt, cand_ids))
    assert results.count("ok") == 5
    assert set(results) == {"ok", "EXAM_FULL"}
    with transaction("system") as db:
        assert db.get(Exam, exam["id"]).registered_count == 5
