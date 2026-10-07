"""Versioned API package.

This package assembles all v1 endpoint routers under a single router
with the ``/api/v1`` prefix, making it easy to include in the main
FastAPI application.
"""

from app.api.v1.api import api_router

__all__ = ["api_router"]
