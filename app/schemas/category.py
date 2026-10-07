"""Daily category-related Pydantic schemas.

Defines request/response schemas for creating, reading, updating, and deleting
daily spending categories within a monthly budget.
"""

from datetime import datetime, time
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DailyCategoryBase(BaseModel):
    """Base schema for daily category fields."""

    name: str = Field(min_length=1, max_length=50, description="Category name (e.g. Food, Transport)")
    daily_limit: Decimal = Field(gt=0, description="Daily spending limit for this category")
    reminder_time: time | None = Field(default=None, description="Daily reminder time (local, no timezone)")
    icon: str | None = Field(default=None, max_length=20, description="Category icon identifier")


class DailyCategoryCreate(DailyCategoryBase):
    """Schema for creating a new daily category."""

    pass


class DailyCategoryUpdate(BaseModel):
    """Schema for updating an existing daily category (all fields optional)."""

    name: str | None = Field(default=None, min_length=1, max_length=50)
    daily_limit: Decimal | None = Field(default=None, gt=0)
    reminder_time: time | None = Field(default=None)
    icon: str | None = Field(default=None, max_length=20)


class DailyCategoryRead(DailyCategoryBase):
    """Schema for reading daily category data."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Category unique identifier")
    monthly_budget_id: UUID = Field(description="Parent monthly budget ID")
    created_at: datetime = Field(description="Creation timestamp (UTC)")
    updated_at: datetime = Field(description="Last update timestamp (UTC)")


class ExpenseRead(BaseModel):
    """Schema for an expense nested inside a category read."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Expense unique identifier")
    amount: Decimal = Field(description="Expense amount")
    note: str | None = Field(default=None, description="Optional expense note")
    spent_at: datetime = Field(description="When the expense was incurred (UTC)")
    created_at: datetime = Field(description="Creation timestamp (UTC)")
    updated_at: datetime = Field(description="Last update timestamp (UTC)")


class CategoryWithExpenses(DailyCategoryRead):
    """Daily category read schema with nested expense list."""

    expenses: list[ExpenseRead] = Field(
        default_factory=list,
        description="List of expenses within this category",
    )
