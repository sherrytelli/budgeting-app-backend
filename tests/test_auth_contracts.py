"""Contract tests for the authentication endpoints.

Covers case-insensitive login and the active-user requirement enforced on
protected routes.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import ProvisionedUser
from tests.helpers import API, login_headers, register_user, unique_email


def test_login_is_case_insensitive(client: TestClient) -> None:
    """Emails are stored lowercase; login must accept any casing."""
    email = unique_email("MiXeD")
    password = "Contract-Test-Passw0rd!"
    register_user(client, email, password)

    headers = login_headers(client, email.upper(), password)
    assert headers["Authorization"].startswith("Bearer ")


def test_inactive_user_is_rejected_with_403(client: TestClient, inactive_user: ProvisionedUser) -> None:
    """A valid JWT for a deactivated account is rejected with 403."""
    response = client.get(f"{API}/budgets", headers=inactive_user.headers)
    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "User account is inactive"
