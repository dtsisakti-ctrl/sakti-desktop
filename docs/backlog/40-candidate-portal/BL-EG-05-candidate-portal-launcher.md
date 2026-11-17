# BL-EG-05 — Candidate Portal, Exam Catalog & Launch Gate (PRD §28)

|                |                                              |
| -------------- | -------------------------------------------- |
| **Owner**      | EG-FE                                        |
| **Phase**      | Phase 3b-1                                   |
| **Estimate**   | 5 days                                       |
| **Depends on** | BL-EG-04                                     |
| **Blocks**     | BL-EG-06                                     |
| **Repo**       | sakti-desktop                                |
| **Branch**     | feat/BL-EG-05-candidate-portal-launcher      |
| **Status**     | **DONE**                                     |

---

### §1. Requirements Covered
- `REQ-EG-PORTAL-01`: Candidate Portal served at `/portal/` with landing gate at `/`, self-registration, public exam catalog, session transfers, and 60-minute password reset.
- `REQ-EG-PORTAL-02`: Time-window gated "Mulai Ujian" launcher with crash re-open button generating `examguard://launch` desktop application deep links.

---

### §2. Context & Design Reconciliation
Delivers a dedicated candidate-facing web portal. Separate authentication contexts ensure candidate and staff sessions do not conflict in the same browser. Designed primarily for laptop and desktop screens where candidates sit for proctored examinations.

---

### §3. Component Architecture
- Location: `sakti-desktop/examguard-web/portal/`
- Views: `MyExamsView.tsx`, `PublicCatalogView.tsx`, `InvitationAcceptView.tsx`, `ProfileSettingsView.tsx`
- Dialogs: `LaunchExamDialog.tsx` (renders deep link and `eg-sim` instructions)

---

### §4. API Integrations
- `POST /api/v1/candidate/auth/register` & `/login`
- `POST /api/v1/candidate/auth/password-reset/request` & `/confirm`
- `GET /api/v1/candidate/enrollments` (Includes `can_launch`, `launch_reason`, and countdowns)
- `POST /api/v1/candidate/enrollments/{id}/launch` (Generates launch token)

---

### §5. Mandatory 5 UI States
1. **Loading State**: Exam card pulse skeletons while querying active registrations.
2. **Empty State**: "Belum ada ujian yang terdaftar. Lihat Katalog Ujian Publik."
3. **Check-in Pending State**: Card shows countdown badge: "Check-in dibuka dalam 2 hari 3 jam".
4. **Active Launch State**: Prominent yellow border and active "Mulai Ujian" button.
5. **Crash Resume State**: Button transitions to "Buka kembali ExamGuard" to allow re-entry after an unexpected client shutdown.

---

### §6. Edge Cases
- Candidate clicks "Mulai Ujian" before check-in opens or after `latest_start` $\to$ Button is disabled with clear explanation tooltip.
- Candidate receives an institutional invite email $\to$ Direct link previews exam details and retains invitation state until account creation is completed.

---

### §7. Tests Required
- 10 automated browser tests covering full flow: registration $\to$ email verification $\to$ invite acceptance $\to$ catalog enrollment $\to$ launch link generation.
- Crash recovery re-launch verification.

---

### §8. Out of Scope
- Native desktop installer packaging (Wave 3).

---

### §9. Acceptance Checklist
- [x] Candidate portal loads at `/portal/` with independent auth sessions.
- [x] "Mulai Ujian" button strictly respects check-in and start time windows.
- [x] Password reset links expire after 60 minutes and revoke all existing sessions.
- [x] Deep link dialog provides instructions for `eg-sim` headless testing.

---

### §10. Security Checklist
- [x] Password reset tokens are single-use and invalidate upon execution.
- [x] Candidate session cannot access administrative endpoints.

