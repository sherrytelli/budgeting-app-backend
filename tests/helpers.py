"""Typed helper functions for the UI-contract test suite.

Keeps the test modules focused on assertions: user provisioning, payload
building, and reference-date arithmetic live here.

All dates are built as aware +05:00 device wall-clock datetimes (the app
targets a Pakistani user) unless a test explicitly wants another offset.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

import httpx
from fastapi.testclient import TestClient

API = "/api/v1"

AuthHeaders = dict[str, str]
JsonDict = dict[str, Any]

# Device wall-clock offset used by the user the app targets.
DEVICE_TZ = timezone(timedelta(hours=5))


def _json(response: httpx.Response) -> JsonDict:
    """Parse a response body that must be a JSON object."""
    payload = response.json()
    assert isinstance(payload, dict), f"expected a JSON object, got: {payload!r}"
    return cast(JsonDict, payload)


def unique_email(prefix: str) -> str:
    """Return a unique email so every test owns isolated rows."""
    return f"{prefix}-{uuid4().hex[:10]}@test.com"


def register_user(client: TestClient, email: str, password: str) -> str:
    """Register a user and return its id (201)."""
    response = client.post(
        f"{API}/auth/register",
        json={"email": email, "password": password, "full_name": "Contract Test"},
    )
    assert response.status_code == 201, response.text
    user_id = _json(response).get("id")
    assert isinstance(user_id, str)
    return user_id


def login_headers(client: TestClient, email: str, password: str) -> AuthHeaders:
    """Log in and return bearer headers (200)."""
    response = client.post(
        f"{API}/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200, response.text
    token = _json(response).get("access_token")
    assert isinstance(token, str)
    return {"Authorization": f"Bearer {token}"}


def create_budget(
    client: TestClient,
    headers: AuthHeaders,
    *,
    name: str,
    month: int,
    year: int,
    total_limit: str = "50000.00",
    currency: str = "PKR",
) -> JsonDict:
    """Create a monthly budget and return its payload (201)."""
    response = client.post(
        f"{API}/budgets",
        headers=headers,
        json={
            "name": name,
            "month": month,
            "year": year,
            "total_limit": total_limit,
            "currency": currency,
        },
    )
    assert response.status_code == 201, response.text
    return _json(response)


def create_category(
    client: TestClient,
    headers: AuthHeaders,
    budget_id: str | UUID,
    *,
    name: str = "Food",
    daily_limit: str = "500.00",
) -> JsonDict:
    """Create a daily category inside a budget and return its payload (201)."""
    response = client.post(
        f"{API}/budgets/{budget_id}/categories",
        headers=headers,
        json={"name": name, "daily_limit": daily_limit, "icon": "utensils"},
    )
    assert response.status_code == 201, response.text
    return _json(response)


def post_expense(
    client: TestClient,
    headers: AuthHeaders,
    daily_category_id: str | UUID,
    *,
    amount: int | float | str = "150.00",
    spent_at: datetime,
    note: str | None = None,
) -> httpx.Response:
    """POST an expense; returns the raw response so tests can assert on it."""
    payload: JsonDict = {
        "daily_category_id": str(daily_category_id),
        "amount": amount,
        "spent_at": spent_at.isoformat(),
    }
    if note is not None:
        payload["note"] = note
    # starlette's TestClient types its httpx dependency loosely (httpx2 fallback),
    # so the return value needs an explicit narrowing for mypy strict.
    return cast(httpx.Response, client.post(f"{API}/expenses", headers=headers, json=payload))


def device_datetime(year: int, month: int, day: int, hour: int = 12, minute: int = 0) -> datetime:
    """Build an aware +05:00 wall-clock datetime, as a device would send it."""
    return datetime(year, month, day, hour, minute, tzinfo=DEVICE_TZ)


def utc_today() -> date:
    """Today's date on the server's UTC clock."""
    return datetime.now(UTC).date()


def shift_month(year: int, month: int, offset: int) -> tuple[int, int]:
    """Shift a (year, month) pair by a whole number of months."""
    index = year * 12 + (month - 1) + offset
    return index // 12, index % 12 + 1


def previous_month(today: date | None = None) -> tuple[int, int]:
    """Return (year, month) of the calendar month before ``today``.

    Expenses for past months are always legal (never future-dated), which
    keeps month-scoped tests independent of the date they run on.
    """
    ref = today if today is not None else utc_today()
    return shift_month(ref.year, ref.month, -1)


def money(value: Any) -> Decimal:
    """Parse a wire-format money value (string or number) for exact comparison."""
    return Decimal(str(value))
