"""Budget service: CRUD operations for monthly budgets and categories.

This module handles all business logic related to monthly budgets,
including creation, retrieval, updates, and deletion. Named budgets
allow multiple budgets per month/year, with unique constraint enforcement
on (user_id, name, month, year).
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.budget import MonthlyBudget

if TYPE_CHECKING:
    from app.schemas.budget import MonthlyBudgetCreate, MonthlyBudgetUpdate

__all__ = [
    "create_monthly_budget",
    "delete_budget",
    "get_budget_with_categories",
    "get_current_budget",
    "get_user_budgets",
    "update_budget",
]


# --- Budget CRUD Operations ---


async def create_monthly_budget(
    db: AsyncSession,
    user_id: UUID,
    data: MonthlyBudgetCreate,
) -> MonthlyBudget:
    """Create a new named monthly budget for the user.

    Allows multiple budgets per month/year as long as each has a distinct name.
    Uniqueness is enforced by the database constraint on (user_id, name, month, year).

    Args:
        db: Async database session.
        user_id: The owning user's UUID.
        data: Validated budget creation data.

    Returns:
        The newly created MonthlyBudget instance.

    Raises:
        HTTPException: If a budget with this name already exists for the month/year (409).
    """
    budget = MonthlyBudget(
        user_id=user_id,
        name=data.name,
        month=data.month,
        year=data.year,
        total_limit=data.total_limit,
        currency=data.currency,
    )
    db.add(budget)

    try:
        await db.flush()
        await db.refresh(budget)
    except IntegrityError as exc:
        db.rollback()
        month_names = {
            1: "January", 2: "February", 3: "March", 4: "April",
            5: "May", 6: "June", 7: "July", 8: "August",
            9: "September", 10: "October", 11: "November", 12: "December",
        }
        month_label = month_names.get(data.month, str(data.month))
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Budget name '{data.name}' already exists for {month_label} {data.year}",
        ) from exc

    return budget


async def get_user_budgets(
    db: AsyncSession,
    user_id: UUID,
    year: int | None = None,
) -> list[MonthlyBudget]:
    """List all monthly budgets for a user, optionally filtered by year.

    Args:
        db: Async database session.
        user_id: The owning user's UUID.
        year: Optional year filter.

    Returns:
        List of MonthlyBudget instances ordered by year descending, then month descending.
    """
    query = select(MonthlyBudget).where(MonthlyBudget.user_id == user_id)
    if year is not None:
        query = query.where(MonthlyBudget.year == year)
    query = query.order_by(MonthlyBudget.year.desc(), MonthlyBudget.month.desc())

    result = await db.execute(query)
    return list(result.scalars().all())


async def get_current_budget(
    db: AsyncSession,
    user_id: UUID,
) -> list[MonthlyBudget]:
    """Find all budgets for the current month and year, with categories loaded.

    With named budgets, there may be multiple budgets for the same month/year.

    Args:
        db: Async database session.
        user_id: The owning user's UUID.

    Returns:
        List of MonthlyBudget instances for the current month/year with
        daily_categories eagerly loaded. May be empty if no budgets exist.
    """
    today = date.today()
    result = await db.execute(
        select(MonthlyBudget)
        .where(
            MonthlyBudget.user_id == user_id,
            MonthlyBudget.month == today.month,
            MonthlyBudget.year == today.year,
        )
        .options(selectinload(MonthlyBudget.daily_categories)),
    )
    return list(result.scalars().all())


async def get_budget_with_categories(
    db: AsyncSession,
    budget_id: UUID,
    user_id: UUID,
) -> MonthlyBudget:
    """Retrieve a monthly budget with its nested categories.

    Validates ownership: the budget must belong to the requesting user.

    Args:
        db: Async database session.
        budget_id: The budget's UUID.
        user_id: The requesting user's UUID.

    Returns:
        The MonthlyBudget instance with categories eagerly loaded.

    Raises:
        HTTPException: If the budget is not found or does not belong to the user (404).
    """
    result = await db.execute(
        select(MonthlyBudget)
        .where(
            MonthlyBudget.id == budget_id,
            MonthlyBudget.user_id == user_id,
        )
        .options(selectinload(MonthlyBudget.daily_categories)),
    )
    budget = result.scalar_one_or_none()

    if budget is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found",
        )

    return budget


async def update_budget(
    db: AsyncSession,
    budget_id: UUID,
    user_id: UUID,
    data: MonthlyBudgetUpdate,
) -> MonthlyBudget:
    """Partially update an existing monthly budget.

    Validates ownership before applying changes.

    Args:
        db: Async database session.
        budget_id: The budget's UUID.
        user_id: The requesting user's UUID.
        data: Validated update fields (only non-None fields are applied).

    Returns:
        The updated MonthlyBudget instance.

    Raises:
        HTTPException: If the budget is not found (404).
    """
    result = await db.execute(
        select(MonthlyBudget).where(
            MonthlyBudget.id == budget_id,
            MonthlyBudget.user_id == user_id,
        ),
    )
    budget = result.scalar_one_or_none()

    if budget is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found",
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(budget, field, value)

    await db.flush()
    await db.refresh(budget)
    return budget


async def delete_budget(
    db: AsyncSession,
    budget_id: UUID,
    user_id: UUID,
) -> None:
    """Delete a monthly budget and cascade-delete its categories and expenses.

    Cascade deletion is handled by the database-level ON DELETE CASCADE
    constraints defined in the model relationships.

    Args:
        db: Async database session.
        budget_id: The budget's UUID.
        user_id: The requesting user's UUID.

    Raises:
        HTTPException: If the budget is not found (404).
    """
    result = await db.execute(
        select(MonthlyBudget).where(
            MonthlyBudget.id == budget_id,
            MonthlyBudget.user_id == user_id,
        ),
    )
    budget = result.scalar_one_or_none()

    if budget is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found",
        )

    await db.delete(budget)
    await db.flush()
