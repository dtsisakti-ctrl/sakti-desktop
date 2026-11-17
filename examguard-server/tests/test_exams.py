"""Exam definition and publication lifecycle."""
from datetime import timedelta

import pytest

from .conftest import NOW


@pytest.fixture
def org(world):
    oid = world.org("acme", admin="admin@acme.example.com", exam_admin="exams@acme.example.com")
    return oid, world.staff_login("exams@acme.example.com"), world.staff_login("admin@acme.example.com")


def test_create_sets_identity_check_default_by_visibility(client, world, org):
    oid, tok, _ = org
    priv = client.post("/api/v1/org/exams", json={"code": "P1", "name": "Private"}, headers=world.h(tok, oid))
    pub = client.post("/api/v1/org/exams", json={"code": "P2", "name": "Public", "visibility": "PUBLIC"},
                      headers=world.h(tok, oid))
    assert priv.json()["identity_check"] == "NONE"
    assert pub.json()["identity_check"] == "MANUAL"
    assert priv.json()["status"] == "DRAFT"


def test_duplicate_code_conflicts(client, world, org):
    oid, tok, _ = org
    client.post("/api/v1/org/exams", json={"code": "DUP", "name": "x"}, headers=world.h(tok, oid))
    r = client.post("/api/v1/org/exams", json={"code": "DUP", "name": "y"}, headers=world.h(tok, oid))
    assert r.status_code == 409 and r.json()["error"]["code"] == "EXAM_CODE_TAKEN"


def test_role_permissions(client, world, org):
    oid, _, admin_tok = org
    r = client.post("/api/v1/org/exams", json={"code": "X", "name": "x"}, headers=world.h(admin_tok, oid))
    assert r.status_code == 403  # ORG_ADMIN manages the org, not exams
    assert client.get("/api/v1/org/members", headers=world.h(admin_tok, oid)).status_code == 200


def test_publish_reports_all_problems(client, world, org):
    oid, tok, _ = org
    body = {"code": "BAD", "name": "bad", "visibility": "PUBLIC",
            "exam_url": "http://exam.example.edu",
            "window_start": (NOW - timedelta(hours=1)).isoformat(),
            "window_end": (NOW - timedelta(hours=2)).isoformat(),
            "late_start_policy": "FULL_DURATION",
            "policy": {"require_camera": False, "face_detection": True, "block_virtual_machines": True}}
    eid = client.post("/api/v1/org/exams", json=body, headers=world.h(tok, oid)).json()["id"]
    r = client.post(f"/api/v1/org/exams/{eid}/publish", headers=world.h(tok, oid))
    assert r.status_code == 422 and r.json()["error"]["code"] == "EXAM_NOT_PUBLISHABLE"
    fields = {p["field"] for p in r.json()["error"]["details"]}
    assert {"exam_url", "window_end", "window_start", "duration_minutes", "visibility",
            "registration", "policy", "identity_check"} <= fields


def test_publish_fills_defaults(client, world, org):
    oid, tok, _ = org
    exam = world.published_exam(tok, oid, code="OK1", allowed_origins=["https://sso.example.edu"])
    ws = exam["window_start"]
    assert exam["status"] == "READY"
    assert exam["latest_start"] > ws  # window_start + 30 min
    assert exam["checkin_open"] < ws  # window_start - 30 min
    assert exam["allowed_origins"] == ["https://exam.example.edu", "https://sso.example.edu"]


def test_ready_exam_is_frozen_until_unpublished(client, world, org):
    oid, tok, _ = org
    exam = world.published_exam(tok, oid, code="FRZ")
    r = client.patch(f"/api/v1/org/exams/{exam['id']}", json={"name": "renamed"}, headers=world.h(tok, oid))
    assert r.status_code == 409 and r.json()["error"]["code"] == "EXAM_NOT_EDITABLE"
    assert client.post(f"/api/v1/org/exams/{exam['id']}/unpublish", headers=world.h(tok, oid)).status_code == 200
    r = client.patch(f"/api/v1/org/exams/{exam['id']}", json={"name": "renamed"}, headers=world.h(tok, oid))
    assert r.status_code == 200 and r.json()["name"] == "renamed"


def test_public_exam_requires_org_permission(client, world, org):
    oid, tok, _ = org  # acme cannot publish public exams
    r = client.post("/api/v1/org/exams", json=world.exam_body(code="PUB", visibility="PUBLIC"),
                    headers=world.h(tok, oid))
    r = client.post(f"/api/v1/org/exams/{r.json()['id']}/publish", headers=world.h(tok, oid))
    assert r.status_code == 422
    assert {"field": "visibility", "problem": "organization is not allowed to publish public exams"} \
        in r.json()["error"]["details"]


def test_cancel_exam_cancels_enrollments_and_notifies(client, world):
    oid = world.org("pub", public=True, admin="a@pub.example.com", exam_admin="e@pub.example.com")
    tok = world.staff_login("e@pub.example.com")
    exam = world.published_exam(tok, oid, code="C1", visibility="PUBLIC")
    cand = world.candidate("p@mail.example.com")
    client.post(f"/api/v1/candidate/exams/{exam['id']}/register", json={}, headers=world.h(cand))

    r = client.post(f"/api/v1/org/exams/{exam['id']}/unpublish", headers=world.h(tok, oid))
    assert r.status_code == 409 and r.json()["error"]["code"] == "EXAM_HAS_ENROLLMENTS"
    r = client.post(f"/api/v1/org/exams/{exam['id']}/cancel", json={"reason": "venue issue"},
                    headers=world.h(tok, oid))
    assert r.status_code == 200 and r.json()["status"] == "CANCELLED" and r.json()["registered_count"] == 0
    mine = client.get("/api/v1/candidate/enrollments", headers=world.h(cand)).json()
    assert mine[0]["status"] == "CANCELLED" and mine[0]["attempt_status"] is None
    assert "registration_cancelled" in world.outbox("p@mail.example.com")


def test_access_code_is_never_returned(client, world, org):
    oid, tok, _ = org
    r = client.post("/api/v1/org/exams", json={"code": "AC", "name": "x", "access_code": "secret123"},
                    headers=world.h(tok, oid))
    assert r.json()["has_access_code"] is True
    assert "secret123" not in r.text and "access_code_hash" not in r.text
