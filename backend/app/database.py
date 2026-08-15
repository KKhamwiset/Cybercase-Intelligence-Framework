import logging
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# Disable verbose SQLAlchemy engine SQL query logging in container logs
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

# ── Engine ───────────────────────────────────────────────────────────────────
engine = create_async_engine(
    "postgresql+asyncpg://",
    connect_args={
        "host": settings.postgres_host,
        "port": int(settings.postgres_port),
        "user": settings.postgres_user,
        "password": settings.postgres_password,
        "database": settings.postgres_db,
    },
    echo=False,
    pool_pre_ping=True,
)

# ── Session factory ──────────────────────────────────────────────────────────
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Base class for all models ────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


async def init_db_schema() -> None:
    """Create declared ORM tables when migrations are not configured."""
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ── Dependency for route injection ───────────────────────────────────────────
async def get_db():
    """Yield an async DB session for FastAPI dependency injection."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
