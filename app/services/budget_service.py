"""Budget service: CRUD operations for monthly budgets and categories.

This module handles all business logic related to monthly budgets,
including creation, retrieval, updates, and deletion. Named budgets
allow multiple budgets per month/year, with unique constraint enforcement
on (user_id, name, month, year).

All write operations commit explicitly so that a write-then-immediate-read
in a separate request always observes the committed data. ``get_db``'s
trailing commit remains as a no-op safety net.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.budget import MonthlyBudget
from app.models.category import DailyCategory
from app.models.expense import Expense

if TYPE_CHECKING:
    from app.schemas.budget import MonthlyBudgetCreate, MonthlyBudgetUpdate

__all__ = [
    "create_monthly_budget",
    "delete_budget",
    "get_budget_with_categories",
    "get_user_budgets",
    "update_budget",
]

_MONTH_NAMES: dict[int, str] = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
}

_DUPLICATE_BUDGET_CONSTRAINT_FRAGMENT = "user_name_month_year"


# --- IntegrityError Helpers ---


def _constraint_name(exc: IntegrityError) -> str | None:
    """Extract the violated DB constraint name from an IntegrityError.

    The layer the constraint name lives at depends on the driver/asyncpg
    wrapping: it may sit directly on ``exc.orig`` or one level deeper on
    ``exc.orig.orig`` (live-confirmed for this stack). As a last resort,
    parse it out of the error message text.

    Args:
        exc: The caught IntegrityError.

    Returns:
        The constraint name, or None if it could not be determined.
    """
    orig = getattr(exc, "orig", None)
    if orig is None:
        return None

    direct = getattr(orig, "constraint_name", None)
    if isinstance(direct, str) and direct:
        return direct

    nested = getattr(orig, "orig", None)
    if nested is not None:
        nested_name = getattr(nested, "constraint_name", None)
        if isinstance(nested_name, str) and nested_name:
            return nested_name

    match = re.search(r'constraint\s+"([^"]+)"', str(orig))
    return match.group(1) if match else None


def _is_duplicate_budget_conflict(exc: IntegrityError) -> bool:
    """Return True if the IntegrityError is the named-budget unique constraint."""
    constraint_name = _constraint_name(exc)
    return constraint_name is not None and _DUPLICATE_BUDGET_CONSTRAINT_FRAGMENT in constraint_name


def _duplicate_budget_detail(name: str, month: int, year: int) -> str:
    """Build the 409 detail message for a duplicate named budget.

    The mobile app renders its own text on 409 responses, but the message
    stays descriptive for direct API consumers and logs.
    """
    month_label = _MONTH_NAMES.get(month, str(month))
    return f"Budget name '{name}' already exists for {month_label} {year}"


def _budget_conflict_exception(name: str, month: int, year: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=_duplicate_budget_detail(name, month, year),
    )


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
        The newly created and committed MonthlyBudget instance.

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
        await db.rollback()
        if _is_duplicate_budget_conflict(exc):
            raise _budget_conflict_exception(data.name, data.month, data.year) from exc

        # Re-raise other integrity errors as 500
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database conflict occurred while creating the budget. Please try again.",
        ) from exc

    await db.commit()
    return budget


async def get_user_budgets(
    db: AsyncSession,
    user_id: UUID,
    year: int | None = None,
    month: int | None = None,
) -> list[tuple[MonthlyBudget, Decimal]]:
    """List all monthly budgets for a user with their total spending.

    Args:
        db: Async database session.
        user_id: The owning user's UUID.
        year: Optional year filter.
        month: Optional month filter (1-12).

    Returns:
        List of (budget, total_spent) pairs ordered by year desc, then month
        desc, then created_at asc — a stable carousel ordering. total_spent
        sums every expense attached to the budget's categories; the write-time
        rule that expenses must fall inside the budget's month makes
        per-month filtering of the sum unnecessary.
    """
    query = (
        select(
            MonthlyBudget,
            func.coalesce(func.sum(Expense.amount), Decimal("0")).label("total_spent"),
        )
        .outerjoin(DailyCategory, DailyCategory.monthly_budget_id == MonthlyBudget.id)
        .outerjoin(Expense, Expense.daily_category_id == DailyCategory.id)
        .where(MonthlyBudget.user_id == user_id)
        .group_by(MonthlyBudget.id)
        .order_by(
            MonthlyBudget.year.desc(),
            MonthlyBudget.month.desc(),
            MonthlyBudget.created_at.asc(),
        )
    )
    if year is not None:
        query = query.where(MonthlyBudget.year == year)
    if month is not None:
        query = query.where(MonthlyBudget.month == month)

    result = await db.execute(query)
    return [(row[0], row[1]) for row in result.all()]


async def get_budget_with_categories(
    db: AsyncSession,
    budget_id: UUID,
    user_id: UUID,
) -> tuple[MonthlyBudget, Decimal]:
    """Retrieve a monthly budget with its nested categories and total spending.

    Validates ownership: the budget must belong to the requesting user.

    Args:
        db: Async database session.
        budget_id: The budget's UUID.
        user_id: The requesting user's UUID.

    Returns:
        A (budget, total_spent) pair. The budget's daily_categories are
        eagerly loaded and ordered by name ASC; total_spent sums every
        expense attached to the budget's categories.

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

    total_spent_result = await db.execute(
        select(func.coalesce(func.sum(Expense.amount), Decimal("0")))
        .select_from(DailyCategory)
        .join(Expense, Expense.daily_category_id == DailyCategory.id)
        .where(DailyCategory.monthly_budget_id == budget.id),
    )
    total_spent: Decimal = total_spent_result.scalar_one()

    return budget, total_spent


async def update_budget(
    db: AsyncSession,
    budget_id: UUID,
    user_id: UUID,
    data: MonthlyBudgetUpdate,
) -> MonthlyBudget:
    """Partially update an existing monthly budget.

    Validates ownership before applying changes. Renaming a budget (or
    changing month/year) onto an existing duplicate raises 409 instead of
    surfacing as an unhandled database error.

    Args:
        db: Async database session.
        budget_id: The budget's UUID.
        user_id: The requesting user's UUID.
        data: Validated update fields (only non-None fields are applied).

    Returns:
        The updated and committed MonthlyBudget instance.

    Raises:
        HTTPException: If the budget is not found (404).
        HTTPException: If the change collides with another named budget (409).
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

    # Capture the post-update identity before flush(): a rollback below
    # expires the instance, so its attributes can't be read afterwards.
    final_name, final_month, final_year = budget.name, budget.month, budget.year

    try:
        await db.flush()
        await db.refresh(budget)
    except IntegrityError as exc:
        await db.rollback()
        if _is_duplicate_budget_conflict(exc):
            raise _budget_conflict_exception(final_name, final_month, final_year) from exc

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database conflict occurred while updating the budget. Please try again.",
        ) from exc

    await db.commit()
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
    await db.commit()
