"""User model with authentication fields and budget relationships."""

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Index, String, func
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

    __table_args__ = (
        # DB-level case-insensitive uniqueness.  ix_users_email only guards
        # exact-case duplicates, so this expression index blocks
        # case-differing duplicates even under direct SQL.
        Index("uq_users_email_lower", func.lower(email), unique=True),
    )

    monthly_budgets: Mapped[list["MonthlyBudget"]] = relationship(
        "MonthlyBudget",
        back_populates="user",
        cascade="all, delete-orphan",
    )
