# BL-EG-<nn> — <Title>

|                |                                              |
| -------------- | -------------------------------------------- |
| **Owner**      | EG-BE / EG-FE / EG-CL                        |
| **Phase**      | Phase 1b / 1c / 3a / 3b-1 / 3b-2             |
| **Estimate**   | N days                                       |
| **Depends on** | Prior BL IDs                                 |
| **Blocks**     | Downstream BL IDs                            |
| **Repo**       | sakti-desktop                                |
| **Branch**     | feat/BL-EG-<nn>-<slug>                       |
| **Status**     | DONE / FULL / STUB                           |

> Read first: `docs/backlog/00-README.md`, `00-standards/protocol-security.md`,
> `00-standards/state-machines.md`, `00-standards/timing-engine.md`.

---

### §1. Requirements Covered
- PRD § references and requirement descriptions.

### §2. Context & Architecture Reconciliation
- How this work-item connects with the authoritative server, web UI, or desktop client.

### §3. Data Model (Database Layer)
- SQLAlchemy models, Alembic migration changes, RLS policies.

### §4. Protocol & API Endpoints
- REST endpoints, request/response formats, wire protocols (`EG-Sig`), WebSocket envelopes.

### §5. Service & Implementation Logic
- State transitions, algorithms, error codes.

### §6. Edge Cases
- Disconnection timeouts, replay attacks, concurrent commands.

### §7. Tests Required
- Unit tests (`pytest`), browser tests (`vitest`/Playwright).

### §8. Out of Scope
- Deferred requirements.

### §9. Acceptance Checklist
- [ ] Features verified against PRD requirements.

### §10. Security Checklist
- [ ] Ed25519 signatures verified.
- [ ] Multi-tenant RLS boundaries confirmed.

