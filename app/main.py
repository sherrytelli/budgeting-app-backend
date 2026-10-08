"""FastAPI application assembly.

This module wires together the FastAPI application with:
- CORS middleware
- Structured logging middleware (request ID, timing, colored console output in dev)
- Exception handlers (HTTPException, ValidationError, generic 500)
- API v1 router inclusion
- Health check endpoint
"""

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app import __version__
from app.api.v1.api import api_router
from app.core.config import get_settings

from app.core.logging import configure_logging, get_logger

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler.

    Configures structured logging on startup and logs shutdown.
    Database tables must be created via Alembic before the app starts.
    """
    # Startup: configure structured logging
    configure_logging(level=logging.INFO, environment=settings.ENVIRONMENT)

    # Disable uvicorn's built-in access log to avoid duplication with our middleware
    uvicorn_logger = logging.getLogger("uvicorn.access")
    uvicorn_logger.disabled = True

    logger = get_logger(__name__)
    logger.info("application_startup")

    yield

    # Shutdown
    logger.info("application_shutdown")


# --- FastAPI Application ---

app = FastAPI(
    title="Budgeting App Backend",
    description="A production-ready FastAPI backend for a personal budgeting Android app with hierarchical budgeting, JWT authentication, and PostgreSQL.",
    version=__version__,
    lifespan=lifespan,
)

# --- CORS Middleware ---

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Structured Logging Middleware ---


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware that adds request ID, timing, and structured logging for every request."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    start_time = time.perf_counter()

    response = await call_next(request)

    process_time = time.perf_counter() - start_time

    logger = get_logger("http_request")
    logger.info(
        "request_completed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round(process_time * 1000, 2),
        request_id=request_id,
    )

    response.headers["X-Request-ID"] = request_id
    return response


# --- Exception Handlers ---


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors with a consistent JSON response."""
    logger = get_logger("validation_error")
    logger.warning(
        "validation_failed",
        method=request.method,
        path=request.url.path,
        errors=exc.errors(),
    )

    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation error",
            "errors": exc.errors(),
        },
    )


@app.exception_handler(ValidationError)
async def pydantic_validation_exception_handler(
    request: Request, exc: ValidationError
) -> JSONResponse:
    """Handle standalone Pydantic V2 validation errors."""
    logger = get_logger("validation_error")
    logger.warning(
        "pydantic_validation_failed",
        method=request.method,
        path=request.url.path,
        errors=exc.errors(),
    )

    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation error",
            "errors": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions with a 500 Internal Server Error."""
    logger = get_logger("unhandled_error")
    logger.error(
        "unhandled_exception",
        method=request.method,
        path=request.url.path,
        error=str(exc),
        exc_info=True,
    )

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
        },
    )


# --- API Router Inclusion ---

app.include_router(api_router)


# --- Health Check Endpoint ---


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for Docker and load balancer probes."""
    return {"status": "ok"}
