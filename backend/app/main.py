"""FastAPI application for the chat-only backend."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine
from app.routers import chat, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        print("[STARTUP] Database connection verified.")
    except Exception as e:
        print(f"[STARTUP] Database connection failed: {e}")
        print("[STARTUP] Backend will start, but database endpoints will fail.")
    yield
    await engine.dispose()
    print("[SHUTDOWN] Database engine disposed.")


app = FastAPI(
    title="Cybercase Framework API",
    description="Persistent chat APIs for the Cybercase Framework project",
    version="1.0.0",
    lifespan=lifespan,
)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(health.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")

# Wrap the full ASGI app so even unhandled 500 responses carry CORS headers.
app = CORSMiddleware(
    app,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
