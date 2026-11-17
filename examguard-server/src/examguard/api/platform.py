"""Platform administration (Platform Admin only)."""
from uuid import UUID

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from .. import audit
from ..models import Organization
from ..schemas import OrgCreateIn, OrgOut, OrgPatchIn, PlatformSettingsIn
from ..services import orgs
from .deps import DB, PlatformPrincipal

router = APIRouter(prefix="/api/v1/platform", tags=["platform"])


@router.get("/organizations", response_model=list[OrgOut])
def list_orgs(db: DB, p: PlatformPrincipal):
    return list(db.scalars(select(Organization).order_by(Organization.slug)))


@router.post("/organizations", response_model=OrgOut, status_code=status.HTTP_201_CREATED)
def create_org(db: DB, p: PlatformPrincipal, body: OrgCreateIn):
    return orgs.create_org(db, p, slug=body.slug, name=body.name, can_publish_public=body.can_publish_public,
                           admin_email=body.admin_email, admin_full_name=body.admin_full_name,
                           admin_password=body.admin_password)


@router.patch("/organizations/{org_id}", response_model=OrgOut)
def patch_org(db: DB, p: PlatformPrincipal, org_id: UUID, body: OrgPatchIn):
    return orgs.patch_org(db, p, org_id, name=body.name, can_publish_public=body.can_publish_public)


@router.get("/settings")
def get_settings(db: DB, p: PlatformPrincipal):
    return orgs.get_platform_settings(db)


@router.put("/settings")
def put_settings(db: DB, p: PlatformPrincipal, body: PlatformSettingsIn):
    return orgs.put_platform_settings(db, p, body.model_dump())


@router.get("/audit-log/verify")
def verify_chain(db: DB, p: PlatformPrincipal, chain: str = Query("platform", max_length=60)):
    return audit.verify(db, chain)
