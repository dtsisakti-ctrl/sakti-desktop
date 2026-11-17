"""Staff authentication and organization-scoped administration (Admin Web backend)."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Query, status
from sqlalchemy import select

from .. import access, audit, permissions
from ..db import elevated
from ..models import Membership, Organization
from ..schemas import (AuditEntryOut, EnrollmentPatchIn, ExamCreateIn, ExamOut, ExamPatchIn,
                       InvitationOut, InvitationsCreateIn, InvitationsCreateOut, LoginIn, MemberAddIn,
                       MemberOut, OrgEnrollmentOut, SessionOut, SettingsPatchIn, StaffMeOut)
from ..services import auth, exams, orgs, registration
from .deps import DB, CurrentStaffUser, OrgPrincipal, Token

auth_router = APIRouter(prefix="/api/v1/staff", tags=["staff"])
router = APIRouter(prefix="/api/v1/org", tags=["organization"])

Reason = Annotated[str, Body(embed=True, min_length=3, max_length=500)]


# ------------------------------------------------------------------ auth
@auth_router.post("/auth/login", response_model=SessionOut)
def staff_login(db: DB, body: LoginIn):
    token, expires = auth.login(db, "STAFF", body.email, body.password)
    return {"token": token, "kind": "STAFF", "expires_at": expires}


@auth_router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def staff_logout(db: DB, user: CurrentStaffUser, token: Token):
    auth.logout(db, token)


@auth_router.get("/me", response_model=StaffMeOut)
def staff_me(db: DB, user: CurrentStaffUser):
    rows = db.execute(select(Membership.org_id, Membership.role).where(Membership.user_id == user.id)).all()
    by_org: dict[UUID, list[str]] = {}
    for org_id, role in rows:
        by_org.setdefault(org_id, []).append(role)
    orgs_ = {o.id: o for o in db.scalars(select(Organization).where(Organization.id.in_(by_org)))}
    return {
        "id": user.id, "email": user.email, "full_name": user.full_name,
        "is_platform_admin": user.is_platform_admin,
        "memberships": [{"org_id": oid, "org_slug": orgs_[oid].slug, "org_name": orgs_[oid].name,
                         "roles": sorted(r)} for oid, r in by_org.items()],
    }


# ------------------------------------------------------------------ members & settings
@router.get("/members", response_model=list[MemberOut])
def list_members(db: DB, p: OrgPrincipal):
    p.require("org.members")
    return [{"membership_id": m.id, "user_id": u.id, "email": u.email, "full_name": u.full_name,
             "role": m.role} for m, u in orgs.list_members(db, p.org_id)]


@router.post("/members", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
def add_member(db: DB, p: OrgPrincipal, body: MemberAddIn):
    p.require("org.members")
    m, u = orgs.add_member(db, p, email=body.email, role=body.role, full_name=body.full_name,
                           initial_password=body.initial_password)
    return {"membership_id": m.id, "user_id": u.id, "email": u.email, "full_name": u.full_name, "role": m.role}


@router.delete("/members/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(db: DB, p: OrgPrincipal, membership_id: UUID):
    p.require("org.members")
    orgs.remove_member(db, p, membership_id)


@router.get("/settings")
def get_org_settings(db: DB, p: OrgPrincipal):
    p.require("org.settings")
    return orgs.org_settings(db, p.org_id)


@router.patch("/settings")
def patch_org_settings(db: DB, p: OrgPrincipal, body: SettingsPatchIn):
    p.require("org.settings")
    return orgs.patch_org_settings(db, p, body.overrides, body.confirm_shorten)


@router.get("/audit-log", response_model=list[AuditEntryOut])
def audit_log(db: DB, p: OrgPrincipal, limit: int = Query(50, ge=1, le=500),
              before_seq: int | None = Query(None, ge=1)):
    p.require("org.audit")
    return orgs.list_audit(db, p.org_id, limit, before_seq)


@router.get("/audit-log/verify")
def audit_verify(db: DB, p: OrgPrincipal):
    p.require("org.audit")
    return audit.verify(db, audit.chain_key(p.org_id))


# ------------------------------------------------------------------ exams
@router.get("/exams", response_model=list[ExamOut])
def list_exams(db: DB, p: OrgPrincipal, status_: str | None = Query(None, alias="status")):
    """All exams of the organization; invigilators see only the exams assigned to them."""
    visible = access.visible_exam_ids(db, p)
    if visible is None:
        p.require("exam.read")
    return [exams.to_out(e) for e in exams.list_exams(db, p.org_id, status_)
            if visible is None or e.id in visible]


@router.post("/exams", response_model=ExamOut, status_code=status.HTTP_201_CREATED)
def create_exam(db: DB, p: OrgPrincipal, body: ExamCreateIn):
    p.require("exam.write")
    return exams.to_out(exams.create_exam(db, p, body))


@router.get("/exams/{exam_id}", response_model=ExamOut)
def get_exam(db: DB, p: OrgPrincipal, exam_id: UUID):
    if "exam.read" not in p.permissions:
        return exams.to_out(access.require_exam(db, p, exam_id, permissions.MONITOR))
    return exams.to_out(exams.get_exam(db, p.org_id, exam_id))


@router.patch("/exams/{exam_id}", response_model=ExamOut)
def patch_exam(db: DB, p: OrgPrincipal, exam_id: UUID, body: ExamPatchIn):
    p.require("exam.write")
    return exams.to_out(exams.patch_exam(db, p, exam_id, body))


@router.post("/exams/{exam_id}/publish", response_model=ExamOut)
def publish_exam(db: DB, p: OrgPrincipal, exam_id: UUID):
    p.require("exam.publish")
    return exams.to_out(exams.publish(db, p, exam_id))


@router.post("/exams/{exam_id}/unpublish", response_model=ExamOut)
def unpublish_exam(db: DB, p: OrgPrincipal, exam_id: UUID):
    p.require("exam.publish")
    return exams.to_out(exams.unpublish(db, p, exam_id))


@router.post("/exams/{exam_id}/cancel", response_model=ExamOut)
def cancel_exam(db: DB, p: OrgPrincipal, exam_id: UUID, reason: Reason):
    p.require("exam.publish")
    return exams.to_out(exams.cancel(db, p, exam_id, reason))


@router.get("/exams/{exam_id}/settings")
def get_exam_settings(db: DB, p: OrgPrincipal, exam_id: UUID):
    p.require("exam.read")
    return exams.exam_settings(db, p.org_id, exam_id)


@router.patch("/exams/{exam_id}/settings")
def patch_exam_settings(db: DB, p: OrgPrincipal, exam_id: UUID, body: SettingsPatchIn):
    p.require("exam.settings")
    return exams.patch_exam_settings(db, p, exam_id, body.overrides, body.confirm_shorten)


# ------------------------------------------------------------------ enrollments & invitations
@router.get("/exams/{exam_id}/enrollments", response_model=list[OrgEnrollmentOut])
def exam_enrollments(db: DB, p: OrgPrincipal, exam_id: UUID):
    p.require("exam.read")
    exams.get_exam(db, p.org_id, exam_id)
    return registration.org_enrollments(db, p.org_id, exam_id)


@router.patch("/enrollments/{enrollment_id}")
def patch_enrollment(db: DB, p: OrgPrincipal, enrollment_id: UUID, body: EnrollmentPatchIn):
    p.require("enrollment.manage")
    enr = registration.org_patch_enrollment(db, p, enrollment_id, body.time_accommodation_minutes)
    return {"id": enr.id, "time_accommodation_minutes": enr.time_accommodation_minutes}


@router.post("/enrollments/{enrollment_id}/cancel")
def cancel_enrollment(db: DB, p: OrgPrincipal, enrollment_id: UUID, reason: Reason):
    p.require("enrollment.manage")
    enr = registration.org_cancel_enrollment(db, p, enrollment_id, reason)
    return {"id": enr.id, "status": enr.status}


@router.post("/exams/{exam_id}/invitations", response_model=InvitationsCreateOut,
             status_code=status.HTTP_201_CREATED)
def invite(db: DB, p: OrgPrincipal, exam_id: UUID, body: InvitationsCreateIn):
    p.require("invitation.manage")
    return registration.create_invitations(db, p, exam_id, [str(e) for e in body.emails], body.expires_in_days)


@router.get("/exams/{exam_id}/invitations", response_model=list[InvitationOut])
def list_invitations(db: DB, p: OrgPrincipal, exam_id: UUID):
    p.require("invitation.manage")
    return registration.list_invitations(db, p.org_id, exam_id)


@router.post("/invitations/{invitation_id}/revoke", response_model=InvitationOut)
def revoke_invitation(db: DB, p: OrgPrincipal, invitation_id: UUID):
    p.require("invitation.manage")
    return registration.revoke_invitation(db, p, invitation_id)
