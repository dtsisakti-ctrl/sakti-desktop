# 00-README: ExamGuard Engineering Manual

This manual governs reading sequence, branch management, and Pull Request review discipline for the ExamGuard platform.

---

## 1. Reading Order

1. `docs/backlog/00-START-HERE.md` (Server setup, seed accounts & quickstart)
2. `docs/backlog/00-assignments.md` (Active ticket & assigned role)
3. `docs/backlog/00-standards/` (Protocol security, state machines, timing, data access, UI, DoD)
4. `docs/backlog/00-schema-decisions.md` (Database models & migrations 0001–0006)
5. `docs/backlog/<module>/BL-*.md` (Your 10-section engineering contract)

---

## 2. Pull Request Mirror Discipline

Before opening a PR:
1. **Branch**: `feat/BL-EG-<nn>-<slug>` or `fix/BL-EG-<nn>-<slug>`.
2. **Commit**: Conventional Commits: `feat(BL-EG-<nn>): <message>`.
3. **PR Description**: Include **§9 Acceptance Checklist** and **§10 Security Checklist** from your spec verbatim.
4. **Verification**: 
   - Server: All tests pass (`pytest tests/`).
   - Web: Vitest and Playwright browser suites pass (`npm test`, `npx playwright test`).

