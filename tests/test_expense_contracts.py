"""Contract tests for the expense endpoints.

Covers the 422 contracts (amount, naive timestamps, month/future date rules),
the ``spent_date`` day-grouping proof that motivated the column, the
zero-spend rows of the daily panel, and the ``budget_id`` list filter.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from tests.conftest import ProvisionedUser
from tests.helpers import (
    API,
    create_budget,
    create_category,
    device_datetime,
    money,
    post_expense,
    previous_month,
    shift_month,
    utc_today,
)


def test_zero_amount_returns_field_level_422(client: TestClient, active_user: ProvisionedUser) -> None:
    """amount: 0 returns a field-level 422 with JSON-serializable errors."""
    response = post_expense(
        client, active_user.headers, uuid4(), amount=0, spent_at=device_datetime(2026, 10, 12)
    )
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["detail"] == "Validation error"
    assert isinstance(body["errors"], list)
    assert any("amount" in error["loc"] for error in body["errors"])


def test_naive_spent_at_returns_422(client: TestClient, active_user: ProvisionedUser) -> None:
    """A spent_at without a UTC offset is rejected, never silently coerced."""
    year, month = previous_month()
    budget = create_budget(client, active_user.headers, name="Regular", month=month, year=year)
    category = create_category(client, active_user.headers, budget["id"])

    response = client.post(
        f"{API}/expenses",
        headers=active_user.headers,
        json={
            "daily_category_id": category["id"],
            "amount": "100.00",
            "spent_at": f"{year}-{month:02d}-15T13:30:00",  # naive: no UTC offset
        },
    )
    assert response.status_code == 422, response.text
    body = response.json()
    assert isinstance(body["errors"], list)
    assert any("spent_at" in error["loc"] for error in body["errors"])


def test_future_spent_date_returns_422(client: TestClient, active_user: ProvisionedUser) -> None:
    """A spent_at beyond tomorrow (any UTC offset) is rejected."""
    future = datetime.now(UTC) + timedelta(days=30)
    month, year = future.month, future.year
    budget = create_budget(client, active_user.headers, name="Regular", month=month, year=year)
    category = create_category(client, active_user.headers, budget["id"])

    response = post_expense(
        client, active_user.headers, category["id"], spent_at=device_datetime(year, month, future.day)
    )
    assert response.status_code == 422, response.text
    assert "future" in response.json()["detail"]


def test_out_of_month_spent_date_returns_422(client: TestClient, active_user: ProvisionedUser) -> None:
    """A spent_at outside the budget's month is rejected."""
    year, month = previous_month()
    budget = create_budget(client, active_user.headers, name="Regular", month=month, year=year)
    category = create_category(client, active_user.headers, budget["id"])

    old_year, old_month = shift_month(year, month, -2)
    response = post_expense(
        client, active_user.headers, category["id"], spent_at=device_datetime(old_year, old_month, 15)
    )
    assert response.status_code == 422, response.text
    assert "outside budget month" in response.json()["detail"]


def test_wall_clock_midnight_expense_stays_on_its_day(client: TestClient, active_user: ProvisionedUser) -> None:
    """An expense at 00:30 +05:00 lands on the wall-clock day, not the UTC day."""
    today = utc_today()
    headers = active_user.headers
    budget = create_budget(client, headers, name="Regular", month=today.month, year=today.year)
    category = create_category(client, headers, budget["id"], name="Food")

    # 00:30 on the device's "today" is 19:30 UTC on the previous day; the
    # expense must still count against today's panel.
    created = post_expense(
        client,
        headers,
        category["id"],
        amount="120.00",
        spent_at=device_datetime(today.year, today.month, today.day, hour=0, minute=30),
    )
    assert created.status_code == 201, created.text
    assert created.json()["spent_date"] == today.isoformat()

    panel = client.get(
        f"{API}/budgets/{budget['id']}/daily",
        headers=headers,
        params={"date": today.isoformat()},
    )
    assert panel.status_code == 200, panel.text
    food = next(row for row in panel.json() if row["id"] == category["id"])
    assert money(food["spent"]) == Decimal("120.00")
    assert [expense["id"] for expense in food["expenses"]] == [created.json()["id"]]

    # The UTC instant sits on the previous day; that day's panel must be empty.
    if today.day > 1:
        yesterday = today - timedelta(days=1)
        prior_panel = client.get(
            f"{API}/budgets/{budget['id']}/daily",
            headers=headers,
            params={"date": yesterday.isoformat()},
        )
        assert prior_panel.status_code == 200, prior_panel.text
        prior_food = next(row for row in prior_panel.json() if row["id"] == category["id"])
        assert money(prior_food["spent"]) == Decimal("0")
        assert prior_food["expenses"] == []


def test_daily_panel_includes_zero_spend_categories(client: TestClient, active_user: ProvisionedUser) -> None:
    """The daily panel lists every category, even those without spending."""
    year, month = previous_month()
    headers = active_user.headers
    budget = create_budget(client, headers, name="Regular", month=month, year=year)
    food = create_category(client, headers, budget["id"], name="Food")
    create_category(client, headers, budget["id"], name="Transport")

    created = post_expense(
        client, headers, food["id"], amount="80.00", spent_at=device_datetime(year, month, 15)
    )
    assert created.status_code == 201, created.text

    panel = client.get(
        f"{API}/budgets/{budget['id']}/daily",
        headers=headers,
        params={"date": f"{year}-{month:02d}-15"},
    )
    assert panel.status_code == 200, panel.text
    rows = panel.json()
    assert [row["name"] for row in rows] == ["Food", "Transport"]

    transport_row = rows[1]
    assert money(transport_row["spent"]) == Decimal("0")
    assert transport_row["expenses"] == []


def test_budget_id_filter_returns_only_matching_expenses(client: TestClient, active_user: ProvisionedUser) -> None:
    """The budget_id filter scopes the expense list to one budget."""
    year, month = previous_month()
    headers = active_user.headers
    budget_a = create_budget(client, headers, name="Regular", month=month, year=year)
    budget_b = create_budget(client, headers, name="Vacation", month=month, year=year)
    category_a = create_category(client, headers, budget_a["id"], name="Food")
    category_b = create_category(client, headers, budget_b["id"], name="Food")

    expense_a = post_expense(
        client, headers, category_a["id"], amount="100.00", spent_at=device_datetime(year, month, 15, hour=9)
    )
    expense_b = post_expense(
        client, headers, category_b["id"], amount="500.00", spent_at=device_datetime(year, month, 15, hour=10)
    )
    assert expense_a.status_code == 201, expense_a.text
    assert expense_b.status_code == 201, expense_b.text

    only_a = client.get(f"{API}/expenses", headers=headers, params={"budget_id": budget_a["id"]})
    assert only_a.status_code == 200, only_a.text
    assert [row["id"] for row in only_a.json()] == [expense_a.json()["id"]]

    only_b = client.get(f"{API}/expenses", headers=headers, params={"budget_id": budget_b["id"]})
    assert only_b.status_code == 200, only_b.text
    assert [row["id"] for row in only_b.json()] == [expense_b.json()["id"]]
