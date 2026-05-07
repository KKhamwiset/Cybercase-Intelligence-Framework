"""
Pydantic schemas for User request / response validation.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, ConfigDict


class UserCreate(BaseModel):
    """Schema for creating a new user."""
    email: EmailStr
    display_name: str | None = None


class UserRead(BaseModel):
    """Schema for reading / returning a user."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str | None
    created_at: datetime
    updated_at: datetime
