-- ExamGuard Server — schema 0005 (Phase 1c-2): identity photos, emergency unlock.
-- Placeholder __APP_ROLE__ is replaced by the migration with the runtime role name.

-- ---------------------------------------------------------------- identity photos (PRD §12.5)
CREATE TABLE identity_photos (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id        uuid NOT NULL REFERENCES organizations(id),
    attempt_id    uuid NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
    submission    int NOT NULL,                        -- 1..3 (retries after rejection)
    kind          text NOT NULL CHECK (kind IN ('SELFIE', 'ID_CARD')),
    storage_key   text NOT NULL UNIQUE,                -- encrypted blob in the storage backend
    content_type  text NOT NULL CHECK (content_type IN ('image/jpeg', 'image/png', 'image/webp')),
    size_bytes    int NOT NULL,
    sha256        text NOT NULL,
    created_at    timestamptz NOT NULL,
    UNIQUE (attempt_id, submission, kind)
);
CREATE TRIGGER identity_photos_set_org BEFORE INSERT ON identity_photos
    FOR EACH ROW EXECUTE FUNCTION eg_set_org_from_attempt();

-- ---------------------------------------------------------------- emergency unlock (PRD §22)
ALTER TABLE attempts ADD COLUMN unlock_secret_enc text;   -- per-attempt HMAC secret, sealed

CREATE TABLE backup_codes (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      uuid NOT NULL REFERENCES organizations(id),
    exam_id     uuid NOT NULL REFERENCES exams(id),
    batch_id    uuid NOT NULL,
    code_hash   text NOT NULL UNIQUE,                  -- sha256(exam_id ":" code); the client gets this
    created_by  uuid REFERENCES users(id),
    created_at  timestamptz NOT NULL,
    used_at     timestamptz,
    used_by_attempt uuid REFERENCES attempts(id)
);
CREATE INDEX backup_codes_exam_idx ON backup_codes (exam_id);
CREATE TRIGGER backup_codes_set_org BEFORE INSERT ON backup_codes
    FOR EACH ROW EXECUTE FUNCTION eg_set_org_from_exam();

ALTER TABLE identity_photos ENABLE ROW LEVEL SECURITY;
CREATE POLICY ip_all ON identity_photos FOR ALL
    USING (eg_privileged() OR eg_is_staff_of(org_id)) WITH CHECK (eg_privileged() OR eg_is_staff_of(org_id));
ALTER TABLE backup_codes ENABLE ROW LEVEL SECURITY;
CREATE POLICY bc_all ON backup_codes FOR ALL
    USING (eg_privileged() OR eg_is_staff_of(org_id)) WITH CHECK (eg_privileged() OR eg_is_staff_of(org_id));

GRANT SELECT, INSERT, UPDATE ON identity_photos, backup_codes TO __APP_ROLE__;
