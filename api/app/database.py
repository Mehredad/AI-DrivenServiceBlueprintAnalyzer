from fastapi import HTTPException
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

settings = get_settings()

_db_url = settings.database_url

# Supabase (and many hosting providers) give postgres:// or postgresql:// —
# asyncpg requires the postgresql+asyncpg:// dialect prefix.
if _db_url and not _db_url.startswith("sqlite"):
    if _db_url.startswith("postgres://"):
        _db_url = "postgresql+asyncpg://" + _db_url[len("postgres://"):]
    elif _db_url.startswith("postgresql://"):
        _db_url = "postgresql+asyncpg://" + _db_url[len("postgresql://"):]

_db_ready = bool(_db_url)

if _db_ready:
    _is_sqlite = _db_url.startswith("sqlite")
    _engine_kw: dict = {"echo": not settings.is_production}
    if not _is_sqlite:
        # statement_cache_size=0 required for Supabase PgBouncer (transaction pool mode)
        _engine_kw.update({
            "pool_pre_ping": True,
            "pool_size": 5,
            "max_overflow": 10,
            "connect_args": {"statement_cache_size": 0},
        })
    engine = create_async_engine(_db_url, **_engine_kw)
    AsyncSessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
else:
    engine = None            # type: ignore[assignment]
    AsyncSessionLocal = None  # type: ignore[assignment]


class Base(DeclarativeBase):
    pass


_DB_NOT_CONFIGURED = HTTPException(
    status_code=503,
    detail="Database not configured. Set DATABASE_URL in Vercel → Settings → Environment Variables.",
)


async def get_db() -> AsyncSession:
    """FastAPI dependency — yields a session, commits on success, rolls back on error."""
    if not _db_ready:
        raise _DB_NOT_CONFIGURED
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
