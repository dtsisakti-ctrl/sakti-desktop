"""Request-scoped database session and authentication dependencies.

Every request runs in ONE transaction whose RLS context is set before any business query.
The session dependency uses scope="function", so the commit happens before the response
is sent — a client never observes a 2xx for work that later failed to commit.
"""
from collections.abc import Iterator
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import elevated, new_session, set_context
from ..errors import AppError, forbidden
from ..models import Candidate, Membership, User
from ..permissions import permissions_for
from ..principal import Principal
from ..services import auth


def get_db() -> Iterator[Session]:
    db = new_session()
    db.begin()
    set_context(db, "public")
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


DB = Annotated[Session, Depends(get_db, scope="function")]


# Declared as OpenAPI security schemes (not plain header parameters): Swagger UI never sends a
# header named "Authorization" that is defined as a parameter, so /docs needs the Authorize button.
_bearer_scheme = HTTPBearer(auto_error=False, scheme_name="SessionToken",
                            description="Token from POST /auth/login (paste it without the word 'Bearer').")
_org_scheme = APIKeyHeader(name="X-Org-Id", auto_error=False, scheme_name="OrgId",
                           description="Active organization id (see GET /api/v1/staff/me).")


def bearer(cred: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)] = None) -> str | None:
    return cred.credentials.strip() if cred and cred.credentials.strip() else None


Token = Annotated[str | None, Depends(bearer)]


def current_candidate(db: DB, token: Token) -> Candidate:
    cid = auth.resolve_session(db, token, "CANDIDATE")
    with elevated(db):
        cand = db.get(Candidate, cid)
    if cand is None or not cand.is_active:
        raise auth.UNAUTHORIZED
    set_context(db, "candidate", candidate_id=cand.id)
    return cand


def _staff_user(db: Session, token: str | None) -> User:
    uid = auth.resolve_session(db, token, "STAFF")
    with elevated(db):
        user = db.get(User, uid)
    if user is None or not user.is_active:
        raise auth.UNAUTHORIZED
    return user


def current_staff_user(db: DB, token: Token) -> User:
    """Authenticated staff user without an organization context (/staff/me)."""
    user = _staff_user(db, token)
    set_context(db, "staff", user_id=user.id)
    return user


def org_principal(
    db: DB, token: Token, org_header: Annotated[str | None, Depends(_org_scheme)] = None
) -> Principal:
    user = _staff_user(db, token)
    if not org_header:
        raise AppError(400, "ORG_REQUIRED", "X-Org-Id header is required")
    try:
        x_org_id = UUID(org_header.strip())
    except ValueError:
        raise AppError(422, "VALIDATION_ERROR", "X-Org-Id must be a UUID") from None
    with elevated(db):
        roles = set(db.scalars(select(Membership.role).where(
            Membership.user_id == user.id, Membership.org_id == x_org_id)))
    if not roles:
        raise forbidden("you are not a member of this organization")
    set_context(db, "staff", org_id=x_org_id, user_id=user.id)
    return Principal(kind="STAFF", id=user.id, email=user.email, org_id=x_org_id,
                     roles=frozenset(roles), permissions=permissions_for(roles))


def platform_principal(db: DB, token: Token) -> Principal:
    user = _staff_user(db, token)
    if not user.is_platform_admin:
        raise forbidden("platform administrator only")
    set_context(db, "platform", user_id=user.id)
    return Principal(kind="PLATFORM", id=user.id, email=user.email)


CurrentCandidate = Annotated[Candidate, Depends(current_candidate)]
CurrentStaffUser = Annotated[User, Depends(current_staff_user)]
OrgPrincipal = Annotated[Principal, Depends(org_principal)]
PlatformPrincipal = Annotated[Principal, Depends(platform_principal)]
