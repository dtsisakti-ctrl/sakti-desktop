-- ExamGuard Server — schema 0001 (Phase 1a)
-- Placeholder __APP_ROLE__ is replaced by the migration with the runtime role name.
--
-- Security model
--   * The migration role owns every table. The runtime role (__APP_ROLE__) does NOT,
--     so Row-Level Security always applies to it.
--   * Every request sets transaction-local GUCs:
--       app.ctx          system | platform | staff | candidate | public
--       app.org_id       active organization (staff)
--       app.user_id      staff user
--       app.candidate_id candidate account
--   * RLS is a second line of defence behind the repository-layer filters: a query that
--     forgets its WHERE org_id = ... still only sees the caller's own organization.

-- ---------------------------------------------------------------- context helpers
CREATE FUNCTION eg_ctx() RETURNS text LANGUAGE sql STABLE AS
$$ SELECT coalesce(nullif(current_setting('app.ctx', true), ''), 'none') $$;

CREATE FUNCTION eg_org() RETURNS uuid LANGUAGE sql STABLE AS
$$ SELECT nullif(current_setting('app.org_id', true), '')::uuid $$;

CREATE FUNCTION eg_user() RETURNS uuid LANGUAGE sql STABLE AS
$$ SELECT nullif(current_setting('app.user_id', true), '')::uuid $$;

CREATE FUNCTION eg_candidate() RETURNS uuid LANGUAGE sql STABLE AS
$$ SELECT nullif(current_setting('app.candidate_id', true), '')::uuid $$;

CREATE FUNCTION eg_privileged() RETURNS boolean LANGUAGE sql STABLE AS
$$ SELECT eg_ctx() IN ('system', 'platform') $$;

CREATE FUNCTION eg_is_staff_of(o uuid) RETURNS boolean LANGUAGE sql STABLE AS
$$ SELECT eg_ctx() = 'staff' AND o IS NOT NULL AND o = eg_org() $$;

CREATE FUNCTION eg_is_candidate(c uuid) RETURNS boolean LANGUAGE sql STABLE AS
$$ SELECT eg_ctx() = 'candidate' AND c IS NOT NULL AND c = eg_candidate() $$;

-- ---------------------------------------------------------------- tables
CREATE TABLE platform_settings (
    id          int PRIMARY KEY CHECK (id = 1),
    settings    jsonb NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now()
);

INSERT INTO platform_settings (id, settings) VALUES (1, '{
  "defaults": {
    "retention_dismissed_days": 30,
    "retention_default_days": 90,
    "retention_identity_days": 90,
    "reentry_approval_threshold_minutes": 10,
    "interruption_threshold_seconds": 60,
    "offline_release_grace_minutes": 30,
    "default_identity_check_public": "MANUAL",
    "default_identity_check_private": "NONE"
  },
  "bounds": {
    "retention_dismissed_days": [7, 365],
    "retention_default_days": [7, 1825],
    "retention_identity_days": [7, 365],
    "reentry_approval_threshold_minutes": [1, 240],
    "interruption_threshold_seconds": [15, 600],
    "offline_release_grace_minutes": [5, 240]
  },
  "choices": {
    "default_identity_check_public": ["NONE", "MANUAL"],
    "default_identity_check_private": ["NONE", "MANUAL"]
  }
}');

CREATE TABLE organizations (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug                text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9][a-z0-9-]{1,62}$'),
    name                text NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
    can_publish_public  boolean NOT NULL DEFAULT false,
    settings            jsonb NOT NULL DEFAULT '{}',
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE users (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email              text NOT NULL,
    full_name          text NOT NULL,
    password_hash      text NOT NULL,
    is_platform_admin  boolean NOT NULL DEFAULT false,
    is_active          boolean NOT NULL DEFAULT true,
    created_at         timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX users_email_uq ON users (lower(email));

CREATE TABLE memberships (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      uuid NOT NULL REFERENCES organizations(id),
    user_id     uuid NOT NULL REFERENCES users(id),
    role        text NOT NULL CHECK (role IN ('ORG_ADMIN', 'EXAM_ADMIN', 'INVIGILATOR')),
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (org_id, user_id, role)
);
CREATE INDEX memberships_user_idx ON memberships (user_id);

CREATE TABLE candidates (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email              text NOT NULL,
    full_name          text NOT NULL,
    password_hash      text NOT NULL,
    email_verified_at  timestamptz,
    is_active          boolean NOT NULL DEFAULT true,
    created_at         timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX candidates_email_uq ON candidates (lower(email));

CREATE TABLE one_time_tokens (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    token_hash  text NOT NULL UNIQUE,
    purpose     text NOT NULL CHECK (purpose IN ('EMAIL_VERIFY', 'PASSWORD_RESET')),
    subject_id  uuid NOT NULL,
    expires_at  timestamptz NOT NULL,
    used_at     timestamptz,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE auth_sessions (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    token_hash    text NOT NULL UNIQUE,
    subject_kind  text NOT NULL CHECK (subject_kind IN ('STAFF', 'CANDIDATE')),
    subject_id    uuid NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now(),
    expires_at    timestamptz NOT NULL,
    revoked_at    timestamptz
);

CREATE TABLE exams (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id               uuid NOT NULL REFERENCES organizations(id),
    code                 text NOT NULL CHECK (code ~ '^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$'),
    name                 text NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
    description          text,
    series               text,
    visibility           text NOT NULL CHECK (visibility IN ('PRIVATE', 'PUBLIC')),
    status               text NOT NULL DEFAULT 'DRAFT'
                         CHECK (status IN ('DRAFT', 'READY', 'RUNNING', 'CLOSED', 'FINALIZED', 'CANCELLED')),
    exam_url             text,
    allowed_origins      text[] NOT NULL DEFAULT '{}',
    window_start         timestamptz,
    latest_start         timestamptz,
    window_end           timestamptz,
    duration_minutes     int CHECK (duration_minutes > 0),
    late_start_policy    text NOT NULL DEFAULT 'FIXED_END' CHECK (late_start_policy IN ('FIXED_END', 'FULL_DURATION')),
    checkin_open         timestamptz,
    identity_check       text NOT NULL DEFAULT 'NONE' CHECK (identity_check IN ('NONE', 'MANUAL')),
    registration_open    timestamptz,
    registration_close   timestamptz,
    capacity             int CHECK (capacity > 0),
    registered_count     int NOT NULL DEFAULT 0 CHECK (registered_count >= 0),
    access_code_hash     text,
    integration_level    int NOT NULL DEFAULT 2 CHECK (integration_level IN (0, 2)),
    min_client_version   text,
    policy               jsonb NOT NULL DEFAULT '{}',
    settings             jsonb NOT NULL DEFAULT '{}',
    created_by           uuid REFERENCES users(id),
    created_at           timestamptz NOT NULL DEFAULT now(),
    updated_at           timestamptz NOT NULL DEFAULT now(),
    UNIQUE (org_id, code)
);
CREATE INDEX exams_catalog_idx ON exams (visibility, status, window_start);

CREATE TABLE enrollments (
    id                          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id                      uuid NOT NULL REFERENCES organizations(id),
    exam_id                     uuid NOT NULL REFERENCES exams(id),
    candidate_id                uuid NOT NULL REFERENCES candidates(id),
    source                      text NOT NULL CHECK (source IN ('SELF_REGISTERED', 'INVITED', 'IMPORTED', 'API')),
    status                      text NOT NULL DEFAULT 'CONFIRMED' CHECK (status IN ('CONFIRMED', 'CANCELLED')),
    time_accommodation_minutes  int NOT NULL DEFAULT 0 CHECK (time_accommodation_minutes BETWEEN 0 AND 600),
    external_ref                text,
    cancel_reason               text,
    created_at                  timestamptz NOT NULL DEFAULT now(),
    cancelled_at                timestamptz
);
CREATE UNIQUE INDEX enrollments_active_uq ON enrollments (exam_id, candidate_id) WHERE status = 'CONFIRMED';
CREATE INDEX enrollments_candidate_idx ON enrollments (candidate_id);
CREATE INDEX enrollments_org_idx ON enrollments (org_id);

CREATE TABLE attempts (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id         uuid NOT NULL REFERENCES organizations(id),
    enrollment_id  uuid NOT NULL UNIQUE REFERENCES enrollments(id) ON DELETE CASCADE,
    status         text NOT NULL DEFAULT 'NOT_STARTED' CHECK (status IN (
                      'NOT_STARTED', 'ACTIVE', 'PAUSED', 'INTERRUPTED', 'WAITING_FOR_INVIGILATOR',
                      'REOPENED', 'REINSTATED', 'SUBMITTED', 'EXPIRED', 'TERMINATED', 'NO_SHOW', 'FINALIZED')),
    state_version  bigint NOT NULL DEFAULT 0,
    created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE invitations (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id                  uuid NOT NULL REFERENCES organizations(id),
    exam_id                 uuid NOT NULL REFERENCES exams(id),
    email                   text NOT NULL,
    token_hash              text NOT NULL UNIQUE,
    status                  text NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'ACCEPTED', 'REVOKED')),
    expires_at              timestamptz NOT NULL,
    accepted_enrollment_id  uuid REFERENCES enrollments(id),
    created_by              uuid REFERENCES users(id),
    created_at              timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX invitations_pending_uq ON invitations (exam_id, lower(email)) WHERE status = 'PENDING';

CREATE TABLE email_outbox (
    id          bigserial PRIMARY KEY,
    to_email    text NOT NULL,
    template    text NOT NULL,
    subject     text NOT NULL,
    body        text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    sent_at     timestamptz
);

CREATE TABLE audit_log (
    id           bigserial PRIMARY KEY,
    chain_key    text NOT NULL,
    seq          bigint NOT NULL,
    org_id       uuid REFERENCES organizations(id),
    occurred_at  timestamptz NOT NULL,
    actor_kind   text NOT NULL,
    actor_id     uuid,
    action       text NOT NULL,
    target_type  text,
    target_id    text,
    data         jsonb NOT NULL DEFAULT '{}',
    prev_hash    text NOT NULL,
    hash         text NOT NULL,
    UNIQUE (chain_key, seq)
);
CREATE INDEX audit_log_org_idx ON audit_log (org_id, seq DESC);

-- ---------------------------------------------------------------- integrity triggers
-- org_id of child rows is always derived from the parent, never trusted from the caller.
CREATE FUNCTION eg_set_org_from_exam() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public AS $$
BEGIN
    SELECT org_id INTO NEW.org_id FROM exams WHERE id = NEW.exam_id;
    IF NEW.org_id IS NULL THEN
        RAISE EXCEPTION 'exam % not found', NEW.exam_id USING ERRCODE = 'foreign_key_violation';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER enrollments_set_org BEFORE INSERT OR UPDATE OF exam_id, org_id ON enrollments
    FOR EACH ROW EXECUTE FUNCTION eg_set_org_from_exam();
CREATE TRIGGER invitations_set_org BEFORE INSERT OR UPDATE OF exam_id, org_id ON invitations
    FOR EACH ROW EXECUTE FUNCTION eg_set_org_from_exam();

CREATE FUNCTION eg_set_org_from_enrollment() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public AS $$
BEGIN
    SELECT org_id INTO NEW.org_id FROM enrollments WHERE id = NEW.enrollment_id;
    IF NEW.org_id IS NULL THEN
        RAISE EXCEPTION 'enrollment % not found', NEW.enrollment_id USING ERRCODE = 'foreign_key_violation';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER attempts_set_org BEFORE INSERT OR UPDATE OF enrollment_id, org_id ON attempts
    FOR EACH ROW EXECUTE FUNCTION eg_set_org_from_enrollment();

-- Only platform/system context may grant public publishing or platform-admin rights.
CREATE FUNCTION eg_guard_privileged_columns() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_TABLE_NAME = 'organizations' THEN
        IF NEW.can_publish_public IS DISTINCT FROM (CASE WHEN TG_OP = 'INSERT' THEN false ELSE OLD.can_publish_public END)
           AND NOT eg_privileged() THEN
            RAISE EXCEPTION 'can_publish_public can only be changed by the platform' USING ERRCODE = 'insufficient_privilege';
        END IF;
    ELSIF TG_TABLE_NAME = 'users' THEN
        IF NEW.is_platform_admin IS DISTINCT FROM (CASE WHEN TG_OP = 'INSERT' THEN false ELSE OLD.is_platform_admin END)
           AND NOT eg_privileged() THEN
            RAISE EXCEPTION 'is_platform_admin can only be changed by the platform' USING ERRCODE = 'insufficient_privilege';
        END IF;
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER organizations_guard BEFORE INSERT OR UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION eg_guard_privileged_columns();
CREATE TRIGGER users_guard BEFORE INSERT OR UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION eg_guard_privileged_columns();

-- ---------------------------------------------------------------- seat counter
-- Atomic seat reservation: the conditional UPDATE takes a row lock, so concurrent
-- registrations are serialized and can never exceed capacity.
CREATE FUNCTION eg_reserve_seat(p_exam uuid) RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public AS $$
DECLARE n int;
BEGIN
    UPDATE exams SET registered_count = registered_count + 1
     WHERE id = p_exam AND (capacity IS NULL OR registered_count < capacity);
    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n = 1;
END $$;

CREATE FUNCTION eg_release_seat(p_exam uuid) RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public AS $$
BEGIN
    UPDATE exams SET registered_count = greatest(registered_count - 1, 0) WHERE id = p_exam;
END $$;

-- ---------------------------------------------------------------- audit log (hash chain)
CREATE FUNCTION eg_audit_payload(
    p_chain text, p_seq bigint, p_ts timestamptz, p_actor_kind text, p_actor_id uuid,
    p_action text, p_target_type text, p_target_id text, p_data jsonb, p_prev text
) RETURNS text LANGUAGE sql IMMUTABLE AS $$
    SELECT concat_ws('|',
        p_chain, p_seq::text,
        to_char(p_ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
        p_actor_kind, coalesce(p_actor_id::text, '-'), p_action,
        coalesce(p_target_type, '-'), coalesce(p_target_id, '-'),
        p_data::text, p_prev)
$$;

-- The runtime role has no INSERT/UPDATE/DELETE on audit_log; this function is the only writer.
CREATE FUNCTION eg_audit_append(
    p_org uuid, p_actor_kind text, p_actor_id uuid, p_action text,
    p_target_type text, p_target_id text, p_data jsonb
) RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    k text := CASE WHEN p_org IS NULL THEN 'platform' ELSE 'org:' || p_org::text END;
    s bigint; ph text; h text; new_id bigint;
    ts timestamptz := clock_timestamp();
    d jsonb := coalesce(p_data, '{}'::jsonb);
BEGIN
    IF eg_ctx() = 'staff' AND p_org IS DISTINCT FROM eg_org() THEN
        RAISE EXCEPTION 'staff may only write to the audit chain of the active organization'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtext('eg_audit:' || k));
    SELECT seq, hash INTO s, ph FROM audit_log WHERE chain_key = k ORDER BY seq DESC LIMIT 1;
    s  := coalesce(s, 0) + 1;
    ph := coalesce(ph, repeat('0', 64));
    h  := encode(sha256(convert_to(
            eg_audit_payload(k, s, ts, p_actor_kind, p_actor_id, p_action, p_target_type, p_target_id, d, ph),
            'UTF8')), 'hex');
    INSERT INTO audit_log (chain_key, seq, org_id, occurred_at, actor_kind, actor_id, action,
                           target_type, target_id, data, prev_hash, hash)
    VALUES (k, s, p_org, ts, p_actor_kind, p_actor_id, p_action, p_target_type, p_target_id, d, ph, h)
    RETURNING id INTO new_id;
    RETURN new_id;
END $$;

CREATE FUNCTION eg_audit_verify(p_chain text)
RETURNS TABLE (ok boolean, checked bigint, first_bad_seq bigint, reason text)
LANGUAGE plpgsql STABLE AS $$
DECLARE r record; expected_prev text := repeat('0', 64); expected_seq bigint := 1; n bigint := 0;
BEGIN
    FOR r IN SELECT * FROM audit_log a WHERE a.chain_key = p_chain ORDER BY a.seq LOOP
        n := n + 1;
        IF r.seq <> expected_seq THEN
            RETURN QUERY SELECT false, n, r.seq, 'sequence gap'; RETURN;
        END IF;
        IF r.prev_hash <> expected_prev THEN
            RETURN QUERY SELECT false, n, r.seq, 'prev_hash mismatch'; RETURN;
        END IF;
        IF r.hash <> encode(sha256(convert_to(eg_audit_payload(r.chain_key, r.seq, r.occurred_at,
                r.actor_kind, r.actor_id, r.action, r.target_type, r.target_id, r.data, r.prev_hash),
                'UTF8')), 'hex') THEN
            RETURN QUERY SELECT false, n, r.seq, 'hash mismatch'; RETURN;
        END IF;
        expected_prev := r.hash;
        expected_seq := expected_seq + 1;
    END LOOP;
    RETURN QUERY SELECT true, n, NULL::bigint, NULL::text;
END $$;

-- ---------------------------------------------------------------- row-level security
ALTER TABLE platform_settings ENABLE ROW LEVEL SECURITY;
CREATE POLICY ps_select ON platform_settings FOR SELECT USING (true);
CREATE POLICY ps_update ON platform_settings FOR UPDATE USING (eg_privileged()) WITH CHECK (eg_privileged());

ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
CREATE POLICY org_select ON organizations FOR SELECT USING (true);
CREATE POLICY org_insert ON organizations FOR INSERT WITH CHECK (eg_privileged());
CREATE POLICY org_update ON organizations FOR UPDATE
    USING (eg_privileged() OR eg_is_staff_of(id)) WITH CHECK (eg_privileged() OR eg_is_staff_of(id));

ALTER TABLE memberships ENABLE ROW LEVEL SECURITY;
CREATE POLICY mem_select ON memberships FOR SELECT
    USING (eg_privileged() OR eg_is_staff_of(org_id) OR (user_id IS NOT NULL AND user_id = eg_user()));
CREATE POLICY mem_write ON memberships FOR ALL
    USING (eg_privileged() OR eg_is_staff_of(org_id)) WITH CHECK (eg_privileged() OR eg_is_staff_of(org_id));

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
CREATE POLICY users_select ON users FOR SELECT USING (
    eg_privileged() OR id = eg_user()
    OR (eg_ctx() = 'staff' AND EXISTS (
        SELECT 1 FROM memberships m WHERE m.user_id = users.id AND m.org_id = eg_org())));
CREATE POLICY users_insert ON users FOR INSERT WITH CHECK (eg_privileged());
CREATE POLICY users_update ON users FOR UPDATE
    USING (eg_privileged() OR id = eg_user()) WITH CHECK (eg_privileged() OR id = eg_user());

ALTER TABLE candidates ENABLE ROW LEVEL SECURITY;
CREATE POLICY cand_select ON candidates FOR SELECT USING (
    eg_privileged() OR eg_is_candidate(id)
    OR (eg_ctx() = 'staff' AND EXISTS (
        SELECT 1 FROM enrollments e WHERE e.candidate_id = candidates.id AND e.org_id = eg_org())));
CREATE POLICY cand_insert ON candidates FOR INSERT WITH CHECK (eg_privileged());
CREATE POLICY cand_update ON candidates FOR UPDATE
    USING (eg_privileged() OR eg_is_candidate(id)) WITH CHECK (eg_privileged() OR eg_is_candidate(id));

ALTER TABLE one_time_tokens ENABLE ROW LEVEL SECURITY;
CREATE POLICY ott_all ON one_time_tokens FOR ALL USING (eg_ctx() = 'system') WITH CHECK (eg_ctx() = 'system');

ALTER TABLE auth_sessions ENABLE ROW LEVEL SECURITY;
CREATE POLICY sess_all ON auth_sessions FOR ALL USING (eg_ctx() = 'system') WITH CHECK (eg_ctx() = 'system');

ALTER TABLE email_outbox ENABLE ROW LEVEL SECURITY;
CREATE POLICY outbox_all ON email_outbox FOR ALL USING (eg_ctx() = 'system') WITH CHECK (eg_ctx() = 'system');

ALTER TABLE exams ENABLE ROW LEVEL SECURITY;
CREATE POLICY exams_select ON exams FOR SELECT USING (
    eg_privileged() OR eg_is_staff_of(org_id)
    OR (eg_ctx() IN ('candidate', 'public') AND visibility = 'PUBLIC' AND status IN ('READY', 'RUNNING'))
    OR (eg_ctx() = 'candidate' AND EXISTS (
        SELECT 1 FROM enrollments e WHERE e.exam_id = exams.id AND e.candidate_id = eg_candidate())));
CREATE POLICY exams_insert ON exams FOR INSERT WITH CHECK (eg_privileged() OR eg_is_staff_of(org_id));
CREATE POLICY exams_update ON exams FOR UPDATE
    USING (eg_privileged() OR eg_is_staff_of(org_id)) WITH CHECK (eg_privileged() OR eg_is_staff_of(org_id));

ALTER TABLE enrollments ENABLE ROW LEVEL SECURITY;
CREATE POLICY enr_all ON enrollments FOR ALL
    USING (eg_privileged() OR eg_is_staff_of(org_id) OR eg_is_candidate(candidate_id))
    WITH CHECK (eg_privileged() OR eg_is_staff_of(org_id) OR eg_is_candidate(candidate_id));

ALTER TABLE attempts ENABLE ROW LEVEL SECURITY;
CREATE POLICY att_all ON attempts FOR ALL
    USING (eg_privileged() OR eg_is_staff_of(org_id) OR (eg_ctx() = 'candidate' AND EXISTS (
        SELECT 1 FROM enrollments e WHERE e.id = attempts.enrollment_id AND e.candidate_id = eg_candidate())))
    WITH CHECK (eg_privileged() OR eg_is_staff_of(org_id) OR (eg_ctx() = 'candidate' AND EXISTS (
        SELECT 1 FROM enrollments e WHERE e.id = attempts.enrollment_id AND e.candidate_id = eg_candidate())));

ALTER TABLE invitations ENABLE ROW LEVEL SECURITY;
CREATE POLICY inv_all ON invitations FOR ALL
    USING (eg_privileged() OR eg_is_staff_of(org_id)) WITH CHECK (eg_privileged() OR eg_is_staff_of(org_id));

ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY audit_select ON audit_log FOR SELECT USING (eg_privileged() OR eg_is_staff_of(org_id));

-- ---------------------------------------------------------------- grants for the runtime role
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO __APP_ROLE__;
GRANT SELECT, UPDATE ON platform_settings TO __APP_ROLE__;
GRANT SELECT, INSERT, UPDATE ON organizations, users, candidates, exams TO __APP_ROLE__;
GRANT SELECT, INSERT, UPDATE, DELETE ON memberships, one_time_tokens, auth_sessions,
      enrollments, attempts, invitations TO __APP_ROLE__;
GRANT SELECT, INSERT, UPDATE ON email_outbox TO __APP_ROLE__;
GRANT USAGE ON SEQUENCE email_outbox_id_seq TO __APP_ROLE__;
GRANT SELECT ON audit_log TO __APP_ROLE__;   -- append only through eg_audit_append()
REVOKE EXECUTE ON FUNCTION eg_reserve_seat(uuid), eg_release_seat(uuid),
       eg_audit_append(uuid, text, uuid, text, text, text, jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION eg_reserve_seat(uuid), eg_release_seat(uuid),
      eg_audit_append(uuid, text, uuid, text, text, text, jsonb) TO __APP_ROLE__;
