# BL-EG-03 — Integration API for LMS, Signed Webhooks & Emergency Challenge Unlock

|                |                                              |
| -------------- | -------------------------------------------- |
| **Owner**      | EG-BE                                        |
| **Phase**      | Phase 1c-2                                   |
| **Estimate**   | 5 days                                       |
| **Depends on** | BL-EG-02                                     |
| **Blocks**     | BL-EG-04                                     |
| **Repo**       | sakti-desktop                                |
| **Branch**     | feat/BL-EG-03-integration-api-webhooks-unlock|
| **Status**     | **DONE**                                     |

---

### §1. Requirements Covered
- `REQ-EG-LMS-01`: Integration API for external LMS websites, Attestation Token header generation, and signed Completion Tokens.
- `REQ-EG-HOOK-01`: Outgoing webhooks signed with Ed25519 sent to subscribed organization endpoints.
- `REQ-EG-UNLOCK-01`: Emergency Unlock suite: online signed command, 8-character challenge–response, and pre-printed backup codes (`XXXXX-XXXXX`).
- `REQ-EG-PHOTO-01`: Encrypted identity photos (selfie + ID card) stored encrypted at rest with audit trail on staff decryption.

---

### §2. Context & Architecture
Allows LMS platforms (Moodle, Canvas, custom university test sites) to integrate ExamGuard as an external proctoring layer. The LMS generates launch links for candidates and receives signed completion tokens upon exam finish. If network or system lockouts occur, invigilators can read an 8-character challenge code off the candidate's monitor and generate an unlock response code.

---

### §3. Data Model (Database Layer)
- Alembic Migrations: `0004_integration_and_webhooks.py`, `0005_emergency_unlock_codes.py`
- Models: `IntegrationCredential`, `WebhookSubscription`, `WebhookDelivery`, `IdentityPhoto`, `EmergencyBackupCode`

---

### §4. REST Endpoints
- `POST /api/v1/integration/attempts/{id}/launch` (LMS requests new launch link)
- `POST /api/v1/integration/attempts/{id}/complete` (LMS reports completion and requests Completion Token)
- `POST /api/v1/org/attempts/{id}/unlock-response` (Invigilator inputs 8-character challenge)
- `POST /api/v1/org/exams/{id}/backup-codes` (Pre-generates printed backup codes)
- `GET /api/v1/org/identity-photos/{id}` (Decrypts photo, logging staff actor)

---

### §5. Service & Business Logic
- Webhooks signed via Ed25519: `X-ExamGuard-Signature` header computed over body.
- Identity photos encrypted using AES-GCM before filesystem/S3 write.
- Challenge–response: `response_code = hmac_sha256(unlock_secret, challenge)[:8]`.

---

### §6. Edge Cases
- Webhook delivery fails due to LMS downtime: Exponential backoff retry schedule (up to 5 attempts).
- Challenge code entered with lowercase or dashes: Normalized automatically by the server.

---

### §7. Tests Required
- Webhook delivery and Ed25519 signature validation test.
- Challenge–response mathematical equivalence test against Rust client.
- Identity photo decryption access audit log assertion.

---

### §8. Out of Scope
- Direct LTI 1.3 Advantage integration (Wave 3).

---

### §9. Acceptance Checklist
- [x] Integration API generates valid launch URLs.
- [x] Webhooks deliver signed payloads with automatic retry.
- [x] Challenge–response unlock produces correct 8-digit response.
- [x] Identity photos encrypted at rest and audited on read.

---

### §10. Security Checklist
- [x] LMS credentials authenticated using HTTP Basic or API Keys.
- [x] Identity photos decrypted strictly in memory upon authorized request.

