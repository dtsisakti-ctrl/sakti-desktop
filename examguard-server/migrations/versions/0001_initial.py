"""Initial schema: tenancy, accounts, exams, registration, audit chain, RLS.

Revision ID: 0001
Revises:
"""
from pathlib import Path
import re

from alembic import context, op

from examguard.config import get_settings

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SQL_FILE = Path(__file__).resolve().parents[1] / "sql" / "0001_initial.sql"


def _app_role() -> str:
    role = context.config.attributes.get("app_role") or get_settings().app_role
    if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", role):
        raise ValueError(f"invalid role name: {role!r}")
    return role


def upgrade() -> None:
    sql = SQL_FILE.read_text(encoding="utf-8").replace("__APP_ROLE__", _app_role())
    # Execute through the raw DB-API cursor so the multi-statement script (with $$ bodies)
    # is sent as-is, without SQLAlchemy bind-parameter parsing.
    raw = op.get_bind().connection.dbapi_connection
    with raw.cursor() as cur:
        cur.execute(sql)


def downgrade() -> None:
    raise NotImplementedError("0001 is the baseline; drop and recreate the database instead.")
