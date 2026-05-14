from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserRead
from typing import List

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/", response_model=List[UserRead])
async def get_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User))
    return result.scalars().all()

@router.post("/", response_model=UserRead)
async def create_user(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    # Check if user exists
    result = await db.execute(select(User).where(User.email == user_in.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user = User(
        email=user_in.email,
        display_name=user_in.display_name
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
