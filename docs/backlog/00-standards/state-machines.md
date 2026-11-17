# 00-standards/state-machines: Formal State Machine Standards (PRD §9 & §10)

ExamGuard separates exam-level status from individual candidate attempt status.

---

## 1. Exam State Machine (PRD §9)

```
DRAFT ───► READY ───► RUNNING ───► CLOSED
  │          │
  └──────────┴────────► CANCELLED
```

- `DRAFT`: Questions/policies being configured.
- `READY`: Open for enrollment and check-in.
- `RUNNING`: Exam session active. New enrollments and invitations are rejected.
- `CLOSED`: All attempts finalized.
- `CANCELLED`: Exam cancelled before or during execution.

---

## 2. Attempt State Machine (PRD §10)

```
REGISTERED ───► CHECKED_IN ───► ACTIVE ───► COMPLETED
                   │              │   ▲
                   │              ▼   │
                   │       INTERRUPTED│
                   │              │   │
                   │              ▼   │
                   └────────► PAUSED ─┘
                                  │
                                  ▼
                         TERMINATED / EXPIRED / NO_SHOW
```

### Key State Transitions & Invariants:
1. `ACTIVE ──► INTERRUPTED`: Triggered automatically when WebSocket drops or when heartbeat exceeds `interruption_threshold` (default **30 seconds**).
2. `INTERRUPTED ──► ACTIVE`: Resumed automatically upon receiving any authenticated, signed request from the active device session. Jeda $< 10$ seconds does not log an unmonitored incident.
3. `ACTIVE / PAUSED ──► TERMINATED`: Requires an explicit mandatory `reason_category` (e.g. `CHEATING_MALPRACTICE`, `UNAUTHORIZED_DEVICE`, `IRRECOVERABLE_HARDWARE_FAILURE`).
4. **State Version Invariant**: Every transition increments `state_version` by 1. Commands with a stale `state_version` are rejected to prevent race conditions.

