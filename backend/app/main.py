"""
FastAPI Application — TSR_Mitre Backend
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine
from app.routers import cases, health, rag, reports, user


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


from app.services.reporting.generator import ReportGenerator

app = FastAPI(
    title="Cybercase Framework API",
    description="APIs for the Cybercase Framework project",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.report_gen = ReportGenerator()

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(health.router, prefix="/api/v1")
app.include_router(user.router, prefix="/api/v1")
app.include_router(rag.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(cases.router, prefix="/api/v1")

# Wrap the full ASGI app so even unhandled 500 responses carry CORS headers.
app = CORSMiddleware(
    app,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
