"""Monthly budget endpoints.

Provides CRUD operations for monthly budgets, including listing
all budgets for a user, retrieving the current month's budget,
and getting a budget with its nested categories.
"""

from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ActiveUserDep, get_db
from app.schemas.budget import (
    MonthlyBudgetCreate,
    MonthlyBudgetRead,
    MonthlyBudgetUpdate,
    MonthlyBudgetWithCategories,
)
from app.services.budget_service import (
    create_monthly_budget,
    delete_budget,
    get_budget_with_categories,
    get_current_budget,
    get_user_budgets,
    update_budget,
)

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.post(
    "",
    response_model=MonthlyBudgetRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a monthly budget",
)
async def create_budget(
    data: MonthlyBudgetCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: ActiveUserDep,
) -> MonthlyBudgetRead:
    """Create a new monthly budget for the authenticated user.

    Args:
        data: Validated budget creation data.
        db: Database session.
        user: The authenticated active user.

    Returns:
        The created MonthlyBudgetRead schema.

    Raises:
        HTTPException: If a budget for this month/year already exists (409).
    """
    budget = await create_monthly_budget(db, user.id, data)
    return budget


@router.get(
    "",
    response_model=list[MonthlyBudgetRead],
    summary="List user's budgets",
)
async def list_budgets(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: ActiveUserDep,
    year: int | None = Query(default=None, ge=2000),
) -> list[MonthlyBudgetRead]:
    """List all monthly budgets for the authenticated user.

    Args:
        year: Optional year filter.
        db: Database session.
        user: The authenticated active user.

    Returns:
        List of MonthlyBudgetRead schemas ordered by year desc, month desc.
    """
    budgets = await get_user_budgets(db, user.id, year=year)
    return budgets


@router.get(
    "/current",
    response_model=Optional[MonthlyBudgetWithCategories],
    summary="Get current month's budget with categories",
)
async def get_current(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: ActiveUserDep,
) -> Optional[MonthlyBudgetWithCategories]:
    """Retrieve the budget for the current month, with its categories.

    Args:
        db: Database session.
        user: The authenticated active user.

    Returns:
        MonthlyBudgetWithCategories if one exists, or None.
    """
    budget = await get_current_budget(db, user.id)
    if budget is None:
        return None
    return budget


@router.get(
    "/{budget_id}",
    response_model=MonthlyBudgetWithCategories,
    summary="Get budget with categories",
)
async def get_budget(
    budget_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: ActiveUserDep,
) -> MonthlyBudgetWithCategories:
    """Retrieve a specific monthly budget with its nested categories.

    Validates that the budget belongs to the requesting user.

    Args:
        budget_id: The budget's UUID.
        db: Database session.
        user: The authenticated active user.

    Returns:
        MonthlyBudgetWithCategories schema.

    Raises:
        HTTPException: If the budget is not found (404).
    """
    budget = await get_budget_with_categories(db, budget_id, user.id)
    return budget


@router.put(
    "/{budget_id}",
    response_model=MonthlyBudgetRead,
    summary="Update a monthly budget",
)
async def update(
    budget_id: UUID,
    data: MonthlyBudgetUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: ActiveUserDep,
) -> MonthlyBudgetRead:
    """Partially update an existing monthly budget.

    Args:
        budget_id: The budget's UUID.
        data: Validated update fields.
        db: Database session.
        user: The authenticated active user.

    Returns:
        The updated MonthlyBudgetRead schema.

    Raises:
        HTTPException: If the budget is not found (404).
    """
    budget = await update_budget(db, budget_id, user.id, data)
    return budget


@router.delete(
    "/{budget_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a monthly budget",
)
async def remove(
    budget_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: ActiveUserDep,
) -> None:
    """Delete a monthly budget and all its categories and expenses.

    Cascade deletion is handled by database-level ON DELETE CASCADE constraints.

    Args:
        budget_id: The budget's UUID.
        db: Database session.
        user: The authenticated active user.

    Raises:
        HTTPException: If the budget is not found (404).
    """
    await delete_budget(db, budget_id, user.id)
