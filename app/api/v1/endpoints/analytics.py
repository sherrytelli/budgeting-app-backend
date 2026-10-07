"""Analytics endpoints.

Provides budget analytics including the overall monthly standing
(under/over budget status, daily allowance) and per-category
spending breakdowns.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ActiveUserDep, get_db
from app.schemas.analytics import MonthlyStanding
from app.services.analytics_service import get_monthly_standing

router = APIRouter(tags=["analytics"])


@router.get(
    "/monthly-standing",
    response_model=MonthlyStanding,
    summary="Get monthly budget standing",
)
async def monthly_standing(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: ActiveUserDep,
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = Query(default=None, ge=2000),
) -> MonthlyStanding:
    """Calculate the user's overall monthly budget standing.

    Returns the total budget, total spent, remaining balance, budget
    status (UNDER_BUDGET / OVER_BUDGET), safe daily allowance for the
    remainder of the month, and per-category analytics.

    Args:
        month: Target month (1-12). Defaults to current month.
        year: Target year. Defaults to current year.
        db: Database session.
        user: The authenticated active user.

    Returns:
        MonthlyStanding schema with overall and per-category analytics.

    Raises:
        HTTPException: If no budget exists for the given month/year (404).
    """
    standing = await get_monthly_standing(db, user.id, month=month, year=year)
    return standing
