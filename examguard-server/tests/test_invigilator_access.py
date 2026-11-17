"""Exam-scoped permissions (PRD §7) and tenant isolation of the Phase 1b tables (§8.2)."""

import pytest
from sqlalchemy import func, select, text

from examguard.db import transaction
from examguard.models import Command, DeviceSession, InvigilatorAssignment, StateTransition

from .conftest import NOW, Exam1b, at


@pytest.fixture
def setup(world):
    ex = Exam1b(world, org_slug="acme", code="EX1")
    other = world.published_exam(ex.ea, ex.org_id, code="EX2")
    inv_id, inv = ex.add_staff("inv@acme.example.com")
    aid = ex.enroll("c@example.com")
    at(ex.window_start)
    ex.launch(aid)
    return ex, other, inv_id, inv, aid


def test_unassigned_invigilator_sees_nothing(setup):
    ex, other, inv_id, inv, aid = setup
    t = ex.as_(inv)
    assert ex.get("/exams", t).json() == []
    assert ex.get(f"/exams/{ex.id}/attempts", t).status_code == 403
    assert ex.get(f"/attempts/{aid}", t).status_code == 403
    assert ex.post(f"/attempts/{aid}/pause", {"reason": "cek"}, t).status_code == 403


def test_assigned_invigilator_scope(setup):
    ex, other, inv_id, inv, aid = setup
    assert ex.post(f"/exams/{ex.id}/invigilators", {"user_id": str(inv_id)}).status_code == 201
    assert ex.post(f"/exams/{ex.id}/invigilators", {"user_id": str(inv_id)}).status_code == 409
    t = ex.as_(inv)
    assert [e["code"] for e in ex.get("/exams", t).json()] == ["EX1"]
    assert ex.get(f"/exams/{ex.id}", t).status_code == 200
    assert ex.get(f"/exams/{other['id']}", t).status_code == 403
    d = ex.detail(aid, t)
    assert "pause" in d["available_actions"] and "reopen" not in d["available_actions"]
    assert ex.post(f"/attempts/{aid}/pause", {"reason": "cek"}, t).status_code == 200
    assert ex.post(f"/attempts/{aid}/resume", {"reason": "lanjut"}, t).status_code == 200
    # Exam-Admin-only actions
    assert ex.post(f"/exams/{ex.id}/extend", {"minutes": 5, "reason": "tambah"}, t).status_code == 403
    assert ex.post(f"/exams/{ex.id}/finalize", {}, t).status_code == 403
    body = {"action": "TERMINATE", "attempt_ids": [str(aid)], "reason": "x" * 5,
            "reason_category": "TECHNICAL", "confirm_exam_code": "EX1"}
    assert ex.post(f"/exams/{ex.id}/bulk", body, t).status_code == 403
    assert ex.post(f"/exams/{ex.id}/invigilators", {"user_id": str(inv_id)}, t).status_code == 403
    # Individual terminate and force submit are allowed (PRD §7, Q9)
    r = ex.post(f"/attempts/{aid}/terminate", {"reason": "joki", "reason_category": "DISCIPLINARY"}, t)
    assert r.status_code == 200
    assert ex.post(f"/attempts/{aid}/reinstate", {"reason": "keliru",
                   "deadline": ex.window_end.isoformat()}, t).status_code == 403
    # unassigning removes access
    assert ex.w.c.delete(f"/api/v1/org/exams/{ex.id}/invigilators/{inv_id}", headers=ex.h()).status_code == 204
    assert ex.get(f"/attempts/{aid}", t).status_code == 403


def test_only_invigilator_members_can_be_assigned(setup, world):
    ex, *_ = setup
    ea_id = world.c.get("/api/v1/staff/me", headers=world.h(ex.ea)).json()["id"]
    r = ex.post(f"/exams/{ex.id}/invigilators", {"user_id": ea_id})
    assert r.json()["error"]["code"] == "NOT_AN_INVIGILATOR"


def test_org_admin_monitors_but_cannot_control(setup):
    ex, other, inv_id, inv, aid = setup
    assert ex.get(f"/exams/{ex.id}/attempts", ex.admin).status_code == 200
    assert ex.detail(aid, ex.admin)["available_actions"] == []
    assert ex.post(f"/attempts/{aid}/pause", {"reason": "cek"}, ex.admin).status_code == 403


def test_other_organization_gets_404(setup, world):
    ex, other, inv_id, inv, aid = setup
    at(NOW)                                   # publish the second org's exam in the future
    b = Exam1b(world, org_slug="beta", code="B1")
    at(ex.window_start)
    assert b.get(f"/attempts/{aid}").status_code == 404
    assert b.post(f"/attempts/{aid}/pause", {"reason": "cek"}).status_code == 404
    assert b.get(f"/exams/{ex.id}/attempts").status_code == 404
    assert b.post(f"/exams/{ex.id}/extend", {"minutes": 5, "reason": "tambah"}).status_code == 404
    assert b.post(f"/exams/{ex.id}/invigilators", {"user_id": str(inv_id)}).status_code == 404


def test_rls_hides_phase1b_tables_across_orgs(setup, world):
    ex, other, inv_id, inv, aid = setup
    ex.post(f"/exams/{ex.id}/invigilators", {"user_id": str(inv_id)})
    ex.post(f"/attempts/{aid}/warning", {"message": "hai"})
    at(NOW)                                   # publish the second org's exam in the future
    b = Exam1b(world, org_slug="beta", code="B1")
    at(ex.window_start)
    tables = (StateTransition, DeviceSession, Command, InvigilatorAssignment)

    def counts(ctx, **ids):
        with transaction(ctx, **ids) as db:
            return [db.scalar(select(func.count()).select_from(t)) for t in tables]

    assert all(n > 0 for n in counts("staff", org_id=ex.org_id))
    assert counts("staff", org_id=b.org_id) == [0, 0, 0, 0]
    assert counts("candidate") == [0, 0, 0, 0]
    assert counts("public") == [0, 0, 0, 0]
    # org_id is derived from the parent attempt, never from the caller
    with pytest.raises(Exception), transaction("staff", org_id=b.org_id) as db:
        db.execute(text("INSERT INTO commands (attempt_id, type, state_version, issued_at, expires_at) "
                        "VALUES (:a, 'WARNING', 1, now(), now())"), {"a": aid})
