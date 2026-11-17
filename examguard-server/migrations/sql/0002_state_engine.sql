-- ExamGuard Server — schema 0002 (Phase 1b): attempt state & timing engine.
-- Placeholder __APP_ROLE__ is replaced by the migration with the runtime role name.

-- ---------------------------------------------------------------- exams
ALTER TABLE exams
    ADD COLUMN extension_minutes int NOT NULL DEFAULT 0 CHECK (extension_minutes BETWEEN 0 AND 1440),
    ADD COLUMN running_at   timestamptz,
    ADD COLUMN closed_at    timestamptz,
    ADD COLUMN finalized_at timestamptz;

-- ---------------------------------------------------------------- attempts
ALTER TABLE attempts
    ADD COLUMN started_at                  timestamptz,
    ADD COLUMN deadline                    timestamptz,
    ADD COLUMN paused_at                   timestamptz,
    ADD COLUMN pause_timer_mode            text CHECK (pause_timer_mode IN ('KEEP_RUNNING', 'PAUSE_TIMER')),
    ADD COLUMN ended_at                    timestamptz,
    ADD COLUMN final_status                text,          -- status before FINALIZED
    ADD COLUMN reopen_count                int NOT NULL DEFAULT 0,
    ADD COLUMN reinstate_count             int NOT NULL DEFAULT 0,
    ADD COLUMN termination_reason_category text
        CHECK (termination_reason_category IN ('TECHNICAL', 'ADMINISTRATIVE', 'DISCIPLINARY')),
    ADD COLUMN identity_status             text NOT NULL DEFAULT 'NONE'
        CHECK (identity_status IN ('NONE', 'PENDING', 'APPROVED', 'REJECTED')),
    ADD COLUMN identity_rejections         int NOT NULL DEFAULT 0,
    ADD COLUMN updated_at                  timestamptz NOT NULL DEFAULT now();

CREATE INDEX attempts_status_idx ON attempts (status);
CREATE INDEX attempts_deadline_idx ON attempts (deadline) WHERE deadline IS NOT NULL;

-- Authoritative state (status or deadline) may only change together with state_version + 1.
-- A second line of defence behind the state engine: a stray UPDATE can never move an attempt
-- silently, which would leave clients unable to order what they receive.
CREATE FUNCTION eg_guard_attempt_version() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (NEW.status IS DISTINCT FROM OLD.status OR NEW.deadline IS DISTINCT FROM OLD.deadline)
       AND NEW.state_version <> OLD.state_version + 1 THEN
        RAISE EXCEPTION 'attempt status/deadline changed without state_version increment'
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.state_version < OLD.state_version THEN
        RAISE EXCEPTION 'state_version must be monotonic' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER attempts_version_guard BEFORE UPDATE ON attempts
    FOR EACH ROW EXECUTE FUNCTION eg_guard_attempt_version();

-- ---------------------------------------------------------------- org_id from attempt
CREATE FUNCTION eg_set_org_from_attempt() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public AS $$
BEGIN
    SELECT org_id INTO NEW.org_id FROM attempts WHERE id = NEW.attempt_id;
    IF NEW.org_id IS NULL THEN
        RAISE EXCEPTION 'attempt % not found', NEW.attempt_id USING ERRCODE = 'foreign_key_violation';
    END IF;
    RETURN NEW;
END $$;

-- ---------------------------------------------------------------- state transitions (append-only)
CREATE TABLE state_transitions (
    id               bigserial PRIMARY KEY,
    org_id           uuid NOT NULL REFERENCES organizations(id),
    attempt_id       uuid NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
    state_version    bigint NOT NULL,
    from_status      text NOT NULL,
    to_status        text NOT NULL,
    trigger          text NOT NULL,
    actor_kind       text NOT NULL,
    actor_id         uuid,
    reason           text,
    reason_category  text,
    old_deadline     timestamptz,
    new_deadline     timestamptz,
    data             jsonb NOT NULL DEFAULT '{}',
    occurred_at      timestamptz NOT NULL,
    UNIQUE (attempt_id, state_version)
);
CREATE TRIGGER state_transitions_set_org BEFORE INSERT ON state_transitions
    FOR EACH ROW EXECUTE FUNCTION eg_set_org_from_attempt();

-- ---------------------------------------------------------------- device sessions
CREATE TABLE device_sessions (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id             uuid NOT NULL REFERENCES organizations(id),
    attempt_id         uuid NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
    status             text NOT NULL CHECK (status IN ('ACTIVE', 'PENDING_APPROVAL', 'REVOKED')),
    public_key         text,
    client_version     text,
    os_info            jsonb NOT NULL DEFAULT '{}',
    created_at         timestamptz NOT NULL,
    activated_at       timestamptz,
    revoked_at         timestamptz,
    revoke_reason      text,
    last_heartbeat_at  timestamptz,
    last_heartbeat_seq bigint NOT NULL DEFAULT 0
);
-- One attempt has at most one ACTIVE and at most one PENDING_APPROVAL device session (PRD §18).
CREATE UNIQUE INDEX device_sessions_one_active ON device_sessions (attempt_id) WHERE status = 'ACTIVE';
CREATE UNIQUE INDEX device_sessions_one_pending ON device_sessions (attempt_id) WHERE status = 'PENDING_APPROVAL';
CREATE INDEX device_sessions_heartbeat_idx ON device_sessions (last_heartbeat_at) WHERE status = 'ACTIVE';
CREATE TRIGGER device_sessions_set_org BEFORE INSERT ON device_sessions
    FOR EACH ROW EXECUTE FUNCTION eg_set_org_from_attempt();

-- ---------------------------------------------------------------- commands (outbox for Phase 1c)
CREATE TABLE commands (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id             uuid NOT NULL REFERENCES organizations(id),
    attempt_id         uuid NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
    device_session_id  uuid REFERENCES device_sessions(id),
    type               text NOT NULL CHECK (type IN (
                          'WARNING', 'PAUSE_EXAM', 'RESUME_EXAM', 'UPDATE_DEADLINE', 'ALLOW_REENTRY',
                          'REJECT_REENTRY', 'FORCE_SUBMIT', 'FORCE_TERMINATE', 'EMERGENCY_UNLOCK')),
    payload            jsonb NOT NULL DEFAULT '{}',
    state_version      bigint NOT NULL,
    issued_by          uuid,
    issued_at          timestamptz NOT NULL,
    expires_at         timestamptz NOT NULL,
    delivery_status    text NOT NULL DEFAULT 'PENDING'
                       CHECK (delivery_status IN ('PENDING', 'SENT', 'APPLIED', 'STALE', 'REJECTED')),
    delivered_at       timestamptz,
    ack_reason         text
);
CREATE INDEX commands_attempt_idx ON commands (attempt_id, issued_at);
CREATE INDEX commands_pending_idx ON commands (delivery_status) WHERE delivery_status = 'PENDING';
CREATE TRIGGER commands_set_org BEFORE INSERT ON commands
    FOR EACH ROW EXECUTE FUNCTION eg_set_org_from_attempt();

-- ---------------------------------------------------------------- invigilator assignments
CREATE TABLE invigilator_assignments (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      uuid NOT NULL REFERENCES organizations(id),
    exam_id     uuid NOT NULL REFERENCES exams(id),
    user_id     uuid NOT NULL REFERENCES users(id),
    created_by  uuid REFERENCES users(id),
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (exam_id, user_id)
);
CREATE INDEX invigilator_assignments_user_idx ON invigilator_assignments (user_id);
CREATE TRIGGER invigilator_assignments_set_org BEFORE INSERT OR UPDATE OF exam_id, org_id
    ON invigilator_assignments FOR EACH ROW EXECUTE FUNCTION eg_set_org_from_exam();

-- ---------------------------------------------------------------- row-level security
ALTER TABLE state_transitions ENABLE ROW LEVEL SECURITY;
CREATE POLICY st_select ON state_transitions FOR SELECT USING (eg_privileged() OR eg_is_staff_of(org_id));
CREATE POLICY st_insert ON state_transitions FOR INSERT
    WITH CHECK (eg_privileged() OR eg_is_staff_of(org_id) OR (eg_ctx() = 'candidate' AND EXISTS (
        SELECT 1 FROM attempts a JOIN enrollments e ON e.id = a.enrollment_id
         WHERE a.id = state_transitions.attempt_id AND e.candidate_id = eg_candidate())));

ALTER TABLE device_sessions ENABLE ROW LEVEL SECURITY;
CREATE POLICY ds_all ON device_sessions FOR ALL
    USING (eg_privileged() OR eg_is_staff_of(org_id)) WITH CHECK (eg_privileged() OR eg_is_staff_of(org_id));

ALTER TABLE commands ENABLE ROW LEVEL SECURITY;
CREATE POLICY cmd_all ON commands FOR ALL
    USING (eg_privileged() OR eg_is_staff_of(org_id)) WITH CHECK (eg_privileged() OR eg_is_staff_of(org_id));

ALTER TABLE invigilator_assignments ENABLE ROW LEVEL SECURITY;
CREATE POLICY ia_all ON invigilator_assignments FOR ALL
    USING (eg_privileged() OR eg_is_staff_of(org_id)) WITH CHECK (eg_privileged() OR eg_is_staff_of(org_id));

-- ---------------------------------------------------------------- grants
GRANT SELECT, INSERT ON state_transitions TO __APP_ROLE__;       -- append-only
GRANT USAGE ON SEQUENCE state_transitions_id_seq TO __APP_ROLE__;
GRANT SELECT, INSERT, UPDATE ON device_sessions, commands TO __APP_ROLE__;
GRANT SELECT, INSERT, DELETE ON invigilator_assignments TO __APP_ROLE__;
