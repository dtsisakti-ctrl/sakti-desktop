# 00-assignments: ExamGuard Team Roster & Backlog Status

---

## 1. ExamGuard Team Roster

| Role Code | Title | Core Modules | Default Reviewer |
| :--- | :--- | :--- | :--- |
| **`EG-BE`** | Server & Protocol Lead | FastAPI Core, State Engine, Ed25519 Signing, Integration API | Tech Lead |
| **`EG-FE`** | Web Applications Lead | React 19 Admin Web (`/admin/`), Candidate Portal (`/portal/`) | Tech Lead |
| **`EG-CL`** | Desktop Client Lead | Rust Core, CEF Embedding, ONNX Runtime AI Proctoring | Tech Lead |

---

## 2. Work-Item Backlog Status (Current Condition vs Upcoming)

| BL Spec ID | Module | Title | Owner | Phase / Wave | Status | Depends On | Blocks |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`BL-EG-01`** | 10-core-server | Attempt State Machine, Timing Service & Scheduler Engine | EG-BE | Phase 1b | **DONE** | - | BL-EG-02 |
| **`BL-EG-02`** | 10-core-server | Client Wire Protocol, Ed25519 Signing (`EG-Sig`) & Key Sets | EG-BE | Phase 1c-1 | **DONE** | BL-EG-01 | BL-EG-03 |
| **`BL-EG-03`** | 20-integration | Integration API for LMS, Signed Webhooks & Challenge Unlock | EG-BE | Phase 1c-2 | **DONE** | BL-EG-02 | BL-EG-04 |
| **`BL-EG-04`** | 30-admin-web | Admin Web, Live Monitoring Console & Incident Timeline | EG-FE | Phase 3a | **DONE** | BL-EG-03 | BL-EG-05 |
| **`BL-EG-05`** | 40-candidate-portal| Candidate Portal (`/portal/`), Exam Catalog & Launch Tokens | EG-FE | Phase 3b-1 | **DONE** | BL-EG-04 | BL-EG-06 |
| **`BL-EG-06`** | 50-upcoming | Advanced Admin Web (Org & Member Mgmt, Hash-Chain Audit, LMS Keys) | EG-FE | Phase 3b-2 | **FULL** | BL-EG-05 | BL-EG-07 |
| **`BL-DESK-01`**| 50-upcoming | OS Kiosk Lockdown Engine & Process Guardian (SEB Replica) | EG-CL | Phase 4 | **FULL** | SPEC-DESK-01 | BL-DESK-02 |
| **`BL-DESK-02`**| 50-upcoming | Participant WebView Embedding & Attestation Token | EG-CL | Phase 4 | **FULL** | BL-DESK-01 | - |
| **`BL-EG-07`** | 50-upcoming | Cross-Platform Desktop Client (Rust + CEF + ONNX Runtime) | EG-CL | Phase 5 | **STUB** | BL-EG-02 | - |

