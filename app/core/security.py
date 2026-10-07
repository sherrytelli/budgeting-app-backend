"""Security utilities: password hashing with Argon2 and JWT token management."""

from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.config import get_settings
from app.core.database import get_db
from app.models.user import User

settings = get_settings()

# Password hashing using Argon2 via pwdlib
password_hash = PasswordHash.recommended()

# JWT token URL
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# --- Custom Exceptions ---


class InvalidTokenError(Exception):
    """Raised when JWT token is invalid or expired."""

    pass


class UserNotFoundError(Exception):
    """Raised when user is not found in the database."""

    pass


# --- Password Utilities ---


def hash_password(password: str) -> str:
    """Hash a password using Argon2."""
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    return password_hash.verify(plain_password, hashed_password)


# --- JWT Token Utilities ---


def create_access_token(user_id: str, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token.

    Args:
        user_id: The user ID to encode in the token (stored as 'sub' claim).
        expires_delta: Optional custom expiry duration. Defaults to settings value.

    Returns:
        Encoded JWT token string.
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    expire = datetime.now(timezone.utc) + expires_delta

    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token.

    Args:
        token: The JWT token string to decode.

    Returns:
        Decoded token payload dict.

    Raises:
        InvalidTokenError: If the token is invalid or expired.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise InvalidTokenError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise InvalidTokenError(f"Invalid token: {e}")


# --- Authentication Dependency ---


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Extract and validate the current user from a Bearer JWT token.

    This is the primary authentication dependency for protected endpoints.

    Args:
        token: Bearer token from the Authorization header.
        db: Database session.

    Returns:
        The authenticated User instance.

    Raises:
        HTTPException: If the token is invalid or user is not found.
    """
    try:
        payload = decode_access_token(token)
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            raise InvalidTokenError("Token does not contain user ID")
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


# Type alias for the current user dependency
CurrentUserDep = Annotated[User, Depends(get_current_user)]
