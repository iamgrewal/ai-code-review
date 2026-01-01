"""
Prometheus metrics for CortexReview platform observability.

Defines all metrics emitted for monitoring system performance,
costs, and operational health per Constitution XI (Observability).
"""

import redis
from celery import Celery
from prometheus_client import Counter, Gauge, Histogram, Summary

# ============================================================================
# Review Performance Metrics
# ============================================================================

review_duration_seconds = Histogram(
    "cortexreview_review_duration_seconds",
    "Time taken to complete code review from webhook to posting",
    buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, float("inf")),
    labelnames=("platform", "status"),
)

review_duration_summary = Summary(
    "cortexreview_review_duration_summary",
    "Summary statistics for code review duration",
    labelnames=("platform",),
)

# ============================================================================
# RAG (Retrieval-Augmented Generation) Metrics
# ============================================================================

rag_retrieval_latency_seconds = Summary(
    "cortexreview_rag_retrieval_latency_seconds",
    "Time taken to retrieve context from vector database",
    labelnames=("repo_id",),
)

rag_match_count = Histogram(
    "cortexreview_rag_match_count",
    "Number of context matches retrieved per review",
    buckets=(1, 3, 5, 7, 10, 15, 20, float("inf")),
    labelnames=("repo_id",),
)

rag_retrieval_success_total = Counter(
    "cortexreview_rag_retrieval_success_total",
    "Total successful RAG context retrievals",
    labelnames=("repo_id",),
)

rag_retrieval_failure_total = Counter(
    "cortexreview_rag_retrieval_failure_total",
    "Total failed RAG context retrievals",
    labelnames=("repo_id", "reason"),
)

# ============================================================================
# LLM Token Usage Metrics
# ============================================================================

llm_tokens_total = Counter(
    "cortexreview_llm_tokens_total",
    "Total LLM tokens consumed",
    labelnames=("model_type", "model_name"),  # model_type: chat/embedding
)

llm_requests_total = Counter(
    "cortexreview_llm_requests_total",
    "Total LLM API requests made",
    labelnames=("model_type", "model_name", "status"),
)

llm_request_duration_seconds = Histogram(
    "cortexreview_llm_request_duration_seconds",
    "Time taken for LLM API requests",
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, float("inf")),
    labelnames=("model_type", "model_name"),
)

# ============================================================================
# Feedback and Learning Loop Metrics (RLHF)
# ============================================================================

feedback_submitted_total = Counter(
    "cortexreview_feedback_submitted_total",
    "Total feedback submissions for learning loop",
    labelnames=("action",),  # action: accepted/rejected/modified
)

constraint_suppressions_total = Counter(
    "cortexreview_constraint_suppressions_total",
    "Total review comments suppressed by learned constraints",
    labelnames=("repo_id", "confidence_level"),
)

constraint_count = Gauge(
    "cortexreview_constraint_count",
    "Current number of active learned constraints per repository",
    labelnames=("repo_id",),
)

constraint_expirations_total = Counter(
    "cortexreview_constraint_expirations_total",
    "Total constraints expired by age policy",
    labelnames=("repo_id",),
)

false_positive_reduction_ratio = Gauge(
    "cortexreview_false_positive_reduction_ratio",
    "False positive reduction ratio (rejected/total feedback) over 30 days",
    labelnames=("repo_id",),
)

# ============================================================================
# Celery Task Queue Metrics
# ============================================================================

celery_queue_depth = Gauge(
    "cortexreview_celery_queue_depth",
    "Current number of tasks in Celery queue",
    labelnames=("queue_name",),
)

celery_worker_active_tasks = Gauge(
    "cortexreview_celery_worker_active_tasks",
    "Number of active tasks per Celery worker",
    labelnames=("worker_name",),
)

celery_task_duration_seconds = Histogram(
    "cortexreview_celery_task_duration_seconds",
    "Time taken for Celery task execution",
    buckets=(0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0, float("inf")),
    labelnames=("task_name", "status"),
)

celery_task_retry_total = Counter(
    "cortexreview_celery_task_retry_total",
    "Total Celery task retries",
    labelnames=("task_name", "reason"),
)

celery_task_failure_total = Counter(
    "cortexreview_celery_task_failure_total",
    "Total permanently failed Celery tasks",
    labelnames=("task_name", "reason"),
)

# ============================================================================
# Repository Indexing Metrics
# ============================================================================

indexing_duration_seconds = Histogram(
    "cortexreview_indexing_duration_seconds",
    "Time taken to index repository",
    buckets=(10.0, 30.0, 60.0, 300.0, 600.0, 1800.0, float("inf")),
    labelnames=("repo_id", "index_depth"),
)

indexing_files_processed_total = Counter(
    "cortexreview_indexing_files_processed_total",
    "Total files processed during indexing",
    labelnames=("repo_id",),
)

indexing_chunks_embedded_total = Counter(
    "cortexreview_indexing_chunks_embedded_total",
    "Total chunks embedded during indexing",
    labelnames=("repo_id",),
)

indexing_secrets_found_total = Counter(
    "cortexreview_indexing_secrets_found_total",
    "Total secrets detected during indexing",
    labelnames=("repo_id", "secret_type"),
)

# ============================================================================
# Webhook Metrics
# ============================================================================

webhook_received_total = Counter(
    "cortexreview_webhook_received_total",
    "Total webhooks received",
    labelnames=("platform",),
)

webhook_signature_verified_total = Counter(
    "cortexreview_webhook_signature_verified_total",
    "Total webhook signature verifications",
    labelnames=("platform", "result"),  # result: success/failure
)

webhook_parse_errors_total = Counter(
    "cortexreview_webhook_parse_errors_total",
    "Total webhook parsing errors",
    labelnames=("platform", "error_type"),
)

# ============================================================================
# Error Metrics
# ============================================================================

error_total = Counter(
    "cortexreview_error_total",
    "Total errors by component",
    labelnames=("component", "error_type", "severity"),
)

# ============================================================================
# Helper Functions
# ============================================================================


def track_review_duration(platform: str, status: str):
    """Decorator to track review duration."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            with review_duration_seconds.labels(platform=platform, status=status).time():
                return func(*args, **kwargs)

        return wrapper

    return decorator


def track_llm_request(model_type: str, model_name: str):
    """Decorator to track LLM request duration and tokens."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            with llm_request_duration_seconds.labels(
                model_type=model_type, model_name=model_name
            ).time():
                result = func(*args, **kwargs)
                # Extract token count if available in result
                if hasattr(result, "usage"):
                    tokens = result.usage.total_tokens
                    llm_tokens_total.labels(model_type=model_type, model_name=model_name).inc(
                        tokens
                    )
                return result

        return wrapper

    return decorator


# ============================================================================
# Celery Metrics Collection Functions (T081-T082)
# ============================================================================


def update_celery_queue_depth(
    broker_url: str,
    queue_name: str = "celery",
) -> int | None:
    """
    Update Celery queue depth gauge (T081).

    Queries Redis to get current queue length and updates the gauge.

    Args:
        broker_url: Redis broker URL (e.g., redis://localhost:6379/0)
        queue_name: Celery queue name to monitor

    Returns:
        Current queue depth or None if query fails
    """
    try:
        # Parse Redis URL
        if broker_url.startswith("redis://"):
            # Extract host and db from URL
            # Format: redis://localhost:6379/0
            url_parts = broker_url.replace("redis://", "").split("/")
            host_port = url_parts[0]
            db = int(url_parts[1]) if len(url_parts) > 1 else 0

            # Connect to Redis
            r = redis.from_url(f"redis://{host_port}/{db}", decode_responses=True)

            # Get queue length (list length for queue key)
            queue_key = queue_name  # Default Celery queue key
            queue_depth = r.llen(queue_key)

            # Update gauge
            celery_queue_depth.labels(queue_name=queue_name).set(queue_depth)

            return queue_depth

    except Exception:
        # Silent failure - metrics should not crash application
        pass

    return None


def update_celery_worker_active_tasks(celery_app: Celery) -> dict | None:
    """
    Update Celery worker active tasks gauge (T082).

    Queries Celery for active tasks and updates worker gauges.

    Args:
        celery_app: Celery application instance

    Returns:
        Dict mapping worker_name -> active_task_count or None if query fails
    """
    try:
        # Get active tasks from Celery
        inspect = celery_app.control.inspect()
        active_tasks = inspect.active()

        if not active_tasks:
            return {}

        worker_stats = {}
        for worker_name, tasks in active_tasks.items():
            # Count active tasks for this worker
            active_count = len(tasks) if tasks else 0

            # Update gauge
            celery_worker_active_tasks.labels(worker_name=worker_name).set(active_count)

            worker_stats[worker_name] = active_count

        return worker_stats

    except Exception:
        # Silent failure - metrics should not crash application
        pass

    return None


def start_celery_metrics_collector(
    celery_app: Celery,
    broker_url: str,
    queue_name: str = "celery",
    interval_seconds: int = 10,
):
    """
    Start background thread to collect Celery metrics (T081-T082).

    This function should be called during worker startup to begin
    periodic collection of Celery queue depth and worker metrics.

    Args:
        celery_app: Celery application instance
        broker_url: Redis broker URL
        queue_name: Celery queue name to monitor
        interval_seconds: Collection interval (default 10 seconds)
    """
    import threading
    import time

    def collect_metrics():
        """Background metrics collection loop."""
        while True:
            try:
                # Update queue depth (T081)
                update_celery_queue_depth(broker_url, queue_name)

                # Update worker active tasks (T082)
                update_celery_worker_active_tasks(celery_app)

            except Exception:
                # Silent failure - metrics collector should not crash
                pass

            # Wait for next collection
            time.sleep(interval_seconds)

    # Start daemon thread
    collector_thread = threading.Thread(
        target=collect_metrics,
        name="celery_metrics_collector",
        daemon=True,
    )
    collector_thread.start()

    return collector_thread
