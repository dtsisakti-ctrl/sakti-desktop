"""Candidate & staff authentication, email verification, sessions."""
from datetime import timedelta

from examguard import clock

from .conftest import NOW, PASSWORD


def test_signup_verify_login_me(client, world):
    r = client.post("/api/v1/candidate/auth/signup",
                    json={"email": "Budi@Mail.example.com", "password": PASSWORD, "full_name": "Budi"})
    assert r.status_code == 201
    assert r.json()["email_verified_at"] is None
    token = world.outbox_token("Budi@Mail.example.com", "candidate_verify_email")
    assert client.post("/api/v1/candidate/auth/verify-email", json={"token": token}).status_code == 200
    # token is single-use
    r = client.post("/api/v1/candidate/auth/verify-email", json={"token": token})
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_TOKEN"
    # login is case-insensitive on email
    r = client.post("/api/v1/candidate/auth/login", json={"email": "budi@mail.example.com", "password": PASSWORD})
    assert r.status_code == 200
    me = client.get("/api/v1/candidate/me", headers=world.h(r.json()["token"])).json()
    assert me["email_verified_at"] is not None


def test_duplicate_email_and_weak_password(client, world):
    world.candidate("a@mail.example.com")
    r = client.post("/api/v1/candidate/auth/signup",
                    json={"email": "A@MAIL.example.com", "password": PASSWORD, "full_name": "Dup"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"
    r = client.post("/api/v1/candidate/auth/signup",
                    json={"email": "b@mail.example.com", "password": "short", "full_name": "B"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "WEAK_PASSWORD"


def test_bad_credentials_are_indistinguishable(client, world):
    world.candidate("c@mail.example.com")
    wrong_pw = client.post("/api/v1/candidate/auth/login", json={"email": "c@mail.example.com", "password": "nope-nope-nope"})
    no_user = client.post("/api/v1/candidate/auth/login", json={"email": "x@mail.example.com", "password": "nope-nope-nope"})
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json() == no_user.json()


def test_resend_verification_does_not_enumerate(client, world):
    world.candidate("d@mail.example.com", verify=False)
    r1 = client.post("/api/v1/candidate/auth/resend-verification", json={"email": "d@mail.example.com"})
    r2 = client.post("/api/v1/candidate/auth/resend-verification", json={"email": "ghost@mail.example.com"})
    assert r1.status_code == r2.status_code == 202
    assert world.outbox("d@mail.example.com").count("candidate_verify_email") == 2


def test_logout_and_expiry(client, world):
    tok = world.candidate("e@mail.example.com")
    assert client.get("/api/v1/candidate/me", headers=world.h(tok)).status_code == 200
    assert client.post("/api/v1/candidate/auth/logout", headers=world.h(tok)).status_code == 204
    assert client.get("/api/v1/candidate/me", headers=world.h(tok)).status_code == 401

    tok = client.post("/api/v1/candidate/auth/login",
                      json={"email": "e@mail.example.com", "password": PASSWORD}).json()["token"]
    clock.set_now(NOW + timedelta(hours=25))
    assert client.get("/api/v1/candidate/me", headers=world.h(tok)).status_code == 401


def test_session_kinds_are_not_interchangeable(client, world):
    org = world.org("acme", admin="admin@acme.example.com")
    staff = world.staff_login("admin@acme.example.com")
    cand = world.candidate("f@mail.example.com")
    assert client.get("/api/v1/candidate/me", headers=world.h(staff)).status_code == 401
    assert client.get("/api/v1/staff/me", headers=world.h(cand)).status_code == 401
    assert client.get("/api/v1/org/members", headers=world.h(cand, org)).status_code == 401


def test_staff_me_lists_memberships(client, world):
    a = world.org("org-a", admin="multi@staff.example.com")
    b = world.org("org-b", exam_admin="multi@staff.example.com", admin="other@staff.example.com")
    me = client.get("/api/v1/staff/me", headers=world.h(world.staff_login("multi@staff.example.com"))).json()
    roles = {m["org_id"]: m["roles"] for m in me["memberships"]}
    assert roles == {str(a): ["ORG_ADMIN"], str(b): ["EXAM_ADMIN"]}
