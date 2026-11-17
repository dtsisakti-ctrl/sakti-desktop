-- ExamGuard Server — schema 0004 (Phase 1c-2): Integration API, webhooks, results.
-- Placeholder __APP_ROLE__ is replaced by the migration with the runtime role name.

-- ---------------------------------------------------------------- integrations (PRD §16.4)
CREATE TABLE integrations (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id        uuid NOT NULL REFERENCES organizations(id),
    name          text NOT NULL,
    client_id     text NOT NULL UNIQUE,
    secret_hash   text NOT NULL,                    -- sha256 of a 256-bit random secret
    webhook_url   text,
    status        text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'REVOKED')),
    created_by    uuid REFERENCES users(id),
    created_at    timestamptz NOT NULL DEFAULT now(),
    last_used_at  timestamptz
);
CREATE INDEX integrations_org_idx ON integrations (org_id);

ALTER TABLE enrollments ADD COLUMN integration_id uuid REFERENCES integrations(id);
CREATE UNIQUE INDEX enrollments_external_ref_uq ON enrollments (exam_id, external_ref)
    WHERE external_ref IS NOT NULL AND status = 'CONFIRMED';

-- ---------------------------------------------------------------- results (PRD §16.4)
ALTER TABLE attempts
    ADD COLUMN result     jsonb,
    ADD COLUMN result_at  timestamptz;

-- ---------------------------------------------------------------- webhook deliveries (PRD §16.6)
CREATE TABLE webhook_deliveries (
    id               uuid PRIMARY KEY,                 -- event_id, the receiver's idempotency key
    org_id           uuid NOT NULL REFERENCES organizations(id),
    integration_id   uuid NOT NULL REFERENCES integrations(id) ON DELETE CASCADE,
    attempt_id       uuid REFERENCES attempts(id) ON DELETE CASCADE,
    event_type       text NOT NULL,
    payload          jsonb NOT NULL,
    status           text NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'DELIVERED', 'FAILED')),
    attempts         int NOT NULL DEFAULT 0,
    next_attempt_at  timestamptz NOT NULL,
    last_status_code int,
    last_error       text,
    created_at       timestamptz NOT NULL,
    delivered_at     timestamptz
);
CREATE INDEX webhook_due_idx ON webhook_deliveries (next_attempt_at) WHERE status = 'PENDING';
CREATE INDEX webhook_integration_idx ON webhook_deliveries (integration_id, created_at DESC);

-- ---------------------------------------------------------------- row-level security
ALTER TABLE integrations ENABLE ROW LEVEL SECURITY;
CREATE POLICY int_all ON integrations FOR ALL
    USING (eg_privileged() OR eg_is_staff_of(org_id)) WITH CHECK (eg_privileged() OR eg_is_staff_of(org_id));
ALTER TABLE webhook_deliveries ENABLE ROW LEVEL SECURITY;
CREATE POLICY wh_all ON webhook_deliveries FOR ALL
    USING (eg_privileged() OR eg_is_staff_of(org_id)) WITH CHECK (eg_privileged() OR eg_is_staff_of(org_id));

GRANT SELECT, INSERT, UPDATE ON integrations, webhook_deliveries TO __APP_ROLE__;
