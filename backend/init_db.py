import asyncio

from app.database import Base, engine
from app.models.user import (
    User,  # noqa: F401 # Import all models to ensure they are registered
)


async def init_db():
    print("Initializing database tables...")
    try:
        async with engine.begin() as conn:
            # This will create all tables defined in models
            await conn.run_sync(Base.metadata.create_all)
        print("Database tables created successfully!")
    except Exception as e:
        print(f"Failed to initialize database: {e}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init_db())
