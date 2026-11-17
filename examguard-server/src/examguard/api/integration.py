"""Integration API for exam websites / LMS (PRD §16.4–16.6) and its management by the Org Admin."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from .. import permissions as P
from ..db import set_context
from ..models import Integration
from ..schemas import (IntegrationCandidateIn, IntegrationCreateIn, IntegrationOut, IntegrationPatchIn,
                       IntegrationResultIn)
from ..services import integration as svc
from .deps import DB, OrgPrincipal

_basic = HTTPBasic(auto_error=False, scheme_name="IntegrationCredentials",
                   description="client_id as username, secret as password")


def current_integration(db: DB, cred: Annotated[HTTPBasicCredentials | None, Depends(_basic)] = None) -> Integration:
    set_context(db, "system")   # every service query below is filtered by the integration's org_id
    return svc.authenticate(db, cred.username if cred else None, cred.password if cred else None)


Integ = Annotated[Integration, Depends(current_integration)]
router = APIRouter(prefix="/integration/v1", tags=["integration (LMS)"])
admin = APIRouter(prefix="/api/v1/org/integrations", tags=["integration management"])


# ------------------------------------------------------------------ LMS → server
@router.get("/exams")
def list_exams(db: DB, integ: Integ):
    return svc.list_exams(db, integ)


@router.post("/exams/{exam_id}/candidates", status_code=status.HTTP_201_CREATED)
def register_candidate(db: DB, integ: Integ, exam_id: UUID, body: IntegrationCandidateIn):
    """Enroll a candidate (idempotent per candidate_ref) and return a launch link when the exam is open."""
    return svc.register_candidate(db, integ, exam_id, email=body.email, full_name=body.full_name,
                                  external_ref=body.candidate_ref, accommodation=body.time_accommodation_minutes)


@router.post("/attempts/{attempt_id}/launch")
def launch_link(db: DB, integ: Integ, attempt_id: UUID):
    """Fresh single-use launch link (15 minutes); request it when the candidate clicks 'Start'."""
    return svc.launch_link(db, integ, attempt_id)


@router.get("/attempts/{attempt_id}")
def get_attempt(db: DB, integ: Integ, attempt_id: UUID):
    return svc.attempt_view(db, integ, attempt_id)


@router.post("/attempts/{attempt_id}/completion")
def completion(db: DB, integ: Integ, attempt_id: UUID):
    """Report that the final answers are saved: ACTIVE → SUBMITTED, returns the completion token."""
    return svc.completion(db, integ, attempt_id)


@router.post("/attempts/{attempt_id}/result")
def result(db: DB, integ: Integ, attempt_id: UUID, body: IntegrationResultIn):
    return svc.save_result(db, integ, attempt_id, body.model_dump())


# ------------------------------------------------------------------ Org Admin management
@admin.get("", response_model=list[IntegrationOut])
def list_integrations(db: DB, p: OrgPrincipal):
    p.require(P.INTEGRATIONS)
    return svc.list_for(db, p)


@admin.post("", response_model=IntegrationOut, status_code=status.HTTP_201_CREATED)
def create_integration(db: DB, p: OrgPrincipal, body: IntegrationCreateIn):
    p.require(P.INTEGRATIONS)
    return svc.create(db, p, body.name, body.webhook_url)


@admin.patch("/{integration_id}", response_model=IntegrationOut)
def update_integration(db: DB, p: OrgPrincipal, integration_id: UUID, body: IntegrationPatchIn):
    p.require(P.INTEGRATIONS)
    return svc.update(db, p, integration_id, body.name, body.webhook_url, body.clear_webhook)


@admin.post("/{integration_id}/rotate-secret", response_model=IntegrationOut)
def rotate_secret(db: DB, p: OrgPrincipal, integration_id: UUID):
    p.require(P.INTEGRATIONS)
    return svc.rotate_secret(db, p, integration_id)


@admin.post("/{integration_id}/revoke", response_model=IntegrationOut)
def revoke(db: DB, p: OrgPrincipal, integration_id: UUID):
    p.require(P.INTEGRATIONS)
    return svc.revoke(db, p, integration_id)


@admin.get("/{integration_id}/deliveries")
def deliveries(db: DB, p: OrgPrincipal, integration_id: UUID):
    """Recent webhook deliveries with status, attempts and last error (for debugging an LMS)."""
    p.require(P.INTEGRATIONS)
    return svc.deliveries(db, p, integration_id)
