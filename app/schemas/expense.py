"""Expense-related Pydantic schemas.

Defines request/response schemas for creating, reading, updating, and deleting
individual expense records.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationInfo, field_validator

# Upper bound matching the Numeric(12, 2) money column.
MONEY_MAX = Decimal("99999999999.99")

SPENT_AT_DESCRIPTION = (
    "When the expense was incurred. Send the device's wall-clock datetime "
    "including its UTC offset (e.g. 2026-10-12T00:30:00+05:00); naive "
    "timestamps are rejected. The server derives spent_date as its "
    "wall-clock date."
)


class ExpenseBase(BaseModel):
    """Base schema for expense fields."""

    daily_category_id: UUID = Field(description="Parent daily category ID")
    amount: Decimal = Field(
        gt=0,
        le=MONEY_MAX,
        description="Expense amount (must be positive)",
    )
    note: str | None = Field(default=None, max_length=500, description="Optional expense note")
    spent_at: AwareDatetime = Field(description=SPENT_AT_DESCRIPTION)


class ExpenseCreate(ExpenseBase):
    """Schema for creating a new expense."""

    spent_at: AwareDatetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description=SPENT_AT_DESCRIPTION + " Defaults to the server clock (UTC) if omitted.",
    )


class ExpenseUpdate(BaseModel):
    """Schema for updating an existing expense (all fields optional).

    Fields omitted from the payload are left unchanged; explicitly sending
    ``null`` for amount, daily_category_id, or spent_at is rejected with a
    422. Only ``note`` may be cleared with null.
    """

    amount: Decimal | None = Field(default=None, gt=0, le=MONEY_MAX)
    note: str | None = Field(default=None, max_length=500)
    daily_category_id: UUID | None = Field(default=None, description="Reassign the expense to another category")
    spent_at: AwareDatetime | None = Field(default=None, description=SPENT_AT_DESCRIPTION)

    @field_validator("amount", "spent_at", "daily_category_id", mode="before")
    @classmethod
    def reject_nulls(cls, value: Any, info: ValidationInfo) -> Any:
        """Reject explicit JSON nulls so they 422 instead of reaching the ORM."""
        if value is None:
            raise ValueError(f"{info.field_name} must not be null")
        return value


class ExpenseRead(ExpenseBase):
    """Schema for reading expense data."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Expense unique identifier")
    spent_date: date = Field(description="Wall-clock day the expense belongs to (derived from spent_at)")
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
