"""Expense endpoints.

Provides CRUD operations for individual expense records, including
filtering by category, date range, month, and year.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ActiveUserDep, get_db
from app.models.budget import MonthlyBudget
from app.models.category import DailyCategory
from app.models.expense import Expense
from app.schemas.expense import ExpenseCreate, ExpenseRead, ExpenseUpdate

router = APIRouter(prefix="/expenses", tags=["expenses"])


@router.post(
    "",
    response_model=ExpenseRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an expense",
)
async def create_expense(
    data: ExpenseCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: ActiveUserDep,
) -> ExpenseRead:
    """Create a new expense record within a category.

    Validates that the parent category belongs to a budget owned by
    the requesting user.

    Args:
        data: Validated expense creation data.
        db: Database session.
        user: The authenticated active user.

    Returns:
        The created ExpenseRead schema.

    Raises:
        HTTPException: If the category is not found or doesn't belong to user (404).
    """
    # Verify category ownership
    category_result = await db.execute(
        select(DailyCategory).join(
            MonthlyBudget,
            DailyCategory.monthly_budget_id == MonthlyBudget.id,
        ).where(
            DailyCategory.id == data.daily_category_id,
            MonthlyBudget.user_id == user.id,
        ),
    )
    category = category_result.scalar_one_or_none()
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    expense = Expense(
        daily_category_id=data.daily_category_id,
        amount=data.amount,
        note=data.note,
        spent_at=data.spent_at,
    )
    db.add(expense)
    await db.flush()
    await db.refresh(expense)
    return expense


@router.get(
    "",
    response_model=list[ExpenseRead],
    summary="List expenses with filters",
)
async def list_expenses(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: ActiveUserDep,
    category_id: UUID | None = Query(default=None),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = Query(default=None, ge=2000),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[ExpenseRead]:
    """List expenses with optional filtering.

    All filters are optional. When month/year are provided, expenses
    are filtered by the month portion of their ``spent_at`` timestamp.
    When category_id is provided, the category must belong to the user.

    Args:
        category_id: Filter by category UUID.
        start_date: Filter expenses on or after this date.
        end_date: Filter expenses on or before this date.
        month: Filter by month (1-12).
        year: Filter by year.
        limit: Max results to return (1-1000).
        offset: Pagination offset.
        db: Database session.
        user: The authenticated active user.

    Returns:
        List of ExpenseRead schemas ordered by spent_at descending.
    """
    query = (
        select(Expense)
        .join(DailyCategory, Expense.daily_category_id == DailyCategory.id)
        .join(MonthlyBudget, DailyCategory.monthly_budget_id == MonthlyBudget.id)
        .where(MonthlyBudget.user_id == user.id)
    )

    if category_id is not None:
        query = query.where(Expense.daily_category_id == category_id)

    if start_date is not None:
        query = query.where(Expense.spent_at >= start_date)

    if end_date is not None:
        query = query.where(Expense.spent_at <= end_date)

    if month is not None and year is not None:
        query = query.where(
            func.extract("year", Expense.spent_at) == year,
            func.extract("month", Expense.spent_at) == month,
        )
    elif month is not None:
        query = query.where(func.extract("month", Expense.spent_at) == month)
    elif year is not None:
        query = query.where(func.extract("year", Expense.spent_at) == year)

    query = query.order_by(Expense.spent_at.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    return list(result.scalars().all())


@router.get(
    "/{expense_id}",
    response_model=ExpenseRead,
    summary="Get an expense",
)
async def get_expense(
    expense_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: ActiveUserDep,
) -> ExpenseRead:
    """Retrieve a specific expense record.

    Validates that the expense's category belongs to a budget owned
    by the requesting user.

    Args:
        expense_id: The expense's UUID.
        db: Database session.
        user: The authenticated active user.

    Returns:
        The ExpenseRead schema.

    Raises:
        HTTPException: If the expense is not found (404).
    """
    result = await db.execute(
        select(Expense).join(
            DailyCategory, Expense.daily_category_id == DailyCategory.id,
        ).join(
            MonthlyBudget, DailyCategory.monthly_budget_id == MonthlyBudget.id,
        ).where(
            Expense.id == expense_id,
            MonthlyBudget.user_id == user.id,
        ),
    )
    expense = result.scalar_one_or_none()
    if expense is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found",
        )
    return expense


@router.put(
    "/{expense_id}",
    response_model=ExpenseRead,
    summary="Update an expense",
)
async def update_expense(
    expense_id: UUID,
    data: ExpenseUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: ActiveUserDep,
) -> ExpenseRead:
    """Partially update an existing expense record.

    Args:
        expense_id: The expense's UUID.
        data: Validated update fields.
        db: Database session.
        user: The authenticated active user.

    Returns:
        The updated ExpenseRead schema.

    Raises:
        HTTPException: If the expense is not found (404).
    """
    result = await db.execute(
        select(Expense).join(
            DailyCategory, Expense.daily_category_id == DailyCategory.id,
        ).join(
            MonthlyBudget, DailyCategory.monthly_budget_id == MonthlyBudget.id,
        ).where(
            Expense.id == expense_id,
            MonthlyBudget.user_id == user.id,
        ),
    )
    expense = result.scalar_one_or_none()
    if expense is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found",
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(expense, field, value)

    await db.flush()
    await db.refresh(expense)
    return expense


@router.delete(
    "/{expense_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an expense",
)
async def delete_expense(
    expense_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: ActiveUserDep,
) -> None:
    """Delete an expense record.

    Args:
        expense_id: The expense's UUID.
        db: Database session.
        user: The authenticated active user.

    Raises:
        HTTPException: If the expense is not found (404).
    """
    result = await db.execute(
        select(Expense).join(
            DailyCategory, Expense.daily_category_id == DailyCategory.id,
        ).join(
            MonthlyBudget, DailyCategory.monthly_budget_id == MonthlyBudget.id,
        ).where(
            Expense.id == expense_id,
            MonthlyBudget.user_id == user.id,
        ),
    )
    expense = result.scalar_one_or_none()
    if expense is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found",
        )

    await db.delete(expense)
    await db.flush()
