"""Monthly budget-related Pydantic schemas.

Defines request/response schemas for creating, reading, updating, and deleting
monthly budgets along with their nested category breakdowns.
"""

from datetime import datetime, time
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

# Upper bound matching the Numeric(12, 2) money columns.
MONEY_MAX = Decimal("99999999999.99")

BUDGET_FIELDS: tuple[str, ...] = ("name", "month", "year", "total_limit", "currency")


def reject_null_budget_field(value: Any, info: ValidationInfo) -> Any:
    """Reject explicit JSON nulls on budget fields.

    Without this, ``null`` passes through ``mode="before"`` hooks and reaches
    the ORM as None, surfacing as a 500 instead of a field-level 422.
    """
    if value is None:
        raise ValueError(f"{info.field_name} must not be null")
    return value


class MonthlyBudgetBase(BaseModel):
    """Base schema for monthly budget fields."""

    name: str = Field(min_length=1, max_length=100, description="Budget label (e.g. Regular, Vacation)")
    month: int = Field(ge=1, le=12, description="Month (1-12)")
    year: int = Field(ge=2000, description="Year (e.g. 2026)")
    total_limit: Decimal = Field(gt=0, le=MONEY_MAX, description="Total monthly spending limit")
    currency: Literal["PKR", "USD"] = Field(default="PKR", description="Currency code (PKR or USD, default: PKR)")

    _reject_nulls = field_validator(*BUDGET_FIELDS, mode="before")(reject_null_budget_field)


class MonthlyBudgetCreate(MonthlyBudgetBase):
    """Schema for creating a new monthly budget."""


class MonthlyBudgetUpdate(BaseModel):
    """Schema for updating an existing monthly budget (all fields optional).

    Fields omitted from the payload are left unchanged; explicitly sending
    ``null`` is rejected with a 422 instead of being applied as a no-op.
    """

    name: str | None = Field(default=None, min_length=1, max_length=100)
    month: int | None = Field(default=None, ge=1, le=12)
    year: int | None = Field(default=None, ge=2000)
    total_limit: Decimal | None = Field(default=None, gt=0, le=MONEY_MAX)
    currency: Literal["PKR", "USD"] | None = Field(default=None, description="Currency code (PKR or USD)")

    _reject_nulls = field_validator(*BUDGET_FIELDS, mode="before")(reject_null_budget_field)


class MonthlyBudgetRead(MonthlyBudgetBase):
    """Schema for reading monthly budget data."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Budget unique identifier")
    user_id: UUID = Field(description="Owner user ID")
    total_spent: Decimal = Field(
        default=Decimal("0"),
        description="Total spent against this budget's month so far (populated by list/detail queries)",
    )
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
    def convert_reminder_time(cls, v: Any) -> str | None:
        """Convert datetime.time objects to HH:MM:SS strings."""
        if isinstance(v, time):
            return v.strftime("%H:%M:%S")
        return v  # type: ignore[no-any-return]


class MonthlyBudgetWithCategories(MonthlyBudgetRead):
    """Monthly budget read schema with nested category breakdowns.

    Serialized as ``categories``; ``validation_alias`` keeps the ORM
    attribute lookup on ``daily_categories`` without leaking the alias to
    the response payload.
    """

    model_config = ConfigDict(populate_by_name=True)

    categories: list[CategoryRead] = Field(
        default_factory=list,
        validation_alias="daily_categories",
        description="List of daily categories within this budget",
    )
