import pytest
import asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.main import app
from app.database import Base, get_db
from app.models.user import User, UserRole
from app.core.security import hash_password

TEST_DATABASE_URL = "postgresql+asyncpg://compras_sei:compras_sei_pass@localhost:5432/compras_sei_test"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def admin_user(db: AsyncSession) -> User:
    user = User(
        name="Test Admin",
        email="admin_test@ifpe.edu.br",
        password_hash=hash_password("Admin@123456"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@pytest.fixture
async def regular_user(db: AsyncSession) -> User:
    user = User(
        name="Test User",
        email="user_test@ifpe.edu.br",
        password_hash=hash_password("User@123456"),
        role=UserRole.USER,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@pytest.fixture
async def admin_token(client: AsyncClient, admin_user: User) -> str:
    response = await client.post("/api/v1/auth/login", json={
        "email": "admin_test@ifpe.edu.br",
        "password": "Admin@123456",
    })
    return response.json()["access_token"]


@pytest.fixture
async def user_token(client: AsyncClient, regular_user: User) -> str:
    response = await client.post("/api/v1/auth/login", json={
        "email": "user_test@ifpe.edu.br",
        "password": "User@123456",
    })
    return response.json()["access_token"]
