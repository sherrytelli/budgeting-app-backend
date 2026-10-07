"""Daily category endpoints.

Provides CRUD operations for daily spending categories within a
monthly budget, plus a reminders endpoint to retrieve categories
that have notification times configured.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ActiveUserDep, get_db
from app.models.budget import MonthlyBudget
from app.models.category import DailyCategory
from app.schemas.category import (
    DailyCategoryCreate,
    DailyCategoryRead,
    DailyCategoryUpdate,
)
from app.services.analytics_service import get_category_reminders

router = APIRouter(tags=["categories"])


@router.post(
    "/budgets/{budget_id}/categories",
    response_model=DailyCategoryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a category within a budget",
)
async def create_category(
    budget_id: UUID,
    data: DailyCategoryCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: ActiveUserDep,
) -> DailyCategoryRead:
    """Create a new daily spending category within a monthly budget.

    Args:
        budget_id: The parent budget's UUID.
        data: Validated category creation data.
        db: Database session.
        user: The authenticated active user.

    Returns:
        The created DailyCategoryRead schema.

    Raises:
        HTTPException: If the parent budget is not found or doesn't belong to user (404).
    """
    # Verify budget ownership
    budget_result = await db.execute(
        select(MonthlyBudget).where(
            MonthlyBudget.id == budget_id,
            MonthlyBudget.user_id == user.id,
        ),
    )
    budget = budget_result.scalar_one_or_none()
    if budget is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found",
        )

    category = DailyCategory(
        monthly_budget_id=budget_id,
        name=data.name,
        daily_limit=data.daily_limit,
        reminder_time=data.reminder_time,
        icon=data.icon,
    )
    db.add(category)
    await db.flush()
    await db.refresh(category)
    return category


@router.get(
    "/budgets/{budget_id}/categories",
    response_model=list[DailyCategoryRead],
    summary="List categories in a budget",
)
async def list_categories(
    budget_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: ActiveUserDep,
) -> list[DailyCategoryRead]:
    """List all daily categories within a monthly budget.

    Args:
        budget_id: The parent budget's UUID.
        db: Database session.
        user: The authenticated active user.

    Returns:
        List of DailyCategoryRead schemas.

    Raises:
        HTTPException: If the parent budget is not found or doesn't belong to user (404).
    """
    # Verify budget ownership
    budget_result = await db.execute(
        select(MonthlyBudget).where(
            MonthlyBudget.id == budget_id,
            MonthlyBudget.user_id == user.id,
        ),
    )
    budget = budget_result.scalar_one_or_none()
    if budget is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found",
        )

    result = await db.execute(
        select(DailyCategory)
        .where(DailyCategory.monthly_budget_id == budget_id)
        .order_by(DailyCategory.name.asc()),
    )
    return list(result.scalars().all())


@router.put(
    "/categories/{category_id}",
    response_model=DailyCategoryRead,
    summary="Update a daily category",
)
async def update_category(
    category_id: UUID,
    data: DailyCategoryUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: ActiveUserDep,
) -> DailyCategoryRead:
    """Partially update an existing daily category.

    Args:
        category_id: The category's UUID.
        data: Validated update fields.
        db: Database session.
        user: The authenticated active user.

    Returns:
        The updated DailyCategoryRead schema.

    Raises:
        HTTPException: If the category's budget doesn't belong to user (404).
    """
    result = await db.execute(
        select(DailyCategory).join(
            MonthlyBudget,
            DailyCategory.monthly_budget_id == MonthlyBudget.id,
        ).where(
            DailyCategory.id == category_id,
            MonthlyBudget.user_id == user.id,
        ),
    )
    category = result.scalar_one_or_none()
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(category, field, value)

    await db.flush()
    await db.refresh(category)
    return category


@router.delete(
    "/categories/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a daily category",
)
async def delete_category(
    category_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: ActiveUserDep,
) -> None:
    """Delete a daily category and all its expenses.

    Cascade deletion is handled by database-level ON DELETE CASCADE constraints.

    Args:
        category_id: The category's UUID.
        db: Database session.
        user: The authenticated active user.

    Raises:
        HTTPException: If the category's budget doesn't belong to user (404).
    """
    result = await db.execute(
        select(DailyCategory).join(
            MonthlyBudget,
            DailyCategory.monthly_budget_id == MonthlyBudget.id,
        ).where(
            DailyCategory.id == category_id,
            MonthlyBudget.user_id == user.id,
        ),
    )
    category = result.scalar_one_or_none()
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    await db.delete(category)
    await db.flush()


@router.get(
    "/reminders",
    response_model=list[DailyCategoryRead],
    summary="Get categories with reminders",
)
async def get_reminders(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: ActiveUserDep,
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = Query(default=None, ge=2000),
) -> list[DailyCategoryRead]:
    """Retrieve all categories with reminder times set for a given month.

    This endpoint is used by the mobile app to schedule push notifications
    for categories where the user has enabled reminders.

    Args:
        month: Target month (1-12). Defaults to current month.
        year: Target year. Defaults to current year.
        db: Database session.
        user: The authenticated active user.

    Returns:
        List of DailyCategoryRead schemas ordered by reminder_time ascending.
    """
    categories = await get_category_reminders(db, user.id, month=month, year=year)
    return categories
