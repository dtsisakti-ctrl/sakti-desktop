"""ORM mapping. The schema itself is owned by migrations/sql; nothing here creates tables."""
from datetime import datetime
from uuid import UUID

from sqlalchemy import ARRAY, BigInteger, Boolean, DateTime, FetchedValue, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    # Fetch trigger/server-generated values (org_id, ids) with RETURNING on insert.
    __mapper_args__ = {"eager_defaults": True}


def _ts(**kw) -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), **kw)


class PlatformSettings(Base):
    __tablename__ = "platform_settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    settings: Mapped[dict] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = _ts(server_default=func.now())


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    slug: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    can_publish_public: Mapped[bool] = mapped_column(Boolean, default=False)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = _ts(server_default=func.now())


class User(Base):
    __tablename__ = "users"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    email: Mapped[str] = mapped_column(String)
    full_name: Mapped[str] = mapped_column(String)
    password_hash: Mapped[str] = mapped_column(String)
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = _ts(server_default=func.now())


class Membership(Base):
    __tablename__ = "memberships"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    org_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = _ts(server_default=func.now())


class Candidate(Base):
    __tablename__ = "candidates"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    email: Mapped[str] = mapped_column(String)
    full_name: Mapped[str] = mapped_column(String)
    password_hash: Mapped[str] = mapped_column(String)
    email_verified_at: Mapped[datetime | None] = _ts(nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = _ts(server_default=func.now())


class OneTimeToken(Base):
    __tablename__ = "one_time_tokens"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    token_hash: Mapped[str] = mapped_column(String)
    purpose: Mapped[str] = mapped_column(String)
    subject_id: Mapped[UUID]
    expires_at: Mapped[datetime] = _ts()
    used_at: Mapped[datetime | None] = _ts(nullable=True)
    created_at: Mapped[datetime] = _ts(server_default=func.now())


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    token_hash: Mapped[str] = mapped_column(String)
    subject_kind: Mapped[str] = mapped_column(String)
    subject_id: Mapped[UUID]
    created_at: Mapped[datetime] = _ts(server_default=func.now())
    expires_at: Mapped[datetime] = _ts()
    revoked_at: Mapped[datetime | None] = _ts(nullable=True)


class Exam(Base):
    __tablename__ = "exams"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    org_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    code: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    series: Mapped[str | None] = mapped_column(String, nullable=True)
    visibility: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="DRAFT")
    exam_url: Mapped[str | None] = mapped_column(String, nullable=True)
    allowed_origins: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    window_start: Mapped[datetime | None] = _ts(nullable=True)
    latest_start: Mapped[datetime | None] = _ts(nullable=True)
    window_end: Mapped[datetime | None] = _ts(nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    late_start_policy: Mapped[str] = mapped_column(String, default="FIXED_END")
    checkin_open: Mapped[datetime | None] = _ts(nullable=True)
    identity_check: Mapped[str] = mapped_column(String, default="NONE")
    registration_open: Mapped[datetime | None] = _ts(nullable=True)
    registration_close: Mapped[datetime | None] = _ts(nullable=True)
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    registered_count: Mapped[int] = mapped_column(Integer, default=0)
    access_code_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    integration_level: Mapped[int] = mapped_column(Integer, default=2)
    min_client_version: Mapped[str | None] = mapped_column(String, nullable=True)
    policy: Mapped[dict] = mapped_column(JSONB, default=dict)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    extension_minutes: Mapped[int] = mapped_column(Integer, default=0)
    running_at: Mapped[datetime | None] = _ts(nullable=True)
    closed_at: Mapped[datetime | None] = _ts(nullable=True)
    finalized_at: Mapped[datetime | None] = _ts(nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = _ts(server_default=func.now())
    updated_at: Mapped[datetime] = _ts(server_default=func.now())


class Enrollment(Base):
    __tablename__ = "enrollments"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    # org_id is filled by a database trigger from the exam; never set it from user input.
    org_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True, server_default=FetchedValue()
    )
    exam_id: Mapped[UUID] = mapped_column(ForeignKey("exams.id"))
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("candidates.id"))
    source: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="CONFIRMED")
    time_accommodation_minutes: Mapped[int] = mapped_column(Integer, default=0)
    external_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    integration_id: Mapped[UUID | None] = mapped_column(ForeignKey("integrations.id"), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = _ts(server_default=func.now())
    cancelled_at: Mapped[datetime | None] = _ts(nullable=True)

    exam: Mapped[Exam] = relationship(lazy="joined")
    candidate: Mapped[Candidate] = relationship(lazy="select")


class Attempt(Base):
    __tablename__ = "attempts"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    org_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True, server_default=FetchedValue()
    )
    enrollment_id: Mapped[UUID] = mapped_column(ForeignKey("enrollments.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String, default="NOT_STARTED")
    state_version: Mapped[int] = mapped_column(BigInteger, default=0)
    started_at: Mapped[datetime | None] = _ts(nullable=True)
    deadline: Mapped[datetime | None] = _ts(nullable=True)
    paused_at: Mapped[datetime | None] = _ts(nullable=True)
    pause_timer_mode: Mapped[str | None] = mapped_column(String, nullable=True)
    ended_at: Mapped[datetime | None] = _ts(nullable=True)
    final_status: Mapped[str | None] = mapped_column(String, nullable=True)
    reopen_count: Mapped[int] = mapped_column(Integer, default=0)
    reinstate_count: Mapped[int] = mapped_column(Integer, default=0)
    termination_reason_category: Mapped[str | None] = mapped_column(String, nullable=True)
    identity_status: Mapped[str] = mapped_column(String, default="NONE")
    identity_rejections: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    result_at: Mapped[datetime | None] = _ts(nullable=True)
    unlock_secret_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = _ts(server_default=func.now())
    updated_at: Mapped[datetime] = _ts(server_default=func.now())

    enrollment: Mapped[Enrollment] = relationship(lazy="select")


class Invitation(Base):
    __tablename__ = "invitations"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    org_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True, server_default=FetchedValue()
    )
    exam_id: Mapped[UUID] = mapped_column(ForeignKey("exams.id"))
    email: Mapped[str] = mapped_column(String)
    token_hash: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="PENDING")
    expires_at: Mapped[datetime] = _ts()
    accepted_enrollment_id: Mapped[UUID | None] = mapped_column(ForeignKey("enrollments.id"), nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = _ts(server_default=func.now())


class EmailOutbox(Base):
    __tablename__ = "email_outbox"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    to_email: Mapped[str] = mapped_column(String)
    template: Mapped[str] = mapped_column(String)
    subject: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = _ts(server_default=func.now())
    sent_at: Mapped[datetime | None] = _ts(nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chain_key: Mapped[str] = mapped_column(String)
    seq: Mapped[int] = mapped_column(BigInteger)
    org_id: Mapped[UUID | None] = mapped_column(nullable=True)
    occurred_at: Mapped[datetime] = _ts()
    actor_kind: Mapped[str] = mapped_column(String)
    actor_id: Mapped[UUID | None] = mapped_column(nullable=True)
    action: Mapped[str] = mapped_column(String)
    target_type: Mapped[str | None] = mapped_column(String, nullable=True)
    target_id: Mapped[str | None] = mapped_column(String, nullable=True)
    data: Mapped[dict] = mapped_column(JSONB)
    prev_hash: Mapped[str] = mapped_column(String)
    hash: Mapped[str] = mapped_column(String)


class StateTransition(Base):
    __tablename__ = "state_transitions"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    org_id: Mapped[UUID | None] = mapped_column(nullable=True, server_default=FetchedValue())
    attempt_id: Mapped[UUID] = mapped_column(ForeignKey("attempts.id", ondelete="CASCADE"))
    state_version: Mapped[int] = mapped_column(BigInteger)
    from_status: Mapped[str] = mapped_column(String)
    to_status: Mapped[str] = mapped_column(String)
    trigger: Mapped[str] = mapped_column(String)
    actor_kind: Mapped[str] = mapped_column(String)
    actor_id: Mapped[UUID | None] = mapped_column(nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason_category: Mapped[str | None] = mapped_column(String, nullable=True)
    old_deadline: Mapped[datetime | None] = _ts(nullable=True)
    new_deadline: Mapped[datetime | None] = _ts(nullable=True)
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    occurred_at: Mapped[datetime] = _ts()


class DeviceSession(Base):
    __tablename__ = "device_sessions"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    org_id: Mapped[UUID | None] = mapped_column(nullable=True, server_default=FetchedValue())
    attempt_id: Mapped[UUID] = mapped_column(ForeignKey("attempts.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String)
    public_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_version: Mapped[str | None] = mapped_column(String, nullable=True)
    os_info: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = _ts()
    activated_at: Mapped[datetime | None] = _ts(nullable=True)
    revoked_at: Mapped[datetime | None] = _ts(nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = _ts(nullable=True)
    last_heartbeat_seq: Mapped[int] = mapped_column(BigInteger, default=0)
    connection_closed_at: Mapped[datetime | None] = _ts(nullable=True)


class Command(Base):
    __tablename__ = "commands"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    org_id: Mapped[UUID | None] = mapped_column(nullable=True, server_default=FetchedValue())
    attempt_id: Mapped[UUID] = mapped_column(ForeignKey("attempts.id", ondelete="CASCADE"))
    device_session_id: Mapped[UUID | None] = mapped_column(ForeignKey("device_sessions.id"), nullable=True)
    type: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    state_version: Mapped[int] = mapped_column(BigInteger)
    issued_by: Mapped[UUID | None] = mapped_column(nullable=True)
    issued_at: Mapped[datetime] = _ts()
    expires_at: Mapped[datetime] = _ts()
    delivery_status: Mapped[str] = mapped_column(String, default="PENDING")
    delivered_at: Mapped[datetime | None] = _ts(nullable=True)
    ack_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    envelope: Mapped[str | None] = mapped_column(Text, nullable=True)


class InvigilatorAssignment(Base):
    __tablename__ = "invigilator_assignments"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    org_id: Mapped[UUID | None] = mapped_column(nullable=True, server_default=FetchedValue())
    exam_id: Mapped[UUID] = mapped_column(ForeignKey("exams.id"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_by: Mapped[UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = _ts(server_default=func.now())


class ServerKey(Base):
    __tablename__ = "server_keys"
    kid_base: Mapped[str] = mapped_column(String, primary_key=True)
    uses: Mapped[list[str]] = mapped_column(ARRAY(Text))
    public_key: Mapped[str] = mapped_column(Text)
    private_key_enc: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default="ACTIVE")
    not_before: Mapped[datetime] = _ts()
    not_after: Mapped[datetime] = _ts()
    created_at: Mapped[datetime] = _ts(server_default=func.now())


class KeySet(Base):
    __tablename__ = "key_sets"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    envelope: Mapped[str] = mapped_column(Text)
    issued_at: Mapped[datetime] = _ts()
    created_at: Mapped[datetime] = _ts(server_default=func.now())


class LaunchToken(Base):
    __tablename__ = "launch_tokens"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    org_id: Mapped[UUID | None] = mapped_column(nullable=True, server_default=FetchedValue())
    attempt_id: Mapped[UUID] = mapped_column(ForeignKey("attempts.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = _ts()
    expires_at: Mapped[datetime] = _ts()
    used_at: Mapped[datetime | None] = _ts(nullable=True)
    used_by_device_session: Mapped[UUID | None] = mapped_column(nullable=True)


class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    org_id: Mapped[UUID | None] = mapped_column(nullable=True, server_default=FetchedValue())
    attempt_id: Mapped[UUID] = mapped_column(ForeignKey("attempts.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String)
    severity: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="OPEN")
    started_at: Mapped[datetime] = _ts()
    ended_at: Mapped[datetime | None] = _ts(nullable=True)
    event_count: Mapped[int] = mapped_column(Integer, default=1)
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    reviewed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = _ts(nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = _ts(server_default=func.now())


class Event(Base):
    __tablename__ = "events"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    org_id: Mapped[UUID | None] = mapped_column(nullable=True, server_default=FetchedValue())
    attempt_id: Mapped[UUID] = mapped_column(ForeignKey("attempts.id", ondelete="CASCADE"))
    device_session_id: Mapped[UUID] = mapped_column(ForeignKey("device_sessions.id"))
    seq: Mapped[int] = mapped_column(BigInteger)
    type: Mapped[str] = mapped_column(String)
    phase: Mapped[str] = mapped_column(String)
    started_at: Mapped[datetime] = _ts()
    ended_at: Mapped[datetime | None] = _ts(nullable=True)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    evidence_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String)
    incident_id: Mapped[UUID | None] = mapped_column(ForeignKey("incidents.id"), nullable=True)
    received_at: Mapped[datetime] = _ts()


class Integration(Base):
    __tablename__ = "integrations"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    org_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    name: Mapped[str] = mapped_column(String)
    client_id: Mapped[str] = mapped_column(String)
    secret_hash: Mapped[str] = mapped_column(String)
    webhook_url: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="ACTIVE")
    created_by: Mapped[UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = _ts(server_default=func.now())
    last_used_at: Mapped[datetime | None] = _ts(nullable=True)


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    org_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    integration_id: Mapped[UUID] = mapped_column(ForeignKey("integrations.id", ondelete="CASCADE"))
    attempt_id: Mapped[UUID | None] = mapped_column(ForeignKey("attempts.id", ondelete="CASCADE"), nullable=True)
    event_type: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String, default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = _ts()
    last_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = _ts()
    delivered_at: Mapped[datetime | None] = _ts(nullable=True)


class IdentityPhoto(Base):
    __tablename__ = "identity_photos"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    org_id: Mapped[UUID | None] = mapped_column(nullable=True, server_default=FetchedValue())
    attempt_id: Mapped[UUID] = mapped_column(ForeignKey("attempts.id", ondelete="CASCADE"))
    submission: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String)
    storage_key: Mapped[str] = mapped_column(String)
    content_type: Mapped[str] = mapped_column(String)
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = _ts()


class BackupCode(Base):
    __tablename__ = "backup_codes"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    org_id: Mapped[UUID | None] = mapped_column(nullable=True, server_default=FetchedValue())
    exam_id: Mapped[UUID] = mapped_column(ForeignKey("exams.id"))
    batch_id: Mapped[UUID] = mapped_column()
    code_hash: Mapped[str] = mapped_column(String)
    created_by: Mapped[UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = _ts()
    used_at: Mapped[datetime | None] = _ts(nullable=True)
    used_by_attempt: Mapped[UUID | None] = mapped_column(nullable=True)
