"""Daily category model for budget category breakdowns."""

from datetime import datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Time,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.budget import MonthlyBudget
    from app.models.expense import Expense


class DailyCategory(Base, TimestampMixin):
    """Daily spending category within a monthly budget.

    Each category represents a spending category (e.g., Food, Transport)
    with its own daily limit and optional reminder time.
    """

    __tablename__ = "daily_categories"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    monthly_budget_id: Mapped[UUID] = mapped_column(ForeignKey("monthly_budgets.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(50))
    daily_limit: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    reminder_time: Mapped[time | None] = mapped_column(Time(timezone=False), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(20), nullable=True)

    monthly_budget: Mapped["MonthlyBudget"] = relationship(
        "MonthlyBudget",
        back_populates="daily_categories",
    )
    expenses: Mapped[list["Expense"]] = relationship(
        "Expense",
        back_populates="daily_category",
        cascade="all, delete-orphan",
    )
