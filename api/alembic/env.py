"""
Alembic env.py — synchronous SQLAlchemy + psycopg2 configuration.

We intentionally use psycopg2 (sync) instead of asyncpg (async) here because
Supabase uses PgBouncer in transaction-pool mode on port 6543. asyncpg's
dialect.initialize() fires `select pg_catalog.version()` as a prepared statement
before statement_cache_size=0 takes effect, causing DuplicatePreparedStatementError.
psycopg2 does not use prepared statements for metadata queries, so it works cleanly.
"""
import os
from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context

# Import all models so Alembic can detect them
from app.models import Base  # noqa: F401

config = context.config

db_url = os.environ.get("DATABASE_URL", "")

# Normalise to a psycopg2-compatible URL (strip +asyncpg, replace postgres://)
if db_url:
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = "postgresql://" + db_url[len("postgresql+asyncpg://"):]
    elif db_url.startswith("postgres://"):
        db_url = "postgresql://" + db_url[len("postgres://"):]

if not db_url:
    import sys
    print("DATABASE_URL not set — skipping migrations.")
    sys.exit(0)

config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(db_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
