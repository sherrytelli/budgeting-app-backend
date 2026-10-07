"""User-related Pydantic schemas.

Defines request/response schemas for user CRUD operations.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    """Base user schema with common fields."""

    email: EmailStr = Field(description="User email address")
    full_name: str | None = Field(default=None, max_length=100, description="User's full name")


class UserCreate(UserBase):
    """Schema for creating a new user."""

    password: str = Field(min_length=8, max_length=128, description="User password (min 8 characters)")


class UserRead(UserBase):
    """Schema for reading user data (excludes password)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="User unique identifier")
    is_active: bool = Field(description="Whether the user account is active")
    created_at: datetime = Field(description="Account creation timestamp (UTC)")
    updated_at: datetime = Field(description="Last update timestamp (UTC)")


class UserUpdate(BaseModel):
    """Schema for updating user profile fields."""

    full_name: str | None = Field(default=None, max_length=100, description="Updated full name")
