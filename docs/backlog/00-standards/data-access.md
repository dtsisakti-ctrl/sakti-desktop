# 00-standards/data-access: Server Data Access & SQLAlchemy Patterns

---

## 1. Asynchronous SQLAlchemy & Repository Layer
- Database sessions run under SQLAlchemy 2.0 with async engine (`asyncpg`).
- Queries affecting tenant entities must execute within the current organization context:
  ```python
  stmt = select(Attempt).where(
      Attempt.id == attempt_id,
      Attempt.org_id == ctx.org_id
  )
  ```

---

## 2. Distributed Locking & Concurrency
- Scheduler runs with `FOR UPDATE SKIP LOCKED` or PostgreSQL advisory locks to guarantee that multiple running server instances do not process duplicate attempt state transitions or heartbeat timeouts.

---

## 3. Migration Standards (Alembic)
- All schema changes must be declared in Alembic migration files under `migrations/versions/`.
- Every migration must provide clean `upgrade()` and `downgrade()` routines.

