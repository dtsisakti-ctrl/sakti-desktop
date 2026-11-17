"""Engine, sessions and the per-transaction security context used by RLS."""
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings

CONTEXTS = {"system", "platform", "staff", "candidate", "public"}


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True)


def reset_engine() -> None:
    if get_engine.cache_info().currsize:
        get_engine().dispose()
    get_engine.cache_clear()


def new_session() -> Session:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, autoflush=True)()


def _s(v: UUID | str | None) -> str:
    return "" if v is None else str(v)


def set_context(
    db: Session,
    ctx: str,
    *,
    org_id: UUID | None = None,
    user_id: UUID | None = None,
    candidate_id: UUID | None = None,
) -> None:
    """Set transaction-local GUCs read by the RLS policies (see migrations/sql)."""
    if ctx not in CONTEXTS:
        raise ValueError(f"unknown context {ctx}")
    db.execute(
        text(
            "SELECT set_config('app.ctx', :c, true), set_config('app.org_id', :o, true),"
            " set_config('app.user_id', :u, true), set_config('app.candidate_id', :k, true)"
        ),
        {"c": ctx, "o": _s(org_id), "u": _s(user_id), "k": _s(candidate_id)},
    )


@contextmanager
def elevated(db: Session, ctx: str = "system") -> Iterator[None]:
    """Temporarily switch to a privileged context inside the current transaction.

    Used only for narrow, well-defined lookups (login, token redemption, outbox).
    """
    db.flush()
    prev = db.execute(
        text(
            "SELECT current_setting('app.ctx', true), current_setting('app.org_id', true),"
            " current_setting('app.user_id', true), current_setting('app.candidate_id', true)"
        )
    ).one()
    db.execute(text("SELECT set_config('app.ctx', :c, true)"), {"c": ctx})
    try:
        yield
        db.flush()
    finally:
        db.execute(
            text(
                "SELECT set_config('app.ctx', :c, true), set_config('app.org_id', :o, true),"
                " set_config('app.user_id', :u, true), set_config('app.candidate_id', :k, true)"
            ),
            {"c": prev[0] or "", "o": prev[1] or "", "u": prev[2] or "", "k": prev[3] or ""},
        )


@contextmanager
def transaction(ctx: str = "system", **ids) -> Iterator[Session]:
    """Stand-alone unit of work (CLI, scripts). Commits on success."""
    db = new_session()
    try:
        with db.begin():
            set_context(db, ctx, **ids)
            yield db
    finally:
        db.close()
