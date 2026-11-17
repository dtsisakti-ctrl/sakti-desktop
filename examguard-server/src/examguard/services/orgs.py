"""Organizations, staff membership, and settings administration."""
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import audit, settings_service
from ..db import elevated
from ..errors import conflict, invalid, not_found
from ..models import AuditLog, Membership, Organization, PlatformSettings, User
from ..principal import Principal
from ..security import hash_password
from .auth import check_password_strength


# ------------------------------------------------------------------ users
def get_or_create_user(
    db: Session, email: str, full_name: str | None, password: str | None,
    *, platform_admin: bool = False,
) -> tuple[User, bool]:
    """Look up a staff user globally (system context), creating it if needed."""
    with elevated(db):
        user = db.scalar(select(User).where(func.lower(User.email) == email.lower()))
        if user is not None:
            if platform_admin and not user.is_platform_admin:
                user.is_platform_admin = True
            return user, False
        if not full_name or not password:
            raise invalid("USER_DETAILS_REQUIRED",
                          "full_name and initial password are required for a new staff account")
        check_password_strength(password)
        user = User(email=email, full_name=full_name, password_hash=hash_password(password),
                    is_platform_admin=platform_admin)
        db.add(user)
        db.flush()
        return user, True


# ------------------------------------------------------------------ organizations (platform)
def create_org(db: Session, actor: Principal, *, slug: str, name: str, can_publish_public: bool,
               admin_email: str | None = None, admin_full_name: str | None = None,
               admin_password: str | None = None) -> Organization:
    if db.scalar(select(Organization.id).where(Organization.slug == slug)):
        raise conflict("SLUG_TAKEN", f"organization slug '{slug}' is already used")
    org = Organization(slug=slug, name=name, can_publish_public=can_publish_public, settings={})
    db.add(org)
    db.flush()
    audit.record(db, org_id=None, actor_kind=actor.actor_kind, actor_id=actor.id,
                 action="organization.created", target_type="organization", target_id=org.id,
                 data={"slug": slug, "can_publish_public": can_publish_public})
    if admin_email:
        user, _ = get_or_create_user(db, admin_email, admin_full_name, admin_password)
        db.add(Membership(org_id=org.id, user_id=user.id, role="ORG_ADMIN"))
        db.flush()
        audit.record(db, org_id=org.id, actor_kind=actor.actor_kind, actor_id=actor.id,
                     action="member.added", target_type="user", target_id=user.id,
                     data={"email": user.email, "role": "ORG_ADMIN"})
    return org


def patch_org(db: Session, actor: Principal, org_id: UUID, *, name: str | None,
              can_publish_public: bool | None) -> Organization:
    org = db.get(Organization, org_id)
    if org is None:
        raise not_found("organization")
    changes: dict[str, Any] = {}
    if name is not None and name != org.name:
        changes["name"] = [org.name, name]
        org.name = name
    if can_publish_public is not None and can_publish_public != org.can_publish_public:
        changes["can_publish_public"] = [org.can_publish_public, can_publish_public]
        org.can_publish_public = can_publish_public
    if changes:
        audit.record(db, org_id=None, actor_kind=actor.actor_kind, actor_id=actor.id,
                     action="organization.updated", target_type="organization", target_id=org.id,
                     data=changes)
    return org


def get_org_by_slug(db: Session, slug: str) -> Organization:
    org = db.scalar(select(Organization).where(Organization.slug == slug))
    if org is None:
        raise not_found("organization")
    return org


# ------------------------------------------------------------------ members (org admin)
def list_members(db: Session, org_id: UUID) -> list[tuple[Membership, User]]:
    rows = db.execute(
        select(Membership, User).join(User, User.id == Membership.user_id)
        .where(Membership.org_id == org_id).order_by(User.email, Membership.role)
    ).all()
    return [(m, u) for m, u in rows]


def add_member(db: Session, actor: Principal, *, email: str, role: str, full_name: str | None,
               initial_password: str | None) -> tuple[Membership, User]:
    user, _ = get_or_create_user(db, email, full_name, initial_password)
    m = Membership(org_id=actor.org_id, user_id=user.id, role=role)
    db.add(m)
    try:
        db.flush()
    except IntegrityError:
        raise conflict("ALREADY_MEMBER", "user already has this role in the organization") from None
    audit.record(db, org_id=actor.org_id, actor_kind=actor.actor_kind, actor_id=actor.id,
                 action="member.added", target_type="user", target_id=user.id,
                 data={"email": user.email, "role": role})
    return m, user


def remove_member(db: Session, actor: Principal, membership_id: UUID) -> None:
    m = db.scalar(select(Membership).where(Membership.id == membership_id,
                                           Membership.org_id == actor.org_id))
    if m is None:
        raise not_found("membership")
    if m.role == "ORG_ADMIN":
        admins = db.scalar(select(func.count()).select_from(Membership).where(
            Membership.org_id == actor.org_id, Membership.role == "ORG_ADMIN"))
        if admins <= 1:
            raise conflict("LAST_ORG_ADMIN", "an organization must keep at least one ORG_ADMIN")
    db.delete(m)
    audit.record(db, org_id=actor.org_id, actor_kind=actor.actor_kind, actor_id=actor.id,
                 action="member.removed", target_type="user", target_id=m.user_id,
                 data={"role": m.role})


# ------------------------------------------------------------------ settings
def org_settings(db: Session, org_id: UUID) -> dict[str, Any]:
    org = db.get(Organization, org_id)
    return {"overrides": org.settings, "effective": settings_service.resolve(db, org)}


def patch_org_settings(db: Session, actor: Principal, overrides: dict[str, Any],
                       confirm_shorten: bool) -> dict[str, Any]:
    org = db.get(Organization, actor.org_id)
    settings_service.validate_overrides(db, overrides, allowed=None)
    before = settings_service.resolve(db, org)
    org.settings = settings_service.merge(org.settings, overrides)
    after = settings_service.resolve(db, org)
    shortened = settings_service.check_retention_shortening(before, after, confirm_shorten)
    db.flush()
    audit.record(db, org_id=org.id, actor_kind=actor.actor_kind, actor_id=actor.id,
                 action="settings.updated", target_type="organization", target_id=org.id,
                 data={"patch": overrides, "retention_shortened": shortened})
    return {"overrides": org.settings, "effective": after}


def get_platform_settings(db: Session) -> dict[str, Any]:
    return settings_service.platform(db)


def put_platform_settings(db: Session, actor: Principal, doc: dict[str, Any]) -> dict[str, Any]:
    settings_service.validate_platform_document(doc)
    row = db.get(PlatformSettings, 1)
    old = row.settings
    row.settings = doc
    audit.record(db, org_id=None, actor_kind=actor.actor_kind, actor_id=actor.id,
                 action="platform_settings.updated", target_type="platform_settings", target_id="1",
                 data={"before": old, "after": doc})
    return doc


# ------------------------------------------------------------------ audit
def list_audit(db: Session, org_id: UUID, limit: int, before_seq: int | None) -> list[AuditLog]:
    q = select(AuditLog).where(AuditLog.org_id == org_id)
    if before_seq is not None:
        q = q.where(AuditLog.seq < before_seq)
    return list(db.scalars(q.order_by(AuditLog.seq.desc()).limit(limit)))
