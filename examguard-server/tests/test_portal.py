"""Candidate Portal backend (PRD §28): password reset, profile, 'Ujian Saya', launch window, invitation preview."""
from datetime import timedelta

import pytest

from examguard.config import get_settings

from .conftest import NOW, PASSWORD, Exam1b, at

NEW_PASSWORD = "another-long-password"


def test_password_reset_flow(client, world):
    cand = world.candidate("rina@example.com")
    other = world.candidate_login("rina@example.com")
    # unknown accounts get the same answer (no enumeration) and no email
    assert client.post("/api/v1/candidate/auth/password-reset/request",
                       json={"email": "nobody@example.com"}).status_code == 202
    assert world.outbox("nobody@example.com") == []
    assert client.post("/api/v1/candidate/auth/password-reset/request",
                       json={"email": "RINA@example.com"}).status_code == 202
    token = world.outbox_token("rina@example.com", "candidate_password_reset")
    weak = client.post("/api/v1/candidate/auth/password-reset/confirm", json={"token": token, "password": "short"})
    assert weak.json()["error"]["code"] == "WEAK_PASSWORD"
    r = client.post("/api/v1/candidate/auth/password-reset/confirm", json={"token": token, "password": NEW_PASSWORD})
    assert r.status_code == 200, r.text
    # every existing session is signed out; the old password no longer works
    assert client.get("/api/v1/candidate/me", headers=world.h(cand)).status_code == 401
    assert client.get("/api/v1/candidate/me", headers=world.h(other)).status_code == 401
    assert client.post("/api/v1/candidate/auth/login",
                       json={"email": "rina@example.com", "password": PASSWORD}).status_code == 401
    assert client.post("/api/v1/candidate/auth/login",
                       json={"email": "rina@example.com", "password": NEW_PASSWORD}).status_code == 200
    # single use
    again = client.post("/api/v1/candidate/auth/password-reset/confirm", json={"token": token, "password": NEW_PASSWORD})
    assert again.json()["error"]["code"] == "INVALID_TOKEN"


def test_password_reset_link_expires_and_newer_reset_voids_older(client, world):
    from examguard import clock
    world.candidate("budi@example.com")
    client.post("/api/v1/candidate/auth/password-reset/request", json={"email": "budi@example.com"})
    first = world.outbox_token("budi@example.com", "candidate_password_reset")
    client.post("/api/v1/candidate/auth/password-reset/request", json={"email": "budi@example.com"})
    second = world.outbox_token("budi@example.com", "candidate_password_reset")
    assert client.post("/api/v1/candidate/auth/password-reset/confirm",
                       json={"token": second, "password": NEW_PASSWORD}).status_code == 200
    r = client.post("/api/v1/candidate/auth/password-reset/confirm", json={"token": first, "password": NEW_PASSWORD})
    assert r.json()["error"]["code"] == "INVALID_TOKEN"
    client.post("/api/v1/candidate/auth/password-reset/request", json={"email": "budi@example.com"})
    late = world.outbox_token("budi@example.com", "candidate_password_reset")
    clock.set_now(clock.now() + timedelta(minutes=61))
    r = client.post("/api/v1/candidate/auth/password-reset/confirm", json={"token": late, "password": NEW_PASSWORD})
    assert r.json()["error"]["code"] == "INVALID_TOKEN"


def test_reset_link_points_to_the_portal_and_verifies_email(client, world):
    from sqlalchemy import select
    from examguard.db import transaction
    from examguard.models import EmailOutbox
    client.post("/api/v1/candidate/auth/signup",
                json={"email": "dewi@example.com", "password": PASSWORD, "full_name": "Dewi"})
    client.post("/api/v1/candidate/auth/password-reset/request", json={"email": "dewi@example.com"})
    with transaction("system") as db:
        body = db.scalars(select(EmailOutbox.body).where(EmailOutbox.template == "candidate_password_reset")).first()
    base = get_settings().public_base_url.rstrip("/")
    assert f"{base}/portal/reset-password?token=" in body
    token = world.outbox_token("dewi@example.com", "candidate_password_reset")
    client.post("/api/v1/candidate/auth/password-reset/confirm", json={"token": token, "password": NEW_PASSWORD})
    tok = client.post("/api/v1/candidate/auth/login",
                      json={"email": "dewi@example.com", "password": NEW_PASSWORD}).json()["token"]
    assert client.get("/api/v1/candidate/me", headers=world.h(tok)).json()["email_verified_at"] is not None


def test_profile_and_change_password(client, world):
    cand = world.candidate("agus@example.com", name="agus")
    other = world.candidate_login("agus@example.com")
    r = client.patch("/api/v1/candidate/me", json={"full_name": "  Agus Pratama "}, headers=world.h(cand))
    assert r.status_code == 200 and r.json()["full_name"] == "Agus Pratama"
    wrong = client.post("/api/v1/candidate/me/password", headers=world.h(cand),
                        json={"current_password": "nope-nope-nope", "new_password": NEW_PASSWORD})
    assert wrong.json()["error"]["code"] == "WRONG_PASSWORD"
    ok = client.post("/api/v1/candidate/me/password", headers=world.h(cand),
                     json={"current_password": PASSWORD, "new_password": NEW_PASSWORD})
    assert ok.status_code == 204
    assert client.get("/api/v1/candidate/me", headers=world.h(cand)).status_code == 200   # this session stays
    assert client.get("/api/v1/candidate/me", headers=world.h(other)).status_code == 401  # others signed out


def _mine(client, world, token):
    r = client.get("/api/v1/candidate/enrollments", headers=world.h(token))
    assert r.status_code == 200, r.text
    return r.json()


def test_my_exams_launch_window(client, world):
    ex = Exam1b(world)
    ex.enroll("sari@example.com")
    tok = world.candidate_login("sari@example.com")
    [e] = _mine(client, world, tok)
    assert e["exam"]["org_name"] == "ACME" and e["exam"]["duration_minutes"] == 90
    assert e["exam"]["latest_start"] and e["attempt"]["status"] == "NOT_STARTED"
    assert e["can_launch"] is False and e["launch_reason"] == "NOT_YET_OPEN" and e["can_change"] is False
    r = client.post(f"/api/v1/candidate/enrollments/{e['id']}/launch", headers=world.h(tok))
    assert r.json()["error"]["code"] == "LAUNCH_NOT_YET_OPEN"
    at(ex.checkin_open)
    tok = world.candidate_login("sari@example.com")
    [e] = _mine(client, world, tok)
    assert e["can_launch"] is True and e["launch_reason"] is None
    r = client.post(f"/api/v1/candidate/enrollments/{e['id']}/launch", headers=world.h(tok))
    assert r.status_code == 200 and r.json()["launch_url"].startswith("examguard://launch?t=")
    at(ex.latest_start + timedelta(seconds=1))
    tok = world.candidate_login("sari@example.com")
    [e] = _mine(client, world, tok)
    assert e["can_launch"] is False and e["launch_reason"] == "LATE_START_CLOSED"


def test_relaunch_allowed_after_start_until_the_attempt_ends(client, world):
    ex = Exam1b(world)
    aid = ex.enroll("tono@example.com")
    at(ex.window_start)
    ex.launch(aid)
    at(ex.latest_start + timedelta(minutes=5))      # past the latest start, but the attempt is running
    tok = world.candidate_login("tono@example.com")
    [e] = _mine(client, world, tok)
    assert e["can_launch"] is True and e["attempt"]["status"] in ("ACTIVE", "INTERRUPTED")
    from examguard.services import client_flow
    ex.call(client_flow.submit, aid, source="MANUAL_FINISH")
    [e] = _mine(client, world, tok)
    assert e["can_launch"] is False and e["launch_reason"] == "ENDED" and e["attempt"]["ended_at"]


def test_self_registered_can_change_until_registration_close(client, world):
    oid = world.org("pub", public=True, admin="admin@pub.example.com", exam_admin="exams@pub.example.com")
    staff = world.staff_login("exams@pub.example.com")
    exam = world.published_exam(staff, oid, code="TOEFL1", visibility="PUBLIC", capacity=5)
    cand = world.candidate("lia@example.com")
    assert client.post(f"/api/v1/candidate/exams/{exam['id']}/register", json={},
                       headers=world.h(cand)).status_code == 201
    [e] = _mine(client, world, cand)
    assert e["can_change"] is True and e["source"] == "SELF_REGISTERED"
    at(NOW + timedelta(days=6, hours=1))             # registration closes one day before the window
    [e] = _mine(client, world, world.candidate_login("lia@example.com"))
    assert e["can_change"] is False


def test_invitation_preview(client, world):
    oid = world.org("company", admin="hr@company.example.com", exam_admin="exams@company.example.com")
    staff = world.staff_login("exams@company.example.com")
    exam = world.published_exam(staff, oid, code="REKRUT", visibility="PRIVATE")
    client.post(f"/api/v1/org/exams/{exam['id']}/invitations", json={"emails": ["joko@example.com"]},
                headers=world.h(staff, oid))
    token = world.outbox_token("joko@example.com", "invitation")
    p = client.post("/api/v1/public/invitations/preview", json={"token": token}).json()
    assert p["status"] == "PENDING" and p["email"] == "joko@example.com" and p["org_name"] == "COMPANY"
    assert p["exam_name"] == "Exam REKRUT" and p["account_exists"] is False
    world.candidate("joko@example.com")
    assert client.post("/api/v1/public/invitations/preview", json={"token": token}).json()["account_exists"] is True
    bad = client.post("/api/v1/public/invitations/preview", json={"token": "x" * 20})
    assert bad.json()["error"]["code"] == "INVALID_TOKEN"


@pytest.mark.parametrize("path", ["/", "/portal/", "/admin/"])
def test_pages_exist_without_auth(client, path, tmp_path):
    get_settings().web_ui_dir = str(tmp_path)
    try:
        (tmp_path / "index.html").write_text("landing")
        for app in ("admin", "portal"):
            (tmp_path / app).mkdir(exist_ok=True)
            (tmp_path / app / "index.html").write_text(app)
        assert client.get(path).status_code == 200
    finally:
        get_settings().web_ui_dir = None
