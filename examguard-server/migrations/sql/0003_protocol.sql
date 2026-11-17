-- ExamGuard Server — schema 0003 (Phase 1c-1): keys, launch tokens, signed commands, events, incidents.
-- Placeholder __APP_ROLE__ is replaced by the migration with the runtime role name.

-- ---------------------------------------------------------------- server signing keys (PRD §19)
-- One Ed25519 key pair may serve several uses (MVP), each published under its own kid "<base>.<use>".
CREATE TABLE server_keys (
    kid_base          text PRIMARY KEY,
    uses              text[] NOT NULL,
    public_key        text NOT NULL,                 -- base64url raw 32 bytes
    private_key_enc   text NOT NULL,                 -- AES-256-GCM with the key-encryption key
    status            text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'RETIRED', 'REVOKED')),
    not_before        timestamptz NOT NULL,
    not_after         timestamptz NOT NULL,
    created_at        timestamptz NOT NULL DEFAULT now()
);
-- Key set documents signed offline by the root trust key. The newest one is served.
CREATE TABLE key_sets (
    id          bigserial PRIMARY KEY,
    envelope    text NOT NULL,                       -- {"kid","body","sig"} as published
    issued_at   timestamptz NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------- launch tokens (PRD §12.1)
CREATE TABLE launch_tokens (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      uuid NOT NULL REFERENCES organizations(id),
    attempt_id  uuid NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
    token_hash  text NOT NULL UNIQUE,
    created_at  timestamptz NOT NULL,
    expires_at  timestamptz NOT NULL,
    used_at     timestamptz,
    used_by_device_session uuid
);
CREATE TRIGGER launch_tokens_set_org BEFORE INSERT ON launch_tokens
    FOR EACH ROW EXECUTE FUNCTION eg_set_org_from_attempt();

-- ---------------------------------------------------------------- signed commands
ALTER TABLE commands ADD COLUMN envelope text;     -- signed once, retransmitted byte-identical

-- ---------------------------------------------------------------- events & incidents (PRD §15, §17.8)
CREATE TABLE incidents (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id         uuid NOT NULL REFERENCES organizations(id),
    attempt_id     uuid NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
    type           text NOT NULL,
    severity       text NOT NULL CHECK (severity IN ('INFO', 'LOW', 'MEDIUM', 'HIGH')),
    status         text NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'REVIEWED', 'DISMISSED', 'ESCALATED')),
    started_at     timestamptz NOT NULL,
    ended_at       timestamptz,
    event_count    int NOT NULL DEFAULT 1,
    data           jsonb NOT NULL DEFAULT '{}',
    reviewed_by    uuid REFERENCES users(id),
    reviewed_at    timestamptz,
    review_note    text,
    created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX incidents_attempt_idx ON incidents (attempt_id, started_at);
CREATE INDEX incidents_open_idx ON incidents (org_id, status) WHERE status = 'OPEN';
CREATE TRIGGER incidents_set_org BEFORE INSERT ON incidents
    FOR EACH ROW EXECUTE FUNCTION eg_set_org_from_attempt();

CREATE TABLE events (
    id                 uuid PRIMARY KEY,               -- event_id from the client
    org_id             uuid NOT NULL REFERENCES organizations(id),
    attempt_id         uuid NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
    device_session_id  uuid NOT NULL REFERENCES device_sessions(id),
    seq                bigint NOT NULL,
    type               text NOT NULL,
    phase              text NOT NULL CHECK (phase IN ('OPEN', 'CLOSE', 'INSTANT')),
    started_at         timestamptz NOT NULL,
    ended_at           timestamptz,
    confidence         real,
    metadata           jsonb NOT NULL DEFAULT '{}',
    evidence_ref       text,
    severity           text NOT NULL,
    incident_id        uuid REFERENCES incidents(id),
    received_at        timestamptz NOT NULL,
    UNIQUE (device_session_id, seq)                    -- idempotent upload (§17.8)
);
CREATE INDEX events_attempt_idx ON events (attempt_id, started_at);
CREATE TRIGGER events_set_org BEFORE INSERT ON events
    FOR EACH ROW EXECUTE FUNCTION eg_set_org_from_attempt();

-- ---------------------------------------------------------------- row-level security
ALTER TABLE server_keys ENABLE ROW LEVEL SECURITY;
CREATE POLICY sk_all ON server_keys FOR ALL USING (eg_privileged()) WITH CHECK (eg_privileged());
ALTER TABLE key_sets ENABLE ROW LEVEL SECURITY;
CREATE POLICY ks_select ON key_sets FOR SELECT USING (true);          -- the key set is public
CREATE POLICY ks_insert ON key_sets FOR INSERT WITH CHECK (eg_privileged());

ALTER TABLE launch_tokens ENABLE ROW LEVEL SECURITY;
CREATE POLICY lt_all ON launch_tokens FOR ALL
    USING (eg_privileged() OR (eg_ctx() = 'candidate' AND EXISTS (
        SELECT 1 FROM attempts a JOIN enrollments e ON e.id = a.enrollment_id
         WHERE a.id = launch_tokens.attempt_id AND e.candidate_id = eg_candidate())))
    WITH CHECK (eg_privileged() OR (eg_ctx() = 'candidate' AND EXISTS (
        SELECT 1 FROM attempts a JOIN enrollments e ON e.id = a.enrollment_id
         WHERE a.id = launch_tokens.attempt_id AND e.candidate_id = eg_candidate())));

ALTER TABLE incidents ENABLE ROW LEVEL SECURITY;
CREATE POLICY inc_all ON incidents FOR ALL
    USING (eg_privileged() OR eg_is_staff_of(org_id)) WITH CHECK (eg_privileged() OR eg_is_staff_of(org_id));
ALTER TABLE events ENABLE ROW LEVEL SECURITY;
CREATE POLICY ev_select ON events FOR SELECT USING (eg_privileged() OR eg_is_staff_of(org_id));
CREATE POLICY ev_insert ON events FOR INSERT WITH CHECK (eg_privileged());

-- ---------------------------------------------------------------- grants
GRANT SELECT, INSERT, UPDATE ON server_keys TO __APP_ROLE__;
GRANT SELECT, INSERT ON key_sets TO __APP_ROLE__;
GRANT USAGE ON SEQUENCE key_sets_id_seq TO __APP_ROLE__;
GRANT SELECT, INSERT, UPDATE ON launch_tokens, incidents TO __APP_ROLE__;
GRANT SELECT, INSERT, UPDATE ON events TO __APP_ROLE__;
