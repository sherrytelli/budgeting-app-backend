"""add spent_date and harden currency/email constraints

Adds the day-grouping key ``expenses.spent_date`` (backfilled from
``spent_at``), a currency check constraint on ``monthly_budgets``, and a
case-insensitive unique index on ``users.email``.  Mirrors the model changes
in ``app/models/expense.py``, ``app/models/budget.py`` and
``app/models/user.py``.

Revision ID: 81a8f0f42907
Revises: c5739fce7544
Create Date: 2026-10-13 22:50:15.559360
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '81a8f0f42907'
down_revision: str | None = 'c5739fce7544'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade migration steps."""
    # Step 1: Add expenses.spent_date as nullable so existing rows don't fail
    op.add_column('expenses', sa.Column('spent_date', sa.Date(), nullable=True))

    # Step 2: Backfill from spent_at's UTC wall-clock date (zero rows today;
    # a safety net so the NOT NULL flip below can never fail)
    op.execute(
        """
        UPDATE expenses
        SET spent_date = (spent_at AT TIME ZONE 'UTC')::date
        WHERE spent_date IS NULL
        """
    )

    # Step 3: Set NOT NULL after the backfill is complete
    op.alter_column('expenses', 'spent_date', nullable=False)

    # Step 4: Composite index powering the daily panel query;
    # ix_expenses_spent_at stays for chronological ordering
    op.create_index(
        'ix_expenses_daily_category_spent_date',
        'expenses',
        ['daily_category_id', 'spent_date'],
        unique=False,
    )

    # Step 5: Only the two supported currencies are allowed.  op.f() marks the
    # name as already convention-applied so the metadata naming convention
    # ("ck_%(table_name)s_%(constraint_name)s") does not mangle it; the model
    # mirror in app/models/budget.py declares name="currency", which renders
    # to this same ck_monthly_budgets_currency.
    op.create_check_constraint(
        op.f('ck_monthly_budgets_currency'),
        'monthly_budgets',
        "currency IN ('PKR', 'USD')",
    )

    # Step 6: Normalize existing emails, then make case-insensitive
    # duplicates impossible (keeps /auth/register open while hardening it)
    op.execute("UPDATE users SET email = lower(email)")
    op.create_index(
        'uq_users_email_lower',
        'users',
        [sa.func.lower(sa.text('email'))],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade migration steps."""
    # Reverse order of upgrade(); the two data normalizations (backfill and
    # lowercased emails) are intentionally not reversible.
    op.drop_index('uq_users_email_lower', table_name='users')
    op.drop_constraint(
        op.f('ck_monthly_budgets_currency'),
        'monthly_budgets',
        type_='check',
    )
    op.drop_index('ix_expenses_daily_category_spent_date', table_name='expenses')
    op.alter_column('expenses', 'spent_date', nullable=True)
    op.drop_column('expenses', 'spent_date')
