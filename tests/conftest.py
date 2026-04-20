"""
Test configuration — async test client with a SQLite test database.
Each test function gets a clean database (no Postgres needed in CI).
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))

from app.main import app
from app.database import Base, get_db

TEST_DB_URL = "sqlite+aiosqlite:///./test_blueprint.db"

_engine = create_async_engine(TEST_DB_URL, echo=False)
_SessionLocal = async_sessionmaker(
    bind=_engine, class_=AsyncSession,
    expire_on_commit=False, autoflush=False,
)


@pytest_asyncio.fixture(autouse=True)
async def reset_db():
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    if os.path.exists("./test_blueprint.db"):
        os.remove("./test_blueprint.db")


@pytest_asyncio.fixture
async def db():
    async with _SessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(db):
    async def _override():
        yield db
    app.dependency_overrides[get_db] = _override
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def user_payload():
    return {
        "email": "researcher@example.com",
        "password": "Secure123",
        "full_name": "Dr. A. Researcher",
        "role": "designer",
    }


@pytest_asyncio.fixture
async def auth_headers(client, user_payload):
    resp = await client.post("/api/auth/register", json=user_payload)
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def board(client, auth_headers):
    resp = await client.post(
        "/api/boards",
        json={"title": "Test Blueprint", "domain": "healthcare"},
        headers=auth_headers,
    )
    return resp.json()
