"""Expense model for granular expense tracking."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.category import DailyCategory


class Expense(Base, TimestampMixin):
    """Individual expense record.

    Each expense is tied to a daily category and has an amount, optional note,
    and a timestamp for when it was spent.
    """

    __tablename__ = "expenses"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    daily_category_id: Mapped[UUID] = mapped_column(
        ForeignKey("daily_categories.id", ondelete="CASCADE"),
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    note: Mapped[str | None] = mapped_column(String(500))
    spent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    daily_category: Mapped["DailyCategory"] = relationship(
        "DailyCategory",
        back_populates="expenses",
    )
