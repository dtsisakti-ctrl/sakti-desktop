# BL-EG-01 — Attempt State Machine, Timing Service & Scheduler Engine

|                |                                              |
| -------------- | -------------------------------------------- |
| **Owner**      | EG-BE                                        |
| **Phase**      | Phase 1b                                     |
| **Estimate**   | 5 days                                       |
| **Depends on** | None (Phase 1a foundation)                   |
| **Blocks**     | BL-EG-02                                     |
| **Repo**       | sakti-desktop                                |
| **Branch**     | feat/BL-EG-01-state-machine-timing-engine    |
| **Status**     | **DONE**                                     |

---

### §1. Requirements Covered
- `REQ-EG-STATE-01`: Formal Attempt State Machine with atomic transition validation, row locking on `state_version`, and mandatory reason categories for `TERMINATED`.
- `REQ-EG-TIME-01`: Precision Timing Engine implementing `FIXED_END` and `FULL_DURATION` modes, pause timer logic, and clock offset tracking.
- `REQ-EG-SCHED-01`: Background scheduler running every 2s detecting `NO_SHOW`, `EXPIRED`, and simultaneous `INTERRUPTED` + `OFFLINE` status within $\le 2$ seconds.

---

### §2. Context & Architecture
Acts as the single authoritative source of truth for all exam lifecycle events. Built with FastAPI and PostgreSQL with Row-Level Security. Enforces an immutable transition table preventing invalid state jumps.

---

### §3. Data Model (Database Layer)
- Alembic Migration: `0002_attempts_state_engine.py`
- Models: `Attempt`, `StateTransition`, `InvigilatorAssignment`, `Exam`
- Key Columns:
  - `Attempt.status`: `REGISTERED`, `CHECKED_IN`, `ACTIVE`, `INTERRUPTED`, `PAUSED`, `COMPLETED`, `TERMINATED`
  - `Attempt.state_version`: Monotonically increasing integer
  - `Attempt.termination_reason_category`: Mandatory enum string when terminating

---

### §4. REST Endpoints
- `POST /api/v1/org/attempts/{id}/pause` (Pause attempt with timer mode)
- `POST /api/v1/org/attempts/{id}/resume` (Resume attempt, recalculating deadline)
- `POST /api/v1/org/attempts/{id}/add-time` (Grant individual minute extension)
- `POST /api/v1/org/attempts/{id}/force-submit` (Transition to `COMPLETED`)
- `POST /api/v1/org/attempts/{id}/terminate` (Transition to `TERMINATED` with category)

---

### §5. Service & Business Logic
- State transitions validate against a single comprehensive state transition matrix.
- Scheduler runs with PostgreSQL advisory locks to prevent dual execution across multiple worker nodes.

---

### §6. Edge Cases
- Late start within check-in window automatically clamps to `window_end` in `FIXED_END` mode.
- Stale commands rejected when client `state_version` lags behind the database.

---

### §7. Tests Required
- 12x18 status/trigger matrix test suite.
- Reopen and reinstate lifecycle assertions.

---

### §8. Out of Scope
- Direct audio streaming proctoring (Wave 3).

---

### §9. Acceptance Checklist
- [x] All state transitions validate atomically against database.
- [x] Deadline calculations accurately match PRD §11 formulas.
- [x] Disconnection triggers INTERRUPTED and OFFLINE simultaneously within 2 seconds.

---

### §10. Security Checklist
- [x] RLS policies prevent invigilators from seeing unassigned exams.
- [x] State transitions emit audit log entries via `eg_audit_append()`.

