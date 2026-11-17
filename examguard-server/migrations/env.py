"""Alembic environment. Migrations run as the schema-owner role."""
from alembic import context
from sqlalchemy import create_engine, pool

from examguard.config import get_settings

config = context.config


def _url() -> str:
    return config.attributes.get("url") or get_settings().migration_database_url


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=None, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    raise SystemExit("Offline mode is not supported; run against a database.")
run_migrations_online()
