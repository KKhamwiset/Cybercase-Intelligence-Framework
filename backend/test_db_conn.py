import asyncio

from app.config import settings
from app.database import engine
from sqlalchemy import text


async def test_connection():
    print(f"Testing database connection with URL: {settings.database_url}")
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            print(f"Connection successful! Result: {result.fetchone()}")
    except Exception as e:
        print(f"Connection failed: {e}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(test_connection())
