"""Shared dependencies for API endpoints.

This module provides reusable FastAPI dependency injection functions
that are imported by all endpoint routers.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentUserDep, get_current_user
from app.models.user import User


# --- Re-exports ---

__all__ = [
    "get_db",
    "get_current_user",
    "get_current_active_user",
    "PaginationParams",
    "get_db_paginated",
    "CurrentUserDep",
]


# --- Active User Dependency ---


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Return the current user only if their account is active.

    Raises HTTP 403 if the user exists but is_inactive.

    Args:
        current_user: The authenticated user from get_current_user.

    Returns:
        The active User instance.

    Raises:
        HTTPException: If the user's account is inactive.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    return current_user


# Type alias for the active user dependency
ActiveUserDep = Annotated[User, Depends(get_current_active_user)]


# --- Pagination ---


class PaginationParams(BaseModel):
    """Standard pagination parameters.

    Attributes:
        limit: Maximum number of items to return (default: 50, max: 100).
        offset: Number of items to skip for pagination (default: 0).
    """

    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


def get_pagination_params(
    limit: int = 50,
    offset: int = 0,
) -> PaginationParams:
    """FastAPI dependency that extracts and validates pagination query parameters.

    Args:
        limit: Maximum number of items to return.
        offset: Number of items to skip.

    Returns:
        A PaginationParams instance with validated values.
    """
    return PaginationParams(limit=limit, offset=offset)


# Type alias for the pagination dependency
PaginationDep = Annotated[PaginationParams, Depends(get_pagination_params)]
