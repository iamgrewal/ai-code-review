"""
CortexReview Platform - Celery Application Configuration

Configures Celery for async task processing with Redis broker,
result backend, retry settings, and task time limits (Constitution VII).
"""

import os
from datetime import timedelta

from celery import Celery
from celery.schedules import crontab

from utils.config import Config
from utils.logger import setup_logging

# Initialize logging
setup_logging()

# Load configuration (singleton instance)
config = Config()

# -----------------------------------------------------------------------------
# Celery Application Configuration
# -----------------------------------------------------------------------------

# Create Celery application
app = Celery("cortexreview")

# -----------------------------------------------------------------------------
# Configuration Settings
# -----------------------------------------------------------------------------
app.conf.update(
    # -------------------------------------------------------------------------
    # Broker Configuration (Redis)
    # -------------------------------------------------------------------------
    broker_url=config.CELERY_BROKER_URL,
    result_backend=config.CELERY_RESULT_BACKEND,
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=5,
    broker_connection_retry_delay=5,  # seconds

    # -------------------------------------------------------------------------
    # Task Configuration
    # -------------------------------------------------------------------------
    # Task serialization (JSON for compatibility with observability)
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,

    # Task time limits (Constitution VII - prevent runaway tasks)
    task_time_limit=config.CELERY_TASK_TIME_LIMIT,  # Hard limit (5 minutes default)
    task_soft_time_limit=int(config.CELERY_TASK_TIME_LIMIT * 0.8),  # Soft limit (80%)
    task_acks_late=True,  # Acknowledge after task completion (for reliability)

    # -------------------------------------------------------------------------
    # Result Backend Configuration
    # -------------------------------------------------------------------------
    result_expires=timedelta(hours=24),  # Results expire after 24 hours
    result_extended=True,  # Store extended result info (trace_id, status)

    # -------------------------------------------------------------------------
    # Retry Configuration (Constitution VII - Exponential Backoff)
    # -------------------------------------------------------------------------
    task_autoretry_for=(Exception,),  # Retry on all exceptions
    task_retry_kwargs={
        "max_retries": 3,
        "countdown": 60,  # Initial delay in seconds
    },
    task_retry_delay=60,  # Default retry delay
    task_retry_backoff=True,  # Enable exponential backoff
    task_retry_backoff_max=600,  # Maximum backoff (10 minutes)
    task_retry_jitter=True,  # Add jitter to prevent thundering herd

    # -------------------------------------------------------------------------
    # Worker Configuration
    # -------------------------------------------------------------------------
    worker_prefetch_multiplier=1,  # Disable prefetch (one task at a time)
    worker_max_tasks_per_child=100,  # Restart worker after 100 tasks (memory cleanup)
    worker_concurrency=config.CELERY_WORKER_CONCURRENCY,

    # -------------------------------------------------------------------------
    # Task Routing (Optional - for future scaling)
    # -------------------------------------------------------------------------
    task_routes={
        "worker.process_code_review": {"queue": "code_review"},
        "worker.index_repository": {"queue": "indexing"},
        "worker.process_feedback": {"queue": "feedback"},
    },
    task_default_queue="default",
    task_default_exchange="default",
    task_default_routing_key="default",

    # -------------------------------------------------------------------------
    # Dead Letter Queue (Constitution VII - Failed Task Handling)
    # -------------------------------------------------------------------------
    task_reject_on_worker_lost=True,  # Reject tasks if worker crashes
    task_send_sent_event=True,  # Track task sending events

    # -------------------------------------------------------------------------
    # Monitoring and Observability (Constitution XI)
    # -------------------------------------------------------------------------
    worker_send_task_events=True,  # Enable task events for monitoring
    task_send_event_props=True,  # Include task properties in events
    task_track_started=True,  # Track task start time
    task_compression="gzip",  # Compress large task payloads

    # -------------------------------------------------------------------------
    # Security
    # -------------------------------------------------------------------------
    broker_use_ssl=None,  # Set to True for SSL connections
    result_backend_transport_options=None,  # Configure SSL if needed
)

# -----------------------------------------------------------------------------
# Celery Beat Schedule (Constitution VII - Scheduled Tasks)
# -----------------------------------------------------------------------------
app.conf.beat_schedule = {
    # Daily repository indexing at 2 AM UTC
    "daily-repository-indexing": {
        "task": "worker.index_repository",
        "schedule": crontab(hour=2, minute=0),
        "options": {"expires": 3600},  # Task expires after 1 hour
    },
    # Hourly cleanup of expired constraints
    "cleanup-expired-constraints": {
        "task": "worker.cleanup_expired_constraints",
        "schedule": crontab(minute=0),  # Every hour
    },
    # Daily metrics aggregation (for Prometheus)
    "daily-metrics-aggregation": {
        "task": "worker.aggregate_metrics",
        "schedule": crontab(hour=3, minute=0),
    },
}

# -----------------------------------------------------------------------------
# Task Registration
# -----------------------------------------------------------------------------
# Tasks will be registered when worker.py imports this module
# Tasks are defined in worker.py and auto-discovered by Celery

# -----------------------------------------------------------------------------
# Application Boot Events
# -----------------------------------------------------------------------------
@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """
    Configure periodic tasks after Celery app is ready.

    This runs when the worker starts and ensures all scheduled tasks
    are properly registered with Celery Beat.
    """
    from loguru import logger

    logger.info(
        "CortexReview Celery app configured",
        extra={
            "broker_url": config.CELERY_BROKER_URL,
            "result_backend": config.CELERY_RESULT_BACKEND,
            "worker_concurrency": config.CELERY_WORKER_CONCURRENCY,
            "task_time_limit": config.CELERY_TASK_TIME_LIMIT,
        }
    )


@app.on_after_configure.connect
def verify_task_queues(sender, **kwargs):
    """
    Verify that all required task queues are declared.

    This ensures queues exist before workers start processing tasks.
    """
    from loguru import logger

    queues = ["code_review", "indexing", "feedback", "default"]

    for queue in queues:
        logger.info(f"Task queue verified: {queue}")


# -----------------------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------------------
def get_task_info(task_id: str) -> dict:
    """
    Get information about a Celery task by ID.

    Args:
        task_id: Celery task ID

    Returns:
        dict with task status, result, and metadata
    """
    from celery.result import AsyncResult

    result = AsyncResult(task_id, app=app)

    return {
        "task_id": task_id,
        "status": result.state,
        "result": result.result if result.ready() else None,
        "traceback": result.traceback if result.failed() else None,
    }


def get_queue_depth(queue_name: str = "default") -> int:
    """
    Get the current depth of a Celery queue.

    Args:
        queue_name: Name of the queue to check

    Returns:
        int: Number of tasks in the queue
    """
    from celery import current_app

    with current_app.connection_or_acquire() as conn:
        return conn.default_channel.queue_declare(
            queue=queue_name, passive=True
        ).message_count


def get_active_tasks() -> list:
    """
    Get list of currently active tasks across all workers.

    Returns:
        list of dicts with active task information
    """
    from celery import current_app

    inspect = current_app.control.inspect()
    active = inspect.active()

    if not active:
        return []

    # Flatten active tasks from all workers
    all_active = []
    for worker, tasks in active.items():
        for task in tasks:
            all_active.append({
                "worker": worker,
                "task_id": task["id"],
                "task_name": task["name"],
                "args": task["args"],
                "kwargs": task["kwargs"],
                "time_start": task.get("time_start"),
            })

    return all_active


# -----------------------------------------------------------------------------
# Module Exports
# -----------------------------------------------------------------------------
__all__ = [
    "app",
    "get_task_info",
    "get_queue_depth",
    "get_active_tasks",
]
