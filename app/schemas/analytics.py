"""Analytics-related Pydantic schemas.

Defines response schemas for budget analytics, including per-category spending
breakdowns and overall monthly standing calculations.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class CategoryAnalytics(BaseModel):
    """Per-category analytics for the current month."""

    category_id: UUID = Field(description="Category unique identifier")
    name: str = Field(description="Category name")
    daily_limit: Decimal = Field(description="Daily spending limit")
    today_spent: Decimal = Field(description="Total spent today in this category")
    today_remaining: Decimal = Field(description="Remaining daily allowance for today")
    month_spent: Decimal = Field(description="Total spent this month in this category")
    reminder_time: str | None = Field(default=None, description="Reminder time in HH:MM:SS format, if set")


class MonthlyStanding(BaseModel):
    """Overall monthly budget standing with per-category breakdown."""

    total_budget: Decimal = Field(description="Total monthly budget limit")
    total_spent: Decimal = Field(description="Total spent across all categories this month")
    remaining_balance: Decimal = Field(description="Remaining budget for the month")
    status: Literal["UNDER_BUDGET", "OVER_BUDGET"] = Field(
        description="Whether the user is under or over their total monthly budget",
    )
    daily_allowance: Decimal = Field(
        description="Safe daily spending allowance for the remainder of the month",
    )
    remaining_days: int = Field(
        description="Number of remaining days in the current month (including today)",
    )
    categories: list[CategoryAnalytics] = Field(
        default_factory=list,
        description="Per-category analytics breakdown",
    )
