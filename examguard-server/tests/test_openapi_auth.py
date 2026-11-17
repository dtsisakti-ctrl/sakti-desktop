"""/docs must be usable: auth is declared as security schemes, never as plain header parameters.

Swagger UI (and the OpenAPI spec) ignore header *parameters* named Authorization, so a token
typed into such a field is never sent. This test keeps that regression from coming back.
"""
from .conftest import Exam1b


def test_no_authorization_header_parameters(client):
    spec = client.get("/openapi.json").json()
    schemes = spec["components"]["securitySchemes"]
    assert schemes["SessionToken"] == {**schemes["SessionToken"], "type": "http", "scheme": "bearer"}
    assert schemes["OrgId"]["in"] == "header" and schemes["OrgId"]["name"] == "X-Org-Id"
    for path, ops in spec["paths"].items():
        for op in ops.values():
            names = {p["name"].lower() for p in op.get("parameters", [])}
            assert not names & {"authorization", "x-org-id"}, path
    assert {"SessionToken": []} in spec["paths"]["/api/v1/staff/me"]["get"]["security"]


def test_header_variants(world):
    ex = Exam1b(world)
    c, tok = world.c, ex.ea
    assert c.get("/api/v1/staff/me", headers={"Authorization": f"bearer {tok}"}).status_code == 200
    assert c.get("/api/v1/staff/me", headers={"Authorization": tok}).status_code == 401
    r = c.get("/api/v1/org/exams", headers={"Authorization": f"Bearer {tok}", "X-Org-Id": "bukan-uuid"})
    assert r.status_code == 422 and r.json()["error"]["message"] == "X-Org-Id must be a UUID"
    r = c.get("/api/v1/org/exams", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "ORG_REQUIRED"
