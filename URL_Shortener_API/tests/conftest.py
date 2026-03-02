import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.redis_client import get_redis_dep

TEST_DATABASE_URL = (
    "postgresql+asyncpg://urluser:urlpass@localhost:5432/urlshortener_test"
)


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session")
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    """Yields a session that is rolled back after each test."""
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


# ---------------------------------------------------------------------------
# Redis fixture (uses fakeredis for isolation)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def fake_redis():
    import fakeredis.aioredis as fakeredis
    redis = fakeredis.FakeRedis(decode_responses=True)
    yield redis
    await redis.flushall()
    await redis.aclose()


# ---------------------------------------------------------------------------
# HTTP client fixture with dependency overrides
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client(db_session: AsyncSession, fake_redis):
    async def override_db():
        yield db_session

    async def override_redis():
        yield fake_redis

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis_dep] = override_redis

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Convenience fixtures: registered user + token
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def registered_user(client: AsyncClient) -> dict:
    resp = await client.post(
        "/api/v1/users",
        json={"email": "testuser@example.com", "password": "SecurePass1!"},
    )
    assert resp.status_code == 201
    return resp.json()


@pytest_asyncio.fixture
async def user_token(client: AsyncClient, registered_user) -> str:
    resp = await client.post(
        "/api/v1/tokens",
        data={"username": "testuser@example.com", "password": "SecurePass1!"},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def user_headers(user_token: str) -> dict:
    return {"Authorization": f"Bearer {user_token}"}
