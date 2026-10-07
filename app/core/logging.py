"""Structured logging configuration using structlog with JSON output."""

import logging
import uuid

import structlog


def add_request_id(
    logger: structlog.typing.WrappedLogger,
    method_name: str,
    event_dict: dict[str, object],
) -> dict[str, object]:
    """Add a unique request ID to every log event for correlation."""
    if "request_id" not in event_dict:
        event_dict["request_id"] = str(uuid.uuid4())
    return event_dict


def configure_logging(level: int = logging.INFO) -> None:
    """Configure structlog with JSON renderer for structured logging.

    This should be called once at application startup.

    Args:
        level: The logging level to use (default: INFO).
    """
    structlog.configure(
        processors=[
            add_request_id,
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure the standard library logger to integrate with structlog
    logging.basicConfig(
        format="%(message)s",
        level=level,
    )


def get_logger(name: str | None = None) -> structlog.typing.FilteringBoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name (usually __name__).

    Returns:
        A bound logger instance.
    """
    return structlog.get_logger(name or __name__)
