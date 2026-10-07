"""Expense-related Pydantic schemas.

Defines request/response schemas for creating, reading, updating, and deleting
individual expense records.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ExpenseBase(BaseModel):
    """Base schema for expense fields."""

    daily_category_id: UUID = Field(description="Parent daily category ID")
    amount: Decimal = Field(gt=0, description="Expense amount (must be positive)")
    note: str | None = Field(default=None, max_length=500, description="Optional expense note")
    spent_at: datetime = Field(description="When the expense was incurred (UTC)")


class ExpenseCreate(ExpenseBase):
    """Schema for creating a new expense."""

    pass


class ExpenseUpdate(BaseModel):
    """Schema for updating an existing expense (all fields optional)."""

    amount: Decimal | None = Field(default=None, gt=0)
    note: str | None = Field(default=None, max_length=500)
    spent_at: datetime | None = Field(default=None)


class ExpenseRead(ExpenseBase):
    """Schema for reading expense data."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Expense unique identifier")
    created_at: datetime = Field(description="Creation timestamp (UTC)")
    updated_at: datetime = Field(description="Last update timestamp (UTC)")


class ExpenseFilter(BaseModel):
    """Schema for filtering expense list queries."""

    category_id: UUID | None = Field(default=None, description="Filter by category ID")
    start_date: datetime | None = Field(default=None, description="Filter expenses on or after this date")
    end_date: datetime | None = Field(default=None, description="Filter expenses on or before this date")
    month: int | None = Field(default=None, ge=1, le=12, description="Filter by month (1-12)")
    year: int | None = Field(default=None, ge=2000, description="Filter by year")
    limit: int = Field(default=100, ge=1, le=1000, description="Max results to return")
    offset: int = Field(default=0, ge=0, description="Pagination offset")
