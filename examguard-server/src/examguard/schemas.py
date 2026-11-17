"""Request/response schemas. All datetimes must be timezone-aware."""
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, EmailStr, Field

Visibility = Literal["PRIVATE", "PUBLIC"]
LateStartPolicy = Literal["FIXED_END", "FULL_DURATION"]
IdentityCheck = Literal["NONE", "MANUAL"]
Role = Literal["ORG_ADMIN", "EXAM_ADMIN", "INVIGILATOR"]


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ------------------------------------------------------------------ auth
class CandidateSignupIn(_In):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)
    full_name: str = Field(min_length=1, max_length=200)


class LoginIn(_In):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class TokenIn(_In):
    token: str = Field(min_length=10, max_length=200)


class ResendVerificationIn(_In):
    email: EmailStr


class PasswordResetIn(_In):
    token: str = Field(min_length=10, max_length=200)
    password: str = Field(min_length=1, max_length=256)


class PasswordChangeIn(_In):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


class ProfileIn(_In):
    full_name: str = Field(min_length=1, max_length=200)


class SessionOut(BaseModel):
    token: str
    kind: Literal["STAFF", "CANDIDATE"]
    expires_at: datetime


class CandidateOut(_Out):
    id: UUID
    email: str
    full_name: str
    email_verified_at: datetime | None


class MembershipSummary(BaseModel):
    org_id: UUID
    org_slug: str
    org_name: str
    roles: list[str]


class StaffMeOut(BaseModel):
    id: UUID
    email: str
    full_name: str
    is_platform_admin: bool
    memberships: list[MembershipSummary]


# ------------------------------------------------------------------ organizations & members
class OrgCreateIn(_In):
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")
    name: str = Field(min_length=1, max_length=200)
    can_publish_public: bool = False
    admin_email: EmailStr | None = None
    admin_full_name: str | None = Field(default=None, max_length=200)
    admin_password: str | None = Field(default=None, max_length=256)


class OrgPatchIn(_In):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    can_publish_public: bool | None = None


class OrgOut(_Out):
    id: UUID
    slug: str
    name: str
    can_publish_public: bool


class MemberAddIn(_In):
    email: EmailStr
    role: Role
    full_name: str | None = Field(default=None, max_length=200)
    initial_password: str | None = Field(default=None, max_length=256)


class MemberOut(BaseModel):
    membership_id: UUID
    user_id: UUID
    email: str
    full_name: str
    role: str


# ------------------------------------------------------------------ settings
class SettingsPatchIn(_In):
    overrides: dict[str, Any]
    confirm_shorten: bool = False


class PlatformSettingsIn(_In):
    defaults: dict[str, Any]
    bounds: dict[str, list[int]]
    choices: dict[str, list[str]] = {}


# ------------------------------------------------------------------ exams
class SecurityPolicy(_In):
    fullscreen: bool = True
    block_app_switching: bool = True
    disable_clipboard: bool = True
    disable_screenshots: bool = True
    block_additional_monitors: bool = True
    monitor_applications: bool = True
    allowed_applications: list[str] = []
    block_remote_access: bool = True
    block_virtual_machines: bool = False  # MVP: warn-only (PRD §13.3)
    block_wsl: bool = False               # roadmap
    require_camera: bool = True
    require_microphone: bool = True
    person_detection: bool = True
    face_detection: bool = True
    voice_activity_detection: bool = True
    evidence_snapshot: bool = False
    inference_fps: int = Field(default=2, ge=1, le=5)
    min_lockdown_level: Literal["STRICT", "STANDARD", "RELAXED"] = "STANDARD"


class _ExamFields(_In):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    series: str | None = Field(default=None, max_length=100)
    exam_url: str | None = Field(default=None, max_length=2000)
    allowed_origins: list[str] | None = None
    window_start: AwareDatetime | None = None
    latest_start: AwareDatetime | None = None
    window_end: AwareDatetime | None = None
    duration_minutes: int | None = Field(default=None, gt=0, le=24 * 60)
    late_start_policy: LateStartPolicy | None = None
    checkin_open: AwareDatetime | None = None
    identity_check: IdentityCheck | None = None
    registration_open: AwareDatetime | None = None
    registration_close: AwareDatetime | None = None
    capacity: int | None = Field(default=None, gt=0, le=100_000)
    access_code: str | None = Field(default=None, min_length=4, max_length=64)
    integration_level: Literal[0, 2] | None = None
    min_client_version: str | None = Field(default=None, pattern=r"^\d+\.\d+\.\d+$")
    policy: SecurityPolicy | None = None


class ExamCreateIn(_ExamFields):
    code: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
    name: str = Field(min_length=1, max_length=200)
    visibility: Visibility = "PRIVATE"


class ExamPatchIn(_ExamFields):
    visibility: Visibility | None = None


class ExamOut(_Out):
    id: UUID
    org_id: UUID
    code: str
    name: str
    description: str | None
    series: str | None
    visibility: str
    status: str
    exam_url: str | None
    allowed_origins: list[str]
    window_start: datetime | None
    latest_start: datetime | None
    window_end: datetime | None
    duration_minutes: int | None
    late_start_policy: str
    checkin_open: datetime | None
    identity_check: str
    registration_open: datetime | None
    registration_close: datetime | None
    capacity: int | None
    registered_count: int
    has_access_code: bool
    integration_level: int
    min_client_version: str | None
    policy: dict[str, Any]
    settings: dict[str, Any]
    extension_minutes: int = 0
    running_at: datetime | None = None
    closed_at: datetime | None = None
    finalized_at: datetime | None = None


class CatalogExamOut(BaseModel):
    id: UUID
    org_name: str
    code: str
    name: str
    description: str | None
    series: str | None
    window_start: datetime | None
    window_end: datetime | None
    duration_minutes: int | None
    registration_open: datetime | None
    registration_close: datetime | None
    registration_status: Literal["NOT_YET_OPEN", "OPEN", "CLOSED", "FULL"]
    seats_left: int | None
    requires_access_code: bool
    identity_check: str


# ------------------------------------------------------------------ enrollments & invitations
class RegisterIn(_In):
    access_code: str | None = Field(default=None, max_length=64)


class MoveIn(_In):
    target_exam_id: UUID
    access_code: str | None = Field(default=None, max_length=64)


class ExamSummary(BaseModel):
    id: UUID
    code: str
    name: str
    series: str | None
    visibility: str
    status: str
    window_start: datetime | None
    window_end: datetime | None
    checkin_open: datetime | None
    registration_close: datetime | None


class PortalExamSummary(ExamSummary):
    latest_start: datetime | None = None
    duration_minutes: int | None = None
    description: str | None = None
    identity_check: str | None = None
    org_name: str | None = None


class PortalAttempt(BaseModel):
    id: UUID
    status: str
    started_at: datetime | None
    deadline: datetime | None
    ended_at: datetime | None


class CandidateEnrollmentOut(BaseModel):
    id: UUID
    status: str
    source: str
    created_at: datetime
    cancelled_at: datetime | None
    attempt_status: str | None
    cancel_reason: str | None = None     # CANDIDATE_CANCELLED | MOVED | ORG_CANCELLED | ...
    attempt: PortalAttempt | None = None
    can_launch: bool = False
    launch_reason: str | None = None     # ENDED | EXAM_NOT_OPEN | NOT_YET_OPEN | LATE_START_CLOSED | NOT_ENROLLED
    can_change: bool = False             # cancel / move (self-registered, before registration_close)
    exam: PortalExamSummary


class InvitationPreviewOut(BaseModel):
    status: str                          # PENDING | ACCEPTED | REVOKED | EXPIRED
    email: str
    expires_at: datetime
    org_name: str
    exam_name: str
    exam_code: str
    window_start: datetime | None
    window_end: datetime | None
    account_exists: bool


class OrgEnrollmentOut(BaseModel):
    id: UUID
    candidate_id: UUID
    candidate_name: str
    candidate_email: str
    source: str
    status: str
    time_accommodation_minutes: int
    created_at: datetime
    cancelled_at: datetime | None
    cancel_reason: str | None


class EnrollmentPatchIn(_In):
    time_accommodation_minutes: int = Field(ge=0, le=600)


class InvitationsCreateIn(_In):
    emails: list[EmailStr] = Field(min_length=1, max_length=500)
    expires_in_days: int | None = Field(default=None, ge=1, le=90)


class InvitationOut(_Out):
    id: UUID
    exam_id: UUID
    email: str
    status: str
    expires_at: datetime
    created_at: datetime


class InvitationsCreateOut(BaseModel):
    created: list[InvitationOut]
    skipped: list[dict[str, str]]


class AuditEntryOut(_Out):
    seq: int
    occurred_at: datetime
    actor_kind: str
    actor_id: UUID | None
    action: str
    target_type: str | None
    target_id: str | None
    data: dict[str, Any]
    hash: str


# ------------------------------------------------------------------ attempts (Phase 1b)
TimerMode = Literal["KEEP_RUNNING", "PAUSE_TIMER"]
ReasonCategory = Literal["TECHNICAL", "ADMINISTRATIVE", "DISCIPLINARY"]
_Reason = Field(min_length=3, max_length=500)


class _ActionIn(_In):
    reason: str = _Reason
    # state_version the Admin Web displayed; a mismatch answers 409 STATE_CONFLICT.
    expected_state_version: int | None = Field(default=None, ge=0)


class WarningIn(_In):
    message: str = Field(min_length=1, max_length=1000)


class PauseIn(_ActionIn):
    timer_mode: TimerMode = "KEEP_RUNNING"


class ResumeIn(_ActionIn):
    pass


class AddTimeIn(_ActionIn):
    minutes: int = Field(ge=1, le=600)


class ForceSubmitIn(_ActionIn):
    pass


class TerminateIn(_ActionIn):
    reason_category: ReasonCategory


class AllowReentryIn(_ActionIn):
    pass


class RejectReentryIn(_ActionIn):
    reason_category: ReasonCategory


class ReopenIn(_ActionIn):
    deadline: AwareDatetime


class IdentityReviewIn(_In):
    reason: str | None = Field(default=None, max_length=500)


class ExtendIn(_In):
    minutes: int = Field(ge=1, le=600)
    reason: str = _Reason


class FinalizeIn(_In):
    reason: str | None = Field(default=None, max_length=500)


class BulkIn(_In):
    action: Literal["WARNING", "PAUSE", "RESUME", "ADD_TIME", "TERMINATE"]
    attempt_ids: list[UUID] = Field(min_length=1, max_length=1000)
    reason: str = _Reason
    message: str | None = Field(default=None, max_length=1000)
    minutes: int | None = Field(default=None, ge=1, le=600)
    timer_mode: TimerMode = "KEEP_RUNNING"
    reason_category: ReasonCategory | None = None
    confirm_exam_code: str | None = None


class AssignIn(_In):
    user_id: UUID


class AttemptActionOut(BaseModel):
    attempt_id: UUID
    status: str
    state_version: int
    deadline: datetime | None
    command_id: UUID | None = None
    note: str | None = None


class AttemptRowOut(BaseModel):
    attempt_id: UUID
    enrollment_id: UUID
    candidate_id: UUID
    candidate_name: str
    candidate_email: str
    status: str
    state_version: int
    connection_status: Literal["ONLINE", "OFFLINE"]
    last_seen_at: datetime | None
    started_at: datetime | None
    deadline: datetime | None
    remaining_seconds: int | None
    paused_at: datetime | None
    pause_timer_mode: str | None
    identity_status: str
    time_accommodation_minutes: int
    reopen_count: int
    reinstate_count: int
    termination_reason_category: str | None
    final_status: str | None
    open_incidents: int = 0
    health: dict[str, Any] = Field(default_factory=dict)
    client_version: str | None = None


class ExamAttemptsOut(BaseModel):
    exam_id: UUID
    exam_status: str
    server_time: datetime
    summary: dict[str, int]
    attempts: list[AttemptRowOut]


class AttemptDetailOut(AttemptRowOut):
    exam_id: UUID
    server_time: datetime
    available_actions: list[str]
    device_sessions: list[dict[str, Any]]
    transitions: list[dict[str, Any]]
    commands: list[dict[str, Any]]
    events: list[dict[str, Any]] = Field(default_factory=list)
    incidents: list[dict[str, Any]] = Field(default_factory=list)


class InvigilatorOut(BaseModel):
    user_id: UUID
    email: str
    full_name: str
    assigned_at: datetime


# ------------------------------------------------------------------ client protocol (Phase 1c)
class LaunchIn(_In):
    launch_token: str = Field(min_length=20, max_length=200)


class DeviceSessionIn(_In):
    launch_token: str = Field(min_length=20, max_length=200)
    public_key: str = Field(min_length=40, max_length=64, description="base64url raw Ed25519 public key")
    client_version: str = Field(max_length=32)
    os_info: dict[str, Any] = Field(default_factory=dict)
    preflight: dict[str, Any] = Field(default_factory=dict)


class ClientHeartbeatIn(_In):
    seq: int = Field(ge=1)
    last_state_version: int | None = Field(default=None, ge=0)
    health: dict[str, Any] = Field(default_factory=dict)
    recovery_cause: Literal["NETWORK_FAILURE", "UNEXPECTED_SHUTDOWN", "CLIENT_CRASH", "UNKNOWN"] | None = None


class ClientEventIn(_In):
    event_id: UUID
    seq: int = Field(ge=1)
    type: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,63}$")
    phase: Literal["OPEN", "CLOSE", "INSTANT"]
    started_at: AwareDatetime
    ended_at: AwareDatetime | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    evidence_ref: str | None = Field(default=None, max_length=500)
    device_session_id: UUID | None = None   # informational; the signed session is authoritative


class ClientEventsIn(_In):
    events: list[ClientEventIn] = Field(min_length=1, max_length=500)


class AckIn(_In):
    result: Literal["APPLIED", "STALE", "REJECTED"]
    reason: str | None = Field(default=None, max_length=200)


class LaunchLinkOut(BaseModel):
    launch_token: str
    launch_url: str
    expires_at: datetime
    attempt_id: UUID


# ------------------------------------------------------------------ integration (Phase 1c-2)
class IntegrationCreateIn(_In):
    name: str = Field(min_length=2, max_length=100)
    webhook_url: str | None = Field(default=None, max_length=500)


class IntegrationPatchIn(_In):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    webhook_url: str | None = Field(default=None, max_length=500)
    clear_webhook: bool = False


class IntegrationOut(BaseModel):
    id: UUID
    name: str
    client_id: str
    webhook_url: str | None
    status: str
    created_at: datetime
    last_used_at: datetime | None
    secret: str | None = Field(default=None, description="Shown only when created or rotated")


class IntegrationCandidateIn(_In):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    candidate_ref: str = Field(min_length=1, max_length=200, description="The candidate's id in the LMS")
    time_accommodation_minutes: int = Field(default=0, ge=0, le=600)


class IntegrationResultIn(_In):
    score: float | None = None
    max_score: float | None = None
    passed: bool | None = None
    details: dict[str, Any] = Field(default_factory=dict)


# ------------------------------------------------------------------ proctoring (Phase 1c-2)
class IdentityPhotosIn(_In):
    content_type: Literal["image/jpeg", "image/png", "image/webp"] = "image/jpeg"
    selfie: str = Field(min_length=10, max_length=4_200_000, description="base64 image")
    id_card: str = Field(min_length=10, max_length=4_200_000, description="base64 image")


class EmergencyUnlockIn(_In):
    reason: str = Field(min_length=3, max_length=500)


class UnlockResponseIn(_In):
    challenge: str = Field(pattern=r"^[A-Za-z2-7]{8}$", description="8 characters shown by the client")
    reason: str = Field(min_length=3, max_length=500)


class BackupCodesIn(_In):
    count: int = Field(default=20, ge=1, le=500)


class IncidentReviewIn(_In):
    status: Literal["REVIEWED", "DISMISSED", "ESCALATED"]
    note: str | None = Field(default=None, max_length=2000)
