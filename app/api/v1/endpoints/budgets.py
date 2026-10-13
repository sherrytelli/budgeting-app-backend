"""Monthly budget endpoints.

Provides CRUD operations for monthly budgets, including listing
all budgets for a user, retrieving the current month's budget,
and getting a budget with its nested categories.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ActiveUserDep, get_db
from app.schemas.budget import (
    MonthlyBudgetCreate,
    MonthlyBudgetRead,
    MonthlyBudgetUpdate,
    MonthlyBudgetWithCategories,
)
from app.schemas.category import CategoryWithExpenses
from app.services.budget_service import (
    create_monthly_budget,
    delete_budget,
    get_budget_daily_view,
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
    return MonthlyBudgetRead.model_validate(budget)


@router.get(
    "",
    response_model=list[MonthlyBudgetRead],
    summary="List user's budgets",
)
async def list_budgets(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: ActiveUserDep,
    year: int | None = Query(default=None, ge=2000),
    month: int | None = Query(default=None, ge=1, le=12),
) -> list[MonthlyBudgetRead]:
    """List all monthly budgets for the authenticated user.

    Args:
        year: Optional year filter.
        month: Optional month filter (1-12).
        db: Database session.
        user: The authenticated active user.

    Returns:
        List of MonthlyBudgetRead schemas ordered by year desc, month desc,
        each carrying its total_spent.
    """
    rows = await get_user_budgets(db, user.id, year=year, month=month)
    reads: list[MonthlyBudgetRead] = []
    for budget, total_spent in rows:
        read = MonthlyBudgetRead.model_validate(budget)
        read.total_spent = total_spent
        reads.append(read)
    return reads


@router.get(
    "/current",
    response_model=list[MonthlyBudgetWithCategories],
    summary="Get current month's budgets with categories",
)
async def get_current(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: ActiveUserDep,
) -> list[MonthlyBudgetWithCategories]:
    """Retrieve all budgets for the current month, with their categories.

    Returns every named budget that exists for the current month/year.
    An empty list is returned if no budgets exist yet.

    Args:
        db: Database session.
        user: The authenticated active user.

    Returns:
        List of MonthlyBudgetWithCategories schemas for the current month.
    """
    budgets = await get_current_budget(db, user.id)
    return [MonthlyBudgetWithCategories.model_validate(b) for b in budgets]


@router.get(
    "/{budget_id}/daily",
    response_model=list[CategoryWithExpenses],
    summary="Get a budget's daily category panel",
)
async def get_budget_daily(
    budget_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: ActiveUserDep,
    date: Annotated[date, Query(description="Wall-clock day (YYYY-MM-DD) to build the panel for")],
) -> list[CategoryWithExpenses]:
    """Build the per-category panel for one day of a budget.

    Returns every category of the budget with its row total and the day's
    expenses (ordered by spent_at ascending). Categories with no spending
    that day are included with spent=0 and an empty expense list.

    Args:
        budget_id: The budget's UUID.
        date: The wall-clock day (spent_date) to build the panel for.
        db: Database session.
        user: The authenticated active user.

    Returns:
        List of CategoryWithExpenses rows ordered by category name ASC.

    Raises:
        HTTPException: If the budget is not found or doesn't belong to user (404).
    """
    return await get_budget_daily_view(db, budget_id, user.id, date)


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
    budget, total_spent = await get_budget_with_categories(db, budget_id, user.id)
    read = MonthlyBudgetWithCategories.model_validate(budget)
    read.total_spent = total_spent
    return read


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
    return MonthlyBudgetRead.model_validate(budget)


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
