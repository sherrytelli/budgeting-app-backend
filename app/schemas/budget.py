"""Monthly budget-related Pydantic schemas.

Defines request/response schemas for creating, reading, updating, and deleting
monthly budgets along with their nested category breakdowns.
"""

from datetime import datetime, time
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MonthlyBudgetBase(BaseModel):
    """Base schema for monthly budget fields."""

    month: int = Field(ge=1, le=12, description="Month (1-12)")
    year: int = Field(ge=2000, description="Year (e.g. 2026)")
    total_limit: Decimal = Field(gt=0, description="Total monthly spending limit")
    currency: str = Field(default="PKR", max_length=3, description="Currency code (default: PKR)")


class MonthlyBudgetCreate(MonthlyBudgetBase):
    """Schema for creating a new monthly budget."""

    pass


class MonthlyBudgetUpdate(BaseModel):
    """Schema for updating an existing monthly budget (all fields optional)."""

    month: int | None = Field(default=None, ge=1, le=12)
    year: int | None = Field(default=None, ge=2000)
    total_limit: Decimal | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, max_length=3)


class MonthlyBudgetRead(MonthlyBudgetBase):
    """Schema for reading monthly budget data."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Budget unique identifier")
    user_id: UUID = Field(description="Owner user ID")
    created_at: datetime = Field(description="Creation timestamp (UTC)")
    updated_at: datetime = Field(description="Last update timestamp (UTC)")


class CategoryRead(BaseModel):
    """Schema for a daily category nested inside a budget read."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Category unique identifier")
    name: str = Field(description="Category name (e.g. Food, Transport)")
    daily_limit: Decimal = Field(description="Daily spending limit for this category")
    reminder_time: str | None = Field(default=None, description="Reminder time in HH:MM:SS format")
    icon: str | None = Field(default=None, max_length=20, description="Category icon identifier")
    created_at: datetime = Field(description="Creation timestamp (UTC)")
    updated_at: datetime = Field(description="Last update timestamp (UTC)")

    @field_validator("reminder_time", mode="before")
    @classmethod
    def convert_reminder_time(cls, v):
        """Convert datetime.time objects to HH:MM:SS strings."""
        if isinstance(v, time):
            return v.strftime("%H:%M:%S")
        return v


class MonthlyBudgetWithCategories(MonthlyBudgetRead):
    """Monthly budget read schema with nested category breakdowns."""

    model_config = ConfigDict(populate_by_name=True)

    categories: list[CategoryRead] = Field(
        default_factory=list,
        description="List of daily categories within this budget",
        alias="daily_categories",
    )
