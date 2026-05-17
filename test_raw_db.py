import asyncio

import asyncpg


async def test_raw():
    print("Testing raw asyncpg connection to 127.0.0.1:5433...")
    try:
        conn = await asyncpg.connect(
            user="postgres",
            password="postgres",
            database="tsr_mitre",
            host="127.0.0.1",
            port=5433,
        )
        print("Raw connection successful!")
        await conn.close()
    except Exception as e:
        print(f"Raw connection failed: {e}")


if __name__ == "__main__":
    asyncio.run(test_raw())
