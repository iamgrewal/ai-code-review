"""
Prometheus metrics for CortexReview platform observability.

Defines all metrics emitted for monitoring system performance,
costs, and operational health per Constitution XI (Observability).
"""

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
            with llm_request_duration_seconds.labels(model_type=model_type, model_name=model_name).time():
                result = func(*args, **kwargs)
                # Extract token count if available in result
                if hasattr(result, "usage"):
                    tokens = result.usage.total_tokens
                    llm_tokens_total.labels(model_type=model_type, model_name=model_name).inc(tokens)
                return result
        return wrapper
    return decorator
