# 00-standards/definition-of-done: ExamGuard Definition of Done

A Pull Request is ready for merge only when:

- [ ] All Python server tests pass (`pytest tests/` $\ge 172$ tests passing).
- [ ] TypeScript compiles cleanly with zero errors (`npm run build`).
- [ ] End-to-end browser tests pass (`npx vitest` / Playwright e2e).
- [ ] RLS policies and organization scoping are verified.
- [ ] State transitions validate `state_version` increments.
- [ ] PR description includes §9 Acceptance and §10 Security checklists from the target BL spec.

