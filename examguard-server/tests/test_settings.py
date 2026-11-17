"""Hierarchical settings: platform → organization → exam (PRD §8.5, §24.1)."""
import pytest


@pytest.fixture
def ctx(world):
    oid = world.org("setco", admin="admin@set.example.com", exam_admin="exams@set.example.com")
    admin, exams = world.staff_login("admin@set.example.com"), world.staff_login("exams@set.example.com")
    exam = world.published_exam(exams, oid, code="S1")
    return oid, admin, exams, exam


def eff(resp, key):
    return resp.json()["effective"][key]


def test_resolution_order(client, world, ctx):
    oid, admin, exams, exam = ctx
    url = f"/api/v1/org/exams/{exam['id']}/settings"
    r = client.get(url, headers=world.h(exams, oid))
    assert eff(r, "retention_default_days") == {"value": 90, "source": "platform", "clamped": False}
    client.patch("/api/v1/org/settings", json={"overrides": {"retention_default_days": 180}},
                 headers=world.h(admin, oid))
    assert eff(client.get(url, headers=world.h(exams, oid)), "retention_default_days")["source"] == "organization"
    client.patch(url, json={"overrides": {"retention_default_days": 365}}, headers=world.h(exams, oid))
    r = client.get(url, headers=world.h(exams, oid))
    assert eff(r, "retention_default_days") == {"value": 365, "source": "exam", "clamped": False}
    # null removes the override and falls back to the organization value
    r = client.patch(url, json={"overrides": {"retention_default_days": None}, "confirm_shorten": True},
                     headers=world.h(exams, oid))
    assert eff(r, "retention_default_days")["value"] == 180


def test_validation(client, world, ctx):
    oid, admin, exams, exam = ctx
    r = client.patch("/api/v1/org/settings", json={"overrides": {"retention_default_days": 3,
                                                                  "nonsense": 1,
                                                                  "default_identity_check_public": "AI"}},
                     headers=world.h(admin, oid))
    assert r.status_code == 422
    assert {d["key"] for d in r.json()["error"]["details"]} == {
        "retention_default_days", "nonsense", "default_identity_check_public"}
    # identity-check defaults are organization-level, not exam-level
    r = client.patch(f"/api/v1/org/exams/{exam['id']}/settings",
                     json={"overrides": {"default_identity_check_public": "NONE"}}, headers=world.h(exams, oid))
    assert r.status_code == 422


def test_shortening_retention_requires_confirmation(client, world, ctx):
    oid, admin, _, _ = ctx
    r = client.patch("/api/v1/org/settings", json={"overrides": {"retention_dismissed_days": 14}},
                     headers=world.h(admin, oid))
    assert r.status_code == 409 and r.json()["error"]["code"] == "RETENTION_SHORTEN_CONFIRMATION_REQUIRED"
    assert r.json()["error"]["details"] == [{"key": "retention_dismissed_days", "from": 30, "to": 14}]
    r = client.patch("/api/v1/org/settings", json={"overrides": {"retention_dismissed_days": 14},
                                                   "confirm_shorten": True}, headers=world.h(admin, oid))
    assert r.status_code == 200
    # lengthening needs no confirmation
    r = client.patch("/api/v1/org/settings", json={"overrides": {"retention_dismissed_days": 60}},
                     headers=world.h(admin, oid))
    assert r.status_code == 200


def test_org_identity_default_applies_to_new_exams(client, world, ctx):
    oid, admin, exams, _ = ctx
    client.patch("/api/v1/org/settings", json={"overrides": {"default_identity_check_private": "MANUAL"}},
                 headers=world.h(admin, oid))
    r = client.post("/api/v1/org/exams", json={"code": "S2", "name": "x"}, headers=world.h(exams, oid))
    assert r.json()["identity_check"] == "MANUAL"


def test_platform_bounds_clamp_existing_overrides(client, world, ctx):
    oid, admin, _, _ = ctx
    client.patch("/api/v1/org/settings", json={"overrides": {"retention_default_days": 1000}},
                 headers=world.h(admin, oid))
    root = world.platform_admin()
    doc = client.get("/api/v1/platform/settings", headers=world.h(root)).json()
    doc["bounds"]["retention_default_days"] = [7, 365]
    assert client.put("/api/v1/platform/settings", json=doc, headers=world.h(root)).status_code == 200
    r = client.get("/api/v1/org/settings", headers=world.h(admin, oid))
    assert eff(r, "retention_default_days") == {"value": 365, "source": "organization", "clamped": True}
    doc["defaults"]["retention_default_days"] = 400
    r = client.put("/api/v1/platform/settings", json=doc, headers=world.h(root))
    assert r.status_code == 422


def test_platform_endpoints_require_platform_admin(client, world, ctx):
    oid, admin, _, _ = ctx
    assert client.get("/api/v1/platform/settings", headers=world.h(admin)).status_code == 403
