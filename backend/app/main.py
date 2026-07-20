"""
FastAPI Application — TSR_Mitre Backend
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine
from app.middleware.report_body_limit import ReportBodyLimitMiddleware
from app.routers import health, rag, user, chat


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    # Startup: verify DB connection
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        print("[STARTUP] Database connection verified.")
    except Exception as e:
        print(f"[STARTUP] Database connection failed: {e}")
        print("[STARTUP] Backend will start, but database endpoints will fail.")

    yield
    # Shutdown: dispose engine pool
    await engine.dispose()
    print("[SHUTDOWN] Database engine disposed.")


app = FastAPI(
    title="TSR Mitre API",
    description="Backend API for the TSR Mitre Thai-law RAG platform",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ReportBodyLimitMiddleware)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(health.router, prefix="/api/v1")
app.include_router(user.router, prefix="/api/v1")
app.include_router(rag.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
