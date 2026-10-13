"""Contract tests for the monthly budget endpoints.

Covers the conflict (409), null-rejection, and currency contracts, plus the
response-key (``categories``), ``total_spent``/``month`` list contract, and
write-then-immediate-read visibility.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from tests.conftest import ProvisionedUser
from tests.helpers import (
    create_budget,
    create_category,
    device_datetime,
    money,
    post_expense,
    previous_month,
    shift_month,
)


def test_duplicate_budget_post_returns_409(client: TestClient, active_user: ProvisionedUser) -> None:
    """A second POST with the same name/month/year is a 409, not a 500."""
    payload = {"name": "Regular", "month": 10, "year": 2026, "total_limit": "50000.00"}

    first = client.post("/api/v1/budgets", headers=active_user.headers, json=payload)
    assert first.status_code == 201, first.text

    second = client.post("/api/v1/budgets", headers=active_user.headers, json=payload)
    assert second.status_code == 409, second.text
    assert "Regular" in second.json()["detail"]


def test_duplicate_budget_rename_via_put_returns_409(client: TestClient, active_user: ProvisionedUser) -> None:
    """Renaming a budget onto an existing duplicate is a 409, not a 500."""
    regular = create_budget(client, active_user.headers, name="Regular", month=10, year=2026)
    create_budget(client, active_user.headers, name="Vacation", month=10, year=2026)

    response = client.put(
        f"/api/v1/budgets/{regular['id']}",
        headers=active_user.headers,
        json={"name": "Vacation"},
    )
    assert response.status_code == 409, response.text


def test_explicit_null_name_returns_field_level_422(client: TestClient, active_user: ProvisionedUser) -> None:
    """PUT {"name": null} is a field-level 422, not a 500."""
    budget = create_budget(client, active_user.headers, name="Regular", month=10, year=2026)

    response = client.put(
        f"/api/v1/budgets/{budget['id']}",
        headers=active_user.headers,
        json={"name": None},
    )
    assert response.status_code == 422, response.text
    body = response.json()
    assert isinstance(body["errors"], list)
    assert any("name" in error["loc"] for error in body["errors"])


def test_eur_currency_returns_422(client: TestClient, active_user: ProvisionedUser) -> None:
    """Only PKR and USD are accepted as currency codes."""
    response = client.post(
        "/api/v1/budgets",
        headers=active_user.headers,
        json={"name": "Regular", "month": 10, "year": 2026, "total_limit": "50000.00", "currency": "EUR"},
    )
    assert response.status_code == 422, response.text
    body = response.json()
    assert isinstance(body["errors"], list)
    assert any("currency" in error["loc"] for error in body["errors"])


def test_budget_detail_exposes_categories_key(client: TestClient, active_user: ProvisionedUser) -> None:
    """Budget detail serializes the nested list as ``categories`` (name ASC)."""
    budget = create_budget(client, active_user.headers, name="Regular", month=10, year=2026)
    create_category(client, active_user.headers, budget["id"], name="Zebra")
    create_category(client, active_user.headers, budget["id"], name="Apple")

    response = client.get(f"/api/v1/budgets/{budget['id']}", headers=active_user.headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert "categories" in body
    assert "daily_categories" not in body
    assert [category["name"] for category in body["categories"]] == ["Apple", "Zebra"]


def test_budget_list_carries_total_spent_and_month_filter(client: TestClient, active_user: ProvisionedUser) -> None:
    """List rows carry total_spent and the month filter excludes other months."""
    year, month = previous_month()
    old_year, old_month = shift_month(year, month, -2)
    headers = active_user.headers

    regular = create_budget(client, headers, name="Regular", month=month, year=year)
    create_budget(client, headers, name="Vacation", month=month, year=year)
    create_budget(client, headers, name="Old", month=old_month, year=old_year)
    category = create_category(client, headers, regular["id"], name="Food")
    expense = post_expense(client, headers, category["id"], amount="250.00", spent_at=device_datetime(year, month, 15))
    assert expense.status_code == 201, expense.text

    unfiltered = client.get("/api/v1/budgets", headers=headers)
    assert unfiltered.status_code == 200, unfiltered.text
    assert {"Regular", "Vacation", "Old"} <= {row["name"] for row in unfiltered.json()}

    filtered = client.get("/api/v1/budgets", headers=headers, params={"month": month, "year": year})
    assert filtered.status_code == 200, filtered.text
    rows = filtered.json()
    assert {row["name"] for row in rows} == {"Regular", "Vacation"}
    totals = {row["name"]: money(row["total_spent"]) for row in rows}
    assert totals["Regular"] == Decimal("250.00")
    assert totals["Vacation"] == Decimal("0")


def test_write_then_immediate_read_sees_committed_data(client: TestClient, active_user: ProvisionedUser) -> None:
    """Each request runs a fresh session; a write must already be committed."""
    year, month = previous_month()
    headers = active_user.headers
    budget = create_budget(client, headers, name="Regular", month=month, year=year)
    category = create_category(client, headers, budget["id"], name="Food")

    created = post_expense(
        client, headers, category["id"], amount="99.50", spent_at=device_datetime(year, month, 15, hour=9)
    )
    assert created.status_code == 201, created.text
    expense_id = created.json()["id"]

    fetched = client.get(f"/api/v1/expenses/{expense_id}", headers=headers)
    assert fetched.status_code == 200, fetched.text
    assert money(fetched.json()["amount"]) == Decimal("99.50")
    assert fetched.json()["spent_date"] == f"{year}-{month:02d}-15"

    listed = client.get("/api/v1/expenses", headers=headers, params={"budget_id": budget["id"]})
    assert listed.status_code == 200, listed.text
    assert [row["id"] for row in listed.json()] == [expense_id]
