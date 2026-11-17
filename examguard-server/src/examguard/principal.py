"""The authenticated caller of a request."""
from dataclasses import dataclass, field
from uuid import UUID

from .errors import forbidden


@dataclass(frozen=True)
class Principal:
    kind: str                     # STAFF | CANDIDATE | PLATFORM | ANONYMOUS
    id: UUID | None = None
    email: str | None = None
    org_id: UUID | None = None
    roles: frozenset[str] = field(default_factory=frozenset)
    permissions: frozenset[str] = field(default_factory=frozenset)

    @property
    def actor_kind(self) -> str:
        return {"STAFF": "staff", "CANDIDATE": "candidate", "PLATFORM": "platform"}.get(self.kind, "system")

    def require(self, permission: str) -> None:
        if permission not in self.permissions:
            raise forbidden(f"missing permission {permission}")
