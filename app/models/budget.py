"""Monthly budget model with daily category breakdowns."""

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.category import DailyCategory
    from app.models.user import User


class MonthlyBudget(Base, TimestampMixin):
    """Monthly budget for a user.

    Represents the total spending limit for a specific month and year.
    Multiple named budgets can exist per month (e.g., "Regular", "Vacation").
    Can be subdivided into daily category budgets via DailyCategory.
    """

    __tablename__ = "monthly_budgets"

    __table_args__ = (
        UniqueConstraint(
            "user_id", "name", "month", "year",
            name="uq_monthly_budget_user_name_month_year",
        ),
        CheckConstraint("month >= 1 AND month <= 12", name="ck_monthly_budget_month_range"),
        CheckConstraint("year >= 2000", name="ck_monthly_budget_year_range"),
        # Base renders this through "ck_%(table_name)s_%(constraint_name)s",
        # yielding the DB-level name ck_monthly_budgets_currency (the matching
        # migration declares that final name directly via op.f(...)).
        CheckConstraint("currency IN ('PKR', 'USD')", name="currency"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    month: Mapped[int] = mapped_column()
    year: Mapped[int] = mapped_column()
    total_limit: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="PKR")

    user: Mapped["User"] = relationship("User", back_populates="monthly_budgets")
    daily_categories: Mapped[list["DailyCategory"]] = relationship(
        "DailyCategory",
        back_populates="monthly_budget",
        cascade="all, delete-orphan",
        # Default all loads (lazy and eager) to name-ASC so every endpoint
        # returns a consistent category order without per-query sorting.
        order_by="DailyCategory.name",
    )
