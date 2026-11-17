"""Organization isolation: API behaviour AND database-level RLS (defence in depth)."""
import psycopg
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, ProgrammingError

from examguard.db import set_context, transaction
from examguard.models import Candidate, Enrollment, Exam, Organization

from .conftest import APP_URL


@pytest.fixture
def two_orgs(world):
    a = world.org("org-a", public=True, admin="admin@a.example.com", exam_admin="exams@a.example.com")
    b = world.org("org-b", public=True, admin="admin@b.example.com", exam_admin="exams@b.example.com")
    ta, tb = world.staff_login("exams@a.example.com"), world.staff_login("exams@b.example.com")
    exam_a = world.published_exam(ta, a, code="A1", visibility="PUBLIC")
    exam_b = world.published_exam(tb, b, code="B1", visibility="PRIVATE")
    return {"a": a, "b": b, "ta": ta, "tb": tb, "exam_a": exam_a, "exam_b": exam_b}


def test_api_hides_other_org_exams(client, world, two_orgs):
    t = two_orgs
    ids = [e["id"] for e in client.get("/api/v1/org/exams", headers=world.h(t["tb"], t["b"])).json()]
    assert ids == [t["exam_b"]["id"]]
    for method, path in (("get", ""), ("patch", ""), ("post", "/publish"), ("get", "/enrollments"),
                         ("get", "/settings")):
        r = getattr(client, method)(f"/api/v1/org/exams/{t['exam_a']['id']}{path}",
                                    headers=world.h(t["tb"], t["b"]),
                                    **({"json": {}} if method == "patch" else {}))
        assert r.status_code == 404, (method, path, r.text)


def test_header_for_foreign_org_is_rejected(client, world, two_orgs):
    t = two_orgs
    r = client.get("/api/v1/org/exams", headers=world.h(t["tb"], t["a"]))
    assert r.status_code == 403
    r = client.get("/api/v1/org/exams", headers=world.h(t["tb"]))
    assert r.status_code == 400 and r.json()["error"]["code"] == "ORG_REQUIRED"


def test_rls_filters_even_without_where_clause(two_orgs):
    """A buggy query that forgets the org filter must still only see its own org."""
    t = two_orgs
    with transaction("staff", org_id=t["b"]) as db:
        codes = {e.code for e in db.scalars(select(Exam))}
    assert codes == {"B1"}
    with transaction("public") as db:
        codes = {e.code for e in db.scalars(select(Exam))}
    assert codes == {"A1"}  # only the published PUBLIC exam


def test_no_context_sees_nothing():
    with psycopg.connect(APP_URL.replace("+psycopg", "")) as c:
        assert c.execute("SELECT count(*) FROM exams").fetchone()[0] == 0
        assert c.execute("SELECT count(*) FROM candidates").fetchone()[0] == 0


def test_staff_sees_only_candidates_enrolled_in_own_org(client, world, two_orgs):
    t = two_orgs
    tok = world.candidate("only-a@mail.example.com")
    assert client.post(f"/api/v1/candidate/exams/{t['exam_a']['id']}/register", json={},
                       headers=world.h(tok)).status_code == 201
    with transaction("staff", org_id=t["a"]) as db:
        assert [c.email for c in db.scalars(select(Candidate))] == ["only-a@mail.example.com"]
    with transaction("staff", org_id=t["b"]) as db:
        assert list(db.scalars(select(Candidate))) == []
        assert list(db.scalars(select(Enrollment))) == []


def test_staff_cannot_write_into_another_org(two_orgs):
    t = two_orgs
    with pytest.raises(DBAPIError):
        with transaction("staff", org_id=t["b"]) as db:
            db.add(Exam(org_id=t["a"], code="EVIL", name="evil", visibility="PRIVATE",
                        allowed_origins=[], policy={}, settings={}))
            db.flush()


def test_staff_cannot_grant_itself_public_publishing(two_orgs):
    t = two_orgs
    with pytest.raises(DBAPIError) as exc:
        with transaction("staff", org_id=t["b"]) as db:
            db.execute(text("UPDATE organizations SET can_publish_public = NOT can_publish_public "
                            "WHERE id = :o"), {"o": t["b"]})
    assert "can_publish_public" in str(exc.value)


def test_enrollment_org_is_derived_from_exam(client, world, two_orgs):
    """Even the system context cannot store an enrollment under the wrong organization."""
    t = two_orgs
    world.candidate("x@mail.example.com")
    with transaction("system") as db:
        cand = db.scalar(select(Candidate))
        enr = Enrollment(exam_id=t["exam_a"]["id"], candidate_id=cand.id, source="API", org_id=t["b"])
        db.add(enr)
        db.flush()
        db.refresh(enr)
        assert enr.org_id == t["a"]


def test_audit_log_is_append_only_for_runtime_role(two_orgs):
    with pytest.raises(ProgrammingError):
        with transaction("system") as db:
            db.execute(text("UPDATE audit_log SET action = 'x'"))
    with pytest.raises(ProgrammingError):
        with transaction("system") as db:
            db.execute(text("DELETE FROM audit_log"))
    with pytest.raises(DBAPIError):
        with transaction("staff", org_id=two_orgs["b"]) as db:
            db.execute(text("SELECT eg_audit_append(:o, 'staff', NULL, 'forged', NULL, NULL, '{}')"),
                       {"o": two_orgs["a"]})


def test_auth_tables_invisible_outside_system_context(two_orgs):
    with transaction("staff", org_id=two_orgs["a"]) as db:
        for table in ("auth_sessions", "one_time_tokens", "email_outbox"):
            assert db.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0


def test_organizations_table_is_readable_but_not_writable_by_staff(two_orgs):
    with transaction("staff", org_id=two_orgs["a"]) as db:
        assert db.scalar(select(Organization).where(Organization.id == two_orgs["b"])) is not None
        n = db.execute(text("UPDATE organizations SET name = 'hacked' WHERE id = :o"),
                       {"o": two_orgs["b"]}).rowcount
        assert n == 0
