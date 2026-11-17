"""Attempt state & timing engine: attempt timing columns, state transitions, device sessions,
command outbox, invigilator assignments.

Revision ID: 0002
Revises: 0001
"""
from pathlib import Path
import re

from alembic import context, op

from examguard.config import get_settings

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

SQL_FILE = Path(__file__).resolve().parents[1] / "sql" / "0002_state_engine.sql"


def _app_role() -> str:
    role = context.config.attributes.get("app_role") or get_settings().app_role
    if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", role):
        raise ValueError(f"invalid role name: {role!r}")
    return role


def upgrade() -> None:
    sql = SQL_FILE.read_text(encoding="utf-8").replace("__APP_ROLE__", _app_role())
    raw = op.get_bind().connection.dbapi_connection
    with raw.cursor() as cur:
        cur.execute(sql)


def downgrade() -> None:
    raise NotImplementedError("restore from backup or recreate the database (development).")
