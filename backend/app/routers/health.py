"""
Health-check router.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Returns service health and database connectivity status.
    """
    db_status = "disconnected"
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "error"

    return {
        "status": "ok",
        "database": db_status,
        "version": "0.1.0",
    }
