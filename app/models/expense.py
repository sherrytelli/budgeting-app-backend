"""Expense model for granular expense tracking."""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.category import DailyCategory


class Expense(Base, TimestampMixin):
    """Individual expense record.

    Each expense is tied to a daily category and has an amount, optional note,
    a timestamp for when it was spent, and the wall-clock day that expense
    belongs to (derived from ``spent_at``).
    """

    __tablename__ = "expenses"

    __table_args__ = (
        # Powers the per-day panel query; ix_expenses_spent_at keeps ordering fast.
        Index(
            "ix_expenses_daily_category_spent_date",
            "daily_category_id",
            "spent_date",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    daily_category_id: Mapped[UUID] = mapped_column(
        ForeignKey("daily_categories.id", ondelete="CASCADE"),
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    note: Mapped[str | None] = mapped_column(String(500))
    spent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    spent_date: Mapped[date] = mapped_column(Date)

    daily_category: Mapped["DailyCategory"] = relationship(
        "DailyCategory",
        back_populates="expenses",
    )
