# BL-EG-06 — Advanced Admin Web: Staff Delegation, LMS Credentials & Audit Inspector

|                |                                              |
| -------------- | -------------------------------------------- |
| **Owner**      | EG-FE                                        |
| **Phase**      | Phase 3b-2                                   |
| **Estimate**   | 5 days                                       |
| **Depends on** | BL-EG-04, BL-EG-05                           |
| **Blocks**     | BL-EG-07                                     |
| **Repo**       | sakti-desktop                                |
| **Branch**     | feat/BL-EG-06-admin-web-advanced-audit-lms   |
| **Status**     | **FULL** (Ready to Build)                    |

> Read first: `docs/backlog/00-README.md`, `00-standards/protocol-security.md`,
> `00-standards/ui.md`, `docs/ExamGuard_PRD_v0_3_7.md` (§27.7).

---

### §1. Requirements Covered
- `REQ-EG-ADMIN-02`: Advanced Admin Web features:
  - Organization member management (invite staff, assign roles: `ORG_ADMIN`, `EXAM_ADMIN`, `INVIGILATOR`, deactivate accounts).
  - LMS Integration management (generate API keys, configure signed webhook URLs, inspect delivery failure history).
  - Cryptographic Hash-Chain Audit Log inspector with cryptographic integrity verification button.
  - Platform Admin global thresholds configuration view (default 30s disconnection threshold, rate limits).

---

### §2. Context & Architecture
Completes the remaining requirements of Phase 3b (PRD §27.7, §30.2). Allows organization administrators to self-manage their proctoring staff, integrate university LMS endpoints, and mathematically verify that audit logs have not been altered.

---

### §3. Component Architecture
- New Views in `examguard-web/admin/`:
  - `OrganizationMembersView.tsx` (Roster management and role assignment modal)
  - `LmsIntegrationsView.tsx` (API keys, webhook URLs, and ping test button)
  - `AuditLogInspectorView.tsx` (Tamper-evident hash chain viewer with verification status badge)
  - `PlatformSettingsView.tsx` (Accessible strictly to `PLATFORM_ADMIN`)

---

### §4. API Integrations
- `GET /api/v1/org/members` & `POST /api/v1/org/members/invite`
- `GET /api/v1/org/integrations` & `POST /api/v1/org/integrations/api-keys`
- `GET /api/v1/org/audit-logs` (Includes `prev_hash`, `curr_hash`, and payload diffs)
- `POST /api/v1/org/audit-logs/verify-chain` (Executes server-side mathematical verification)

---

### §5. Mandatory 5 UI States
1. **Loading State**: Table skeleton pulses while members or audit records load.
2. **Empty State**: "Belum ada integrasi LMS yang terdaftar. Buat API Key pertama."
3. **Audit Verified State**: Green cryptographic badge confirming: "Rantai hash audit utuh (100% valid)".
4. **Forbidden State**: Non-Platform Admin attempting to view `/admin/platform` sees 403.
5. **Happy Path**: Rich data tables with member action dropdowns and webhook delivery attempt logs.

---

### §6. Edge Cases
- Organization admin attempts to deactivate their own account $\to$ Blocked by client and server.
- Webhook test ping fails $\to$ Displays raw HTTP response code and error response body from target LMS.

---

### §7. Tests Required
- Member role delegation modal updates user status.
- Audit log hash chain verification assertion.

---

### §8. Out of Scope
- Direct Shibboleth SAML metadata import (Wave 3).

---

### §9. Acceptance Checklist
- [ ] Organization Admins can invite staff and designate roles.
- [ ] LMS API keys can be generated and revoked.
- [ ] Audit logs display previous and current hash with integrity verification.
- [ ] Platform Admin can modify global interruption threshold defaults.

---

### §10. Security Checklist
- [ ] API keys displayed only once upon initial creation.
- [ ] Audit logs remain read-only; no manual mutation permitted.

