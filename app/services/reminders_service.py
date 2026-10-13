"""Reminders service: category reminder lookups for push notifications.

Provides the query used by the mobile app to schedule daily reminders for
categories that have a reminder time set.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.budget import MonthlyBudget
from app.models.category import DailyCategory

__all__ = [
    "get_category_reminders",
]


async def get_category_reminders(
    db: AsyncSession,
    user_id: UUID,
    month: int | None = None,
    year: int | None = None,
    budget_name: str | None = None,
) -> list[DailyCategory]:
    """Retrieve all categories that have reminder times set for the given named budget.

    This is used by the mobile app to schedule push notifications
    for categories where the user has enabled reminders.

    Args:
        db: Async database session.
        user_id: The user's UUID.
        month: Target month (1-12). Defaults to current month.
        year: Target year. Defaults to current year.
        budget_name: Optional name of the specific budget to query.

    Returns:
        List of DailyCategory instances with reminder_time set,
        ordered by reminder_time ascending.
    """
    target_month = month or date.today().month
    target_year = year or date.today().year

    query = (
        select(DailyCategory)
        .join(MonthlyBudget, DailyCategory.monthly_budget_id == MonthlyBudget.id)
        .where(
            MonthlyBudget.user_id == user_id,
            MonthlyBudget.month == target_month,
            MonthlyBudget.year == target_year,
            DailyCategory.reminder_time.isnot(None),
        )
        .order_by(DailyCategory.reminder_time.asc())
    )

    if budget_name is not None:
        query = query.where(MonthlyBudget.name == budget_name)

    result = await db.execute(query)
    return list(result.scalars().all())
