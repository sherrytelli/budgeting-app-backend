"""Analytics service: monthly budget standing and category-level spending analysis.

This module calculates the user's overall monthly budget standing (under/over budget),
daily spending allowance for the remainder of the month, and per-category analytics
including today's spending and month-to-date totals.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.budget import MonthlyBudget
from app.models.category import DailyCategory
from app.models.expense import Expense

if TYPE_CHECKING:
    from app.schemas.analytics import CategoryAnalytics, MonthlyStanding

__all__ = [
    "get_category_reminders",
    "get_monthly_standing",
]


# --- Analytics Calculations ---


async def get_monthly_standing(
    db: AsyncSession,
    user_id: UUID,
    month: int | None = None,
    year: int | None = None,
) -> MonthlyStanding:
    """Calculate the user's overall monthly budget standing.

    Queries total spending across all categories for the given month,
    computes remaining balance, budget status, and the safe daily allowance
    for the remainder of the month.

    Also calculates per-category analytics: today's spending, month-to-date
    spending, and remaining daily allowance.

    Args:
        db: Async database session.
        user_id: The user's UUID.
        month: Target month (1-12). Defaults to current month.
        year: Target year. Defaults to current year.

    Returns:
        A MonthlyStanding schema with overall and per-category analytics.

    Raises:
        HTTPException: If no budget exists for the given month/year (404).
    """
    today = date.today()
    target_month = month or today.month
    target_year = year or today.year

    # Fetch the budget for the target month/year
    result = await db.execute(
        select(MonthlyBudget)
        .where(
            MonthlyBudget.user_id == user_id,
            MonthlyBudget.month == target_month,
            MonthlyBudget.year == target_year,
        )
        .options(selectinload(MonthlyBudget.daily_categories)),
    )
    budget = result.scalar_one_or_none()

    if budget is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No budget found for {target_month}/{target_year}",
        )

    # Calculate total spent this month across all categories
    # We join expenses through categories to the budget
    total_spent_result = await db.execute(
        select(func.coalesce(func.sum(Expense.amount), Decimal("0")))
        .select_from(MonthlyBudget)
        .join(DailyCategory, MonthlyBudget.id == DailyCategory.monthly_budget_id)
        .join(Expense, DailyCategory.id == Expense.daily_category_id)
        .where(
            MonthlyBudget.id == budget.id,
            func.date_trunc("month", Expense.spent_at)
            == datetime(target_year, target_month, 1, tzinfo=timezone.utc),
        ),
    )
    total_spent: Decimal = total_spent_result.scalar() or Decimal("0")

    remaining_balance: Decimal = budget.total_limit - total_spent

    # Determine status
    status_str: str = (
        "OVER_BUDGET" if remaining_balance < Decimal("0") else "UNDER_BUDGET"
    )

    # Calculate remaining days in the month (including today if in the same month)
    days_in_month = monthrange(target_year, target_month)[1]
    if target_month == today.month and target_year == today.year:
        remaining_days: int = days_in_month - today.day + 1
    else:
        remaining_days = days_in_month

    # Calculate daily allowance for the remainder of the month
    if remaining_days > 0:
        daily_allowance: Decimal = remaining_balance / Decimal(str(remaining_days))
    else:
        daily_allowance = Decimal("0")

    # Build per-category analytics
    categories_analytics: list[CategoryAnalytics] = []
    for category in budget.daily_categories:
        # Today's spending for this category
        today_start = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)
        today_end = today_start.replace(hour=23, minute=59, second=59)

        today_spent_result = await db.execute(
            select(func.coalesce(func.sum(Expense.amount), Decimal("0")))
            .select_from(DailyCategory)
            .join(Expense, DailyCategory.id == Expense.daily_category_id)
            .where(
                DailyCategory.id == category.id,
                Expense.spent_at >= today_start,
                Expense.spent_at <= today_end,
            ),
        )
        today_spent: Decimal = today_spent_result.scalar() or Decimal("0")

        # Month-to-date spending for this category
        month_start = datetime(target_year, target_month, 1, tzinfo=timezone.utc)
        month_end = datetime(
            target_year,
            target_month,
            days_in_month,
            23,
            59,
            59,
            tzinfo=timezone.utc,
        )

        month_spent_result = await db.execute(
            select(func.coalesce(func.sum(Expense.amount), Decimal("0")))
            .select_from(DailyCategory)
            .join(Expense, DailyCategory.id == Expense.daily_category_id)
            .where(
                DailyCategory.id == category.id,
                Expense.spent_at >= month_start,
                Expense.spent_at <= month_end,
            ),
        )
        month_spent: Decimal = month_spent_result.scalar() or Decimal("0")

        today_remaining: Decimal = category.daily_limit - today_spent

        reminder_time_str: str | None = (
            category.reminder_time.strftime("%H:%M:%S")
            if category.reminder_time is not None
            else None
        )

        categories_analytics.append(
            CategoryAnalytics(
                category_id=category.id,
                name=category.name,
                daily_limit=category.daily_limit,
                today_spent=today_spent,
                today_remaining=today_remaining,
                month_spent=month_spent,
                reminder_time=reminder_time_str,
            ),
        )

    return MonthlyStanding(
        total_budget=budget.total_limit,
        total_spent=total_spent,
        remaining_balance=remaining_balance,
        status=status_str,  # type: ignore[call-arg]
        daily_allowance=daily_allowance,
        remaining_days=remaining_days,
        categories=categories_analytics,
    )


async def get_category_reminders(
    db: AsyncSession,
    user_id: UUID,
    month: int | None = None,
    year: int | None = None,
) -> list[DailyCategory]:
    """Retrieve all categories that have reminder times set for the given month.

    This is used by the mobile app to schedule push notifications
    for categories where the user has enabled reminders.

    Args:
        db: Async database session.
        user_id: The user's UUID.
        month: Target month (1-12). Defaults to current month.
        year: Target year. Defaults to current year.

    Returns:
        List of DailyCategory instances with reminder_time set,
        ordered by reminder_time ascending.
    """
    target_month = month or date.today().month
    target_year = year or date.today().year

    result = await db.execute(
        select(DailyCategory)
        .join(MonthlyBudget, DailyCategory.monthly_budget_id == MonthlyBudget.id)
        .where(
            MonthlyBudget.user_id == user_id,
            MonthlyBudget.month == target_month,
            MonthlyBudget.year == target_year,
            DailyCategory.reminder_time.isnot(None),
        )
        .order_by(DailyCategory.reminder_time.asc()),
    )
    return list(result.scalars().all())
