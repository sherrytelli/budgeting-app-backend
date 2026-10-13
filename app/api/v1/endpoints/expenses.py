"""Expense endpoints.

Provides CRUD operations for individual expense records, including
filtering by category, budget, date range, month, and year.

Expenses carry both ``spent_at`` (an aware timestamp) and the derived
wall-clock day ``spent_date``. All list filters and the day-panel logic
operate on ``spent_date`` so results are timezone-independent.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
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

# Tolerance for the day-level future rule: a device at UTC+14 sending
# "today 23:59 local" is still tomorrow relative to the UTC clock, and
# every real UTC offset is covered within 14 hours.
FUTURE_DATE_TOLERANCE = timedelta(hours=14)


def _resolve_spent_date(spent_at: datetime, budget: MonthlyBudget) -> date:
    """Derive ``spent_date`` and enforce the month and future-date rules.

    Args:
        spent_at: The aware datetime sent by the client.
        budget: The budget the expense belongs to.

    Returns:
        The wall-clock date derived from ``spent_at``.

    Raises:
        HTTPException: If the date is outside the budget's month (422).
        HTTPException: If the date is beyond tomorrow in any UTC offset (422).
    """
    spent_date = spent_at.date()

    if (spent_date.year, spent_date.month) != (budget.year, budget.month):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"spent_at date {spent_date.isoformat()} is outside budget month "
                f"{budget.year}-{budget.month:02d}"
            ),
        )

    latest_allowed = (datetime.now(UTC) + FUTURE_DATE_TOLERANCE).date()
    if spent_date > latest_allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"spent_at date {spent_date.isoformat()} is in the future",
        )

    return spent_date


def _next_month_start(year: int, month: int) -> date:
    """Return the first day of the month after the given (year, month)."""
    if month == 12:
        return date(year + 1, 1, 1)
    return date(year, month + 1, 1)


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
    the requesting user, derives ``spent_date`` from ``spent_at``, and
    enforces that it falls inside the budget's month and is not in the
    future.

    Args:
        data: Validated expense creation data.
        db: Database session.
        user: The authenticated active user.

    Returns:
        The created ExpenseRead schema.

    Raises:
        HTTPException: If the category is not found or doesn't belong to user (404).
        HTTPException: If spent_at is outside the budget's month or in the future (422).
    """
    # Verify category ownership and load its budget for the date rules
    category_result = await db.execute(
        select(DailyCategory, MonthlyBudget)
        .join(
            MonthlyBudget,
            DailyCategory.monthly_budget_id == MonthlyBudget.id,
        ).where(
            DailyCategory.id == data.daily_category_id,
            MonthlyBudget.user_id == user.id,
        ),
    )
    row = category_result.one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )
    budget = row[1]

    spent_date = _resolve_spent_date(data.spent_at, budget)

    expense = Expense(
        daily_category_id=data.daily_category_id,
        amount=data.amount,
        note=data.note,
        spent_at=data.spent_at,
        spent_date=spent_date,
    )
    db.add(expense)
    await db.flush()
    await db.refresh(expense)
    await db.commit()
    return ExpenseRead.model_validate(expense)


@router.get(
    "",
    response_model=list[ExpenseRead],
    summary="List expenses with filters",
)
async def list_expenses(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: ActiveUserDep,
    category_id: UUID | None = None,
    budget_id: UUID | None = None,
    start_date: Annotated[
        date | None,
        Query(description="Include expenses whose spent_date is on or after this day"),
    ] = None,
    end_date: Annotated[
        date | None,
        Query(description="Include expenses whose spent_date is on or before this day"),
    ] = None,
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = Query(default=None, ge=2000),
    budget_name: str | None = Query(
        default=None,
        description="Deprecated: filter by budget name (prefer budget_id)",
        deprecated=True,
    ),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[ExpenseRead]:
    """List expenses with optional filtering.

    All filters are optional. Date filters (start_date, end_date, month,
    year) operate on the timezone-independent ``spent_date`` column. When
    category_id or budget_id is provided, ownership is enforced through
    the budget join.

    Args:
        category_id: Filter by category UUID.
        budget_id: Filter by budget UUID.
        start_date: Include expenses on or after this wall-clock day.
        end_date: Include expenses on or before this wall-clock day.
        month: Filter by month (1-12).
        year: Filter by year.
        budget_name: Deprecated filter by budget name; prefer budget_id.
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

    if budget_id is not None:
        query = query.where(MonthlyBudget.id == budget_id)

    if budget_name is not None:
        query = query.where(MonthlyBudget.name == budget_name)

    if category_id is not None:
        query = query.where(Expense.daily_category_id == category_id)

    if start_date is not None:
        query = query.where(Expense.spent_date >= start_date)

    if end_date is not None:
        query = query.where(Expense.spent_date <= end_date)

    if month is not None and year is not None:
        query = query.where(
            Expense.spent_date >= date(year, month, 1),
            Expense.spent_date < _next_month_start(year, month),
        )
    elif month is not None:
        query = query.where(func.extract("month", Expense.spent_date) == month)
    elif year is not None:
        query = query.where(
            Expense.spent_date >= date(year, 1, 1),
            Expense.spent_date < date(year + 1, 1, 1),
        )

    query = query.order_by(Expense.spent_at.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    return [ExpenseRead.model_validate(e) for e in result.scalars().all()]


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
    return ExpenseRead.model_validate(expense)


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

    If the expense is reassigned to another category, ownership of the
    target category is re-verified and both date rules are re-run against
    the target's budget.

    Args:
        expense_id: The expense's UUID.
        data: Validated update fields.
        db: Database session.
        user: The authenticated active user.

    Returns:
        The updated ExpenseRead schema.

    Raises:
        HTTPException: If the expense is not found (404).
        HTTPException: If the target category isn't owned by the user (404).
        HTTPException: If the final spent_at breaks the month/future rules (422).
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

    # Re-resolve the final category (it may have just been reassigned) to
    # re-verify ownership and to validate the dates against its budget.
    final_category_id = expense.daily_category_id
    final_result = await db.execute(
        select(DailyCategory, MonthlyBudget)
        .join(
            MonthlyBudget,
            DailyCategory.monthly_budget_id == MonthlyBudget.id,
        ).where(
            DailyCategory.id == final_category_id,
            MonthlyBudget.user_id == user.id,
        ),
    )
    final_row = final_result.one_or_none()
    if final_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )
    final_budget = final_row[1]

    expense.spent_date = _resolve_spent_date(expense.spent_at, final_budget)

    await db.flush()
    await db.refresh(expense)
    await db.commit()
    return ExpenseRead.model_validate(expense)


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
    await db.commit()
