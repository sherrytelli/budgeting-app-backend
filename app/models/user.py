"""User model with authentication fields and budget relationships."""

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.budget import MonthlyBudget


class User(Base, TimestampMixin):
    """User account model.

    Each user can have multiple monthly budgets across different months and years.
    """

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(default=True)

    monthly_budgets: Mapped[list["MonthlyBudget"]] = relationship(
        "MonthlyBudget",
        back_populates="user",
        cascade="all, delete-orphan",
    )
