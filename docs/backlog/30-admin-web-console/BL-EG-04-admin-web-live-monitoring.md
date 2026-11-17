# BL-EG-04 — Admin Web, Live Monitoring Console & Incident Review Timeline

|                |                                              |
| -------------- | -------------------------------------------- |
| **Owner**      | EG-FE                                        |
| **Phase**      | Phase 3a                                     |
| **Estimate**   | 5 days                                       |
| **Depends on** | BL-EG-03                                     |
| **Blocks**     | BL-EG-05                                     |
| **Repo**       | sakti-desktop                                |
| **Branch**     | feat/BL-EG-04-admin-web-live-monitoring      |
| **Status**     | **DONE**                                     |

---

### §1. Requirements Covered
- `REQ-EG-ADMIN-01`: Admin Web dashboard served by FastAPI at `/admin/`, displaying live monitoring console with candidate tiles and emergency action controls.
- `REQ-EG-INC-01`: Incident review timeline with localized Indonesian event names ("Keluar dari jendela ujian", "Lebih dari satu orang"), severity badges, AI confidence scores, and review statuses (`OPEN`, `REVIEWED`, `DISMISSED`, `ESCALATED`).

---

### §2. Context & Design Reconciliation
Built with React, Vite, and TypeScript. Compiled static assets are served directly by the Python server at `/admin/`, eliminating Node.js runtime dependencies in production. Polling executes every 2 seconds during active surveillance, meeting the sub-3-second real-time latency target.

---

### §3. Component Architecture
- Location: `sakti-desktop/examguard-web/admin/`
- Views: `LiveMonitoringView.tsx`, `CandidateDetailDrawer.tsx`, `ExamsListView.tsx`
- Modals: `IncidentReviewDialog.tsx`, `EmergencyUnlockModal.tsx`, `AddTimeModal.tsx`

---

### §4. API Integrations
- `GET /api/v1/org/dashboard` (Summary cards: active, interrupted, incident count)
- `GET /api/v1/org/exams/{id}/attempts` (Polls candidate status matrix every 2s)
- `GET /api/v1/org/attempts/{id}` (Retrieves event timeline & incident detail)
- `PATCH /api/v1/org/incidents/{id}` (Updates review status: `REVIEWED`, `DISMISSED`, `ESCALATED`)

---

### §5. Mandatory 5 UI States
1. **Loading State**: Pulse skeletons on candidate surveillance tiles.
2. **Empty State**: "Belum ada peserta yang memulai sesi ujian ini."
3. **Error State**: Actionable reconnection banner if server polling drops.
4. **Forbidden State**: Invigilators accessing exams they are not assigned to see 403 Forbidden.
5. **Happy Path**: Live monitoring tiles indicating online status, active time remaining, and red clickable incident count badges.

---

### §6. Edge Cases
- Invigilator clicks on an incident badge $\to$ Directly opens the Candidate Detail drawer scrolled to the Incident Review section (PRD v0.3.6).
- Attempt disconnected $\to$ Tile immediately displays "Terputus" and "Offline" in unison within $\le 2$ seconds.

---

### §7. Tests Required
- 12 automated browser tests verifying incident review, emergency actions, and status updates.
- Fast polling interval assertion during visible browser tab state.

---

### §8. Out of Scope
- WebRTC video streaming directly in the Python server (covered in Phase 3b-2 / SAKTI integration).

---

### §9. Acceptance Checklist
- [x] Admin Web loads at `/admin/` without requiring external Node server.
- [x] Live monitoring updates candidate states within 2 seconds.
- [x] Incident timeline renders localized Indonesian titles and review dialogs.
- [x] Emergency unlock response can be calculated directly from the console.

---

### §10. Security Checklist
- [x] Session tokens scoped to organization staff accounts.
- [x] Invigilator permissions restricted to assigned exams.

