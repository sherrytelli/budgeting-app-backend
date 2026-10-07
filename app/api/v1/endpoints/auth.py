"""Authentication endpoints: register, login, and profile retrieval.

Provides user registration with password hashing, JWT-based login
via OAuth2 password flow, and a protected ``/me`` endpoint to
retrieve the current user's profile.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.api.deps import ActiveUserDep, get_db
from app.core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import Token
from app.schemas.user import UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["authentication"])

settings = get_settings()


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    data: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserRead:
    """Register a new user account.

    Creates a new User record with a hashed password. Returns the
    user profile (without the password hash).

    Args:
        data: Validated registration data.
        db: Database session.

    Returns:
        The created UserRead schema.

    Raises:
        HTTPException: If a user with this email already exists (409).
    """
    existing = await db.execute(
        select(User).where(User.email == data.email),
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@router.post(
    "/login",
    response_model=Token,
    summary="Login and get JWT token",
)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """Authenticate a user and return a JWT access token.

    Accepts credentials via OAuth2 password form (username/email + password),
    verifies them, and returns a short-lived JWT token.

    Args:
        form_data: OAuth2 password form with email and password.
        db: Database session.

    Returns:
        Token with access_token and token_type.

    Raises:
        HTTPException: If credentials are invalid (401).
    """
    result = await db.execute(
        select(User).where(User.email == form_data.username),
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        user_id=str(user.id),
        expires_delta=access_token_expires,
    )

    return Token(access_token=access_token)


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get current user profile",
)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserRead:
    """Retrieve the authenticated user's profile.

    This is a protected endpoint that requires a valid Bearer JWT token.

    Args:
        current_user: The authenticated user from JWT.

    Returns:
        The current user's profile.
    """
    return current_user
