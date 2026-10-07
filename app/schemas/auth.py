"""Authentication-related Pydantic schemas.

Defines request/response schemas for user registration, login, and JWT token handling.
"""

from pydantic import BaseModel, EmailStr, Field


class Token(BaseModel):
    """JWT token response."""

    access_token: str = Field(description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type (always 'bearer')")


class TokenData(BaseModel):
    """Decoded JWT token payload.

    Used internally to extract the user ID from a validated token.
    """

    sub: str | None = Field(default=None, description="User ID string from JWT 'sub' claim")


class UserRegister(BaseModel):
    """Schema for user registration requests."""

    email: EmailStr = Field(description="User email address")
    password: str = Field(min_length=8, max_length=128, description="User password (min 8 characters)")
    full_name: str | None = Field(default=None, max_length=100, description="User's full name")


class UserLogin(BaseModel):
    """Schema for user login requests."""

    email: EmailStr = Field(description="User email address")
    password: str = Field(description="User password")
