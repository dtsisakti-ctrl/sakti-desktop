# 00-schema-decisions: ExamGuard Database Architecture Decisions

This document details the PostgreSQL database architecture, Alembic migrations (0001–0006), Row-Level Security (RLS) contexts, and hash-chained audit logging for ExamGuard.

---

## 1. Migration History (Alembic 0001 → 0006)

| Migration | Version | Key Tables & Entities Introduced | Purpose |
| :--- | :--- | :--- | :--- |
| **`0001`** | Phase 1a | `organizations`, `users`, `exams`, `enrollments`, `audit_logs` | Tenancy foundation, dual database roles (owner vs runtime), hash-chained audit log with `eg_audit_append()`, and atomic seat reservations (`eg_reserve_seat()`). |
| **`0002`** | Phase 1b | `attempts`, `state_transitions`, `invigilator_assignments`, `device_sessions`, `commands`, `events`, `incidents` | Attempt lifecycle state machine, precision timing engine, invigilator assignments, and incident aggregation. |
| **`0003`** | Phase 1c-1 | `signing_keys`, `trust_anchors`, `launch_tokens` | Ed25519 cryptographic signing keys, public key sets (`.well-known/examguard-keys.json`), and Signed Exam Config envelopes. |
| **`0004`** | Phase 1c-2 | `integration_credentials`, `webhook_subscriptions`, `webhook_deliveries`, `identity_photos` | Integration API for LMS, signed outgoing webhooks, and AES-encrypted identity verification photos (selfie + ID card). |
| **`0005`** | Phase 1c-2 | `emergency_backup_codes`, `attempt_unlock_secrets` | Challenge–response HMAC secrets and pre-generated printed backup unlock codes. |
| **`0006`** | Phase 3a | `exams.interruption_threshold_seconds` | Unified disconnection threshold defaulting to **30 seconds** (replacing separate 30s/60s offline/interrupted timers). |

---

## 2. Row-Level Security (RLS) & Multi-Tenancy Architecture

ExamGuard enforces strict multi-tenancy using PostgreSQL native RLS:
1. **Dual Role Separation**:
   - `examguard_owner`: DDL migrations, bypasses RLS during setup.
   - `examguard_runtime`: Operational application queries; RLS is unconditionally enabled.
2. **Session Context Injection**:
   Every database connection sets transaction-level configuration variables:
   ```sql
   SET LOCAL app.current_org_id = '<org-uuid>';
   SET LOCAL app.current_user_id = '<user-uuid>';
   SET LOCAL app.current_role = 'INVIGILATOR';
   ```
3. **Parent Hierarchy Propagation**:
   Child tables (`attempts`, `events`, `incidents`) inherit `org_id` from their parent entities via database triggers, preventing cross-tenant leakage even on malformed insert statements.

---

## 3. Cryptographic Audit Chain (`eg_audit_append`)

Every administrative action, staff override, and identity inspection writes an entry to `audit_logs` via the PostgreSQL stored function `eg_audit_append()`:
- Computes `SHA-256(previous_hash + current_event_payload)`.
- Produces a tamper-evident hash chain. If an attacker tampers with or deletes a historical row in `audit_logs`, the hash chain fails mathematical verification.

