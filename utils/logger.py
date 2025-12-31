import inspect
import json
import logging
import sys
import threading
from typing import Any

from loguru import logger


class InterceptHandler(logging.Handler):

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

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def structured_formatter(record: dict[str, Any]) -> str:
    """
    Convert log record to JSON string with request_id, latency_ms, status fields.

    This enables structured logging for LLM requests and other operations.
    Extra context can be bound using logger.bind(request_id=..., latency_ms=..., status=...).
    """
    log_data = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "message": record["message"],
        "file": record["file"].name,
        "line": record["line"],
    }

    # Add bound context (request_id, latency_ms, status, etc.)
    extra = record.get("extra", {})
    if "request_id" in extra:
        log_data["request_id"] = str(extra["request_id"])
    if "latency_ms" in extra:
        log_data["latency_ms"] = int(extra["latency_ms"])
    if "status" in extra:
        log_data["status"] = extra["status"]

    return json.dumps(log_data)


lock = threading.Lock()


def stop_logging() -> None:
    models = ["httpcore", "httpx", "apscheduler", "elastic_transport", "sqlalchemy"]
    for model in models:
        logger.disable(model)


def setup_logging():
    with lock:
        logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

        # remove every other logger's handlers
        # and propagate to root logger
        for name in logging.root.manager.loggerDict.keys():
            logging.getLogger(name).handlers = []
            logging.getLogger(name).propagate = True
        logger.remove()  # Will remove all handlers already configured

        stop_logging()

        # Console output with human-readable format
        logger.add(
            sink=sys.stdout,
            format="<white>{time:YYYY-MM-DD HH:mm:ss}</white>"
            " | <level>{level: <8}</level>"
            " | <cyan><b>{line}</b></cyan>"
            " - <white><b>{message}</b></white>",
        )

        # File output with structured JSON format
        logger.add(
            sink="./logs/app.log",
            format=structured_formatter,
            level="DEBUG",
            rotation="10 MB",
            retention="10 days",
            compression="zip",
        )
        logger.opt(colors=True)
