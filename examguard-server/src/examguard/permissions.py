"""Role -> permission mapping for organization staff (PRD §7).

ORG_ADMIN and EXAM_ADMIN permissions apply to every exam of the organization. INVIGILATOR
permissions apply only to exams the invigilator is assigned to (see services/access.py).
"""
ROLES = ("ORG_ADMIN", "EXAM_ADMIN", "INVIGILATOR")

# Attempt-level permissions (Phase 1b)
MONITOR = "attempt.monitor"            # see candidates, attempts, transitions
CONTROL = "attempt.control"            # warning, pause/resume, add time
REENTRY = "attempt.reentry"            # allow/reject re-entry
FORCE_SUBMIT = "attempt.force_submit"
TERMINATE = "attempt.terminate"
IDENTITY = "identity.review"
REOPEN = "attempt.reopen"              # reopen & reinstate
BULK_TERMINATE = "attempt.bulk_terminate"
EXTEND = "exam.extend"
FINALIZE = "exam.finalize"
ASSIGN = "invigilator.assign"
INTEGRATIONS = "org.integrations"     # manage LMS integrations (Phase 1c-2)

_INVIGILATE = frozenset({MONITOR, CONTROL, REENTRY, FORCE_SUBMIT, TERMINATE, IDENTITY})

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "ORG_ADMIN": frozenset({"org.members", "org.settings", "org.audit", "exam.read", MONITOR, INTEGRATIONS}),
    "EXAM_ADMIN": frozenset({
        "exam.read", "exam.write", "exam.publish", "enrollment.manage", "invitation.manage",
        "exam.settings", "org.audit",
        REOPEN, BULK_TERMINATE, EXTEND, FINALIZE, ASSIGN,
    }) | _INVIGILATE,
    "INVIGILATOR": _INVIGILATE,
}

# Roles whose permissions cover every exam in the organization.
UNSCOPED_ROLES = frozenset({"ORG_ADMIN", "EXAM_ADMIN"})


def permissions_for(roles: set[str] | frozenset[str]) -> frozenset[str]:
    out: set[str] = set()
    for r in roles:
        out |= ROLE_PERMISSIONS.get(r, frozenset())
    return frozenset(out)


def unscoped_permissions(roles: set[str] | frozenset[str]) -> frozenset[str]:
    return permissions_for({r for r in roles if r in UNSCOPED_ROLES})
