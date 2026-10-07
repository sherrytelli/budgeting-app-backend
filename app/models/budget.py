"""Monthly budget model with daily category breakdowns."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.category import DailyCategory
    from app.models.user import User


class MonthlyBudget(Base, TimestampMixin):
    """Monthly budget for a user.

    Represents the total spending limit for a specific month and year.
    Can be subdivided into daily category budgets via DailyCategory.
    """

    __tablename__ = "monthly_budgets"

    __table_args__ = (
        UniqueConstraint("user_id", "month", "year", name="uq_monthly_budget_user_month_year"),
        CheckConstraint("month >= 1 AND month <= 12", name="ck_monthly_budget_month_range"),
        CheckConstraint("year >= 2000", name="ck_monthly_budget_year_range"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    month: Mapped[int] = mapped_column()
    year: Mapped[int] = mapped_column()
    total_limit: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="PKR")

    user: Mapped["User"] = relationship("User", back_populates="monthly_budgets")
    daily_categories: Mapped[list["DailyCategory"]] = relationship(
        "DailyCategory",
        back_populates="monthly_budget",
        cascade="all, delete-orphan",
    )
