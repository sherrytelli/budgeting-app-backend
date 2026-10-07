"""Main API router assembly.

This module aggregates all versioned endpoint routers under a single
``APIRouter`` with the ``/api/v1`` prefix, making it easy to include
in the main FastAPI application.
"""

from fastapi import APIRouter

from app.api.v1.endpoints.analytics import router as analytics_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.budgets import router as budgets_router
from app.api.v1.endpoints.categories import router as categories_router
from app.api.v1.endpoints.expenses import router as expenses_router

api_router = APIRouter(prefix="/api/v1")

# Register all endpoint routers
# Note: FastAPI automatically prepends the parent router's prefix (/api/v1)
# to included routers, so we don't specify prefix here.
api_router.include_router(auth_router)
api_router.include_router(budgets_router)
api_router.include_router(categories_router)
api_router.include_router(expenses_router)
api_router.include_router(analytics_router)
