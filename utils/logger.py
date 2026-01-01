"""
CortexReview Platform - Logging Configuration

Configures loguru with structured JSON logging for observability (Constitution XI).
Supports trace_id binding for request correlation across async tasks.
"""

import inspect
import json
import logging
import sys
import threading
from typing import Any

from loguru import logger


class InterceptHandler(logging.Handler):
    """
    Intercept standard logging and redirect to loguru.

    This enables all third-party libraries to use the same logging configuration.
    """

    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding Loguru level if it exists.
        level: str | int
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message.
        frame, depth = inspect.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def structured_formatter(record: dict[str, Any]) -> str:
    """
    Convert log record to JSON string with structured fields (Constitution XI).

    Enables structured logging for:
    - trace_id: Request correlation across async tasks (Constitution VII)
    - request_id: Individual request tracking
    - latency_ms: Operation latency in milliseconds
    - status: Operation status (success, error, timeout, etc.)

    Extra context can be bound using:
        logger.bind(trace_id=..., request_id=..., latency_ms=..., status=...)
    """
    log_data = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "message": record["message"],
        "file": record["file"].name,
        "line": record["line"],
        "function": record["function"],
    }

    # Add bound context (trace_id, request_id, latency_ms, status, etc.)
    extra = record.get("extra", {})

    # Trace ID for request correlation (Constitution VII)
    if "trace_id" in extra:
        log_data["trace_id"] = str(extra["trace_id"])

    # Request ID for individual request tracking
    if "request_id" in extra:
        log_data["request_id"] = str(extra["request_id"])

    # Latency tracking for observability (Constitution XI)
    if "latency_ms" in extra:
        log_data["latency_ms"] = int(extra["latency_ms"])

    # Operation status
    if "status" in extra:
        log_data["status"] = extra["status"]

    # Platform identifier
    if "platform" in extra:
        log_data["platform"] = extra["platform"]

    # Task ID for Celery task tracking
    if "task_id" in extra:
        log_data["task_id"] = str(extra["task_id"])

    # Repository ID for multi-tenant context
    if "repo_id" in extra:
        log_data["repo_id"] = extra["repo_id"]

    # PR number for context
    if "pr_number" in extra:
        log_data["pr_number"] = extra["pr_number"]

    return json.dumps(log_data)


# Thread-safe lock for logging setup
lock = threading.Lock()


def stop_logging() -> None:
    """
    Disable noisy loggers from third-party libraries.

    Reduces log noise from HTTP clients and database drivers.
    """
    noisy_loggers = [
        "httpcore",
        "httpx",
        "apscheduler",
        "elastic_transport",
        "sqlalchemy",
        "urllib3",
        "git",
        "PIL",
    ]
    for module_name in noisy_loggers:
        logger.disable(module_name)


def setup_logging(log_level: str = "INFO") -> None:
    """
    Configure loguru for console and file logging.

    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Configuration:
    - Console: Human-readable colored output for development
    - File: Structured JSON for log aggregation (Constitution XI)
    - Rotation: 10 MB per file
    - Retention: 10 days
    - Compression: ZIP

    Trace ID Binding:
        Use logger.bind(trace_id=...) to add correlation ID to all logs.
        This is essential for tracking async Celery tasks (Constitution VII).

    Example:
        # In main.py
        trace_id = str(uuid.uuid4())
        logger.bind(trace_id=trace_id).info("Webhook received")

        # In worker.py (Celery task)
        logger.bind(trace_id=trace_id).info("Processing code review")

        # In codereview/copilot.py
        request_id = str(uuid.uuid4())
        start_time = time.time()
        logger.bind(request_id=request_id, trace_id=trace_id).info("LLM request started")
        # ... make request ...
        latency_ms = int((time.time() - start_time) * 1000)
        logger.bind(request_id=request_id, trace_id=trace_id, latency_ms=latency_ms, status="success").info("LLM request completed")
    """
    with lock:
        # Intercept standard logging
        logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

        # Remove all other logger handlers and propagate to root
        for name in logging.root.manager.loggerDict.keys():
            logging.getLogger(name).handlers = []
            logging.getLogger(name).propagate = True

        # Remove default loguru handler
        logger.remove()

        # Disable noisy loggers
        stop_logging()

        # -------------------------------------------------------------------------
        # Console Handler: Human-readable colored output (development)
        # -------------------------------------------------------------------------
        logger.add(
            sink=sys.stdout,
            format=(
                "<white>{time:YYYY-MM-DD HH:mm:ss}</white>"
                " | <level>{level: <8}</level>"
                " | <cyan><b>{line}</b></cyan>"
                " - <white><b>{message}</b></white>"
            ),
            level=log_level,
            colorize=True,
            backtrace=True,
            diagnose=True,
        )

        # -------------------------------------------------------------------------
        # File Handler: Structured JSON for log aggregation (Constitution XI)
        # -------------------------------------------------------------------------
        # Gracefully handle permission errors (e.g., in containerized environments)
        try:
            logger.add(
                sink="./logs/app.log",
                format="{message}",  # Raw message - structured JSON added via bind()
                level="DEBUG",
                rotation="10 MB",
                retention="10 days",
                compression="zip",
                enqueue=True,  # Thread-safe logging
                serialize=True,  # Enable JSON serialization
            )
        except (PermissionError, OSError) as e:
            # Fall back to console-only logging if file logging fails
            logger.warning(f"File logging disabled due to permission error: {e}")

        # Optional: Separate file for errors
        try:
            logger.add(
                sink="./logs/error.log",
                format="{message}",  # Raw message - structured JSON added via bind()
                level="ERROR",
                rotation="10 MB",
                retention="30 days",
                compression="zip",
                enqueue=True,
                serialize=True,  # Enable JSON serialization
            )
        except (PermissionError, OSError) as e:
            logger.warning(f"Error file logging disabled due to permission error: {e}")

        logger.opt(colors=True)


def get_logger(trace_id: str = None, **kwargs):
    """
    Get a logger with pre-bound context for request correlation.

    Args:
        trace_id: Request correlation ID for async task tracking
        **kwargs: Additional context to bind (request_id, platform, repo_id, etc.)

    Returns:
        loguru logger with bound context

    Example:
        logger = get_logger(trace_id="abc-123", platform="github", repo_id="user/repo")
        logger.info("Processing webhook")
        # All logs include: trace_id, platform, repo_id
    """
    context = {}
    if trace_id:
        context["trace_id"] = trace_id
    context.update(kwargs)

    return logger.bind(**context)


# =============================================================================
# Module Exports
# =============================================================================
__all__ = [
    "InterceptHandler",
    "get_logger",
    "logger",
    "setup_logging",
    "structured_formatter",
]
