"""Endpoint routers package.

Exports all versioned endpoint routers so they can be imported
by the parent ``api.py`` module.
"""

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.budgets import router as budgets_router
from app.api.v1.endpoints.categories import router as categories_router
from app.api.v1.endpoints.expenses import router as expenses_router

__all__ = [
    "auth_router",
    "budgets_router",
    "categories_router",
    "expenses_router",
]
