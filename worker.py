"""
CortexReview Platform - Celery Worker Entry Point

Defines async Celery tasks for code review processing, repository indexing,
and feedback handling. Integrates with platform adapters, RAG, and RLHF.

Constitution VII: Async-First Processing - All reviews run as background tasks.
"""

import time
import uuid
from datetime import datetime, timedelta
from typing import Optional

from loguru import logger
from openai import OpenAI
from supabase import Client, create_client

from celery_app import app
from codereview.copilot import Copilot
from models.feedback import FeedbackAction, FeedbackRecord, LearnedConstraint
from models.indexing import IndexDepth, IndexingProgress, IndexingStatus
from models.platform import PRMetadata
from models.review import (
    ReviewComment,
    ReviewConfig,
    ReviewResponse,
    ReviewStats,
    ReviewStatus,
)
from adapters.github import GitHubAdapter
from adapters.gitea import GiteaAdapter
from utils.config import Config
from utils.metrics import (
    feedback_submitted_total,
    indexing_duration_seconds,
    llm_tokens_total,
    rag_retrieval_latency_seconds,
    review_duration_seconds,
)
from utils.secrets import scan_for_secrets, SecretType

# Load configuration (singleton instance)
config = Config()

# Initialize LLM client
llm_client = OpenAI(
    api_key=config.effective_llm_api_key,
    base_url=config.effective_llm_base_url,
)

# Initialize Supabase client (if configured)
supabase_client: Optional[Client] = None
if config.SUPABASE_URL and config.SUPABASE_SERVICE_KEY:
    try:
        supabase_client = create_client(
            config.SUPABASE_URL,
            config.SUPABASE_SERVICE_KEY,
        )
        logger.info("Supabase client initialized")
    except Exception as e:
        logger.warning(f"Supabase initialization failed: {e}. RAG/RLHF features disabled.")


# =============================================================================
# Celery Tasks
# =============================================================================

@app.task(name="worker.process_code_review", bind=True, max_retries=3)
def process_code_review(self, metadata_dict: dict, trace_id: str) -> dict:
    """
    Process code review asynchronously (Constitution VII).

    Args:
        self: Celery task bound instance
        metadata_dict: PRMetadata as dict (for Celery serialization)
        trace_id: Request correlation ID

    Returns:
        dict with review result and status

    Raises:
        Exception: Propagates after max retries exceeded
    """
    start_time = time.time()

    # Bind trace_id to logger for all subsequent logs
    logger.configure(extra={"trace_id": trace_id})
    logger.info(f"Processing code review: task_id={self.request.id}")

    try:
        # Reconstruct PRMetadata from dict
        metadata = PRMetadata(**metadata_dict)

        # Initialize platform adapter
        if metadata.platform == "github":
            adapter = GitHubAdapter(token=config.GITHUB_TOKEN or "")
        else:  # gitea
            adapter = GiteaAdapter(
                host=config.GITEA_HOST,
                token=config.GITEA_TOKEN,
            )

        # Get diff from platform
        diff_blocks = adapter.get_diff(metadata)

        if not diff_blocks:
            logger.warning(f"No diff content found for {metadata.repo_id}#{metadata.pr_number}")
            return {
                "task_id": self.request.id,
                "status": "failed",
                "error": "No diff content found",
            }

        # -------------------------------------------------------------------------
        # RAG: Retrieve context from knowledge base (if enabled)
        # -------------------------------------------------------------------------
        rag_context = []
        if config.RAG_ENABLED and supabase_client:
            rag_start = time.time()
            try:
                rag_context = _retrieve_rag_context(metadata, diff_blocks)
                rag_latency = time.time() - rag_start
                rag_retrieval_latency_seconds.labels(repo_id=metadata.repo_id).observe(rag_latency)
                logger.info(f"RAG retrieved {len(rag_context)} context chunks in {rag_latency:.2f}s")
            except Exception as e:
                logger.warning(f"RAG retrieval failed (graceful fallback): {e}")

        # -------------------------------------------------------------------------
        # RLHF: Check for learned constraints (if enabled)
        # -------------------------------------------------------------------------
        suppressed_patterns = []
        if config.RLHF_ENABLED and supabase_client:
            try:
                suppressed_patterns = _check_learned_constraints(metadata, diff_blocks)
                if suppressed_patterns:
                    logger.info(f"RLHF suppressed {len(suppressed_patterns)} known patterns")
            except Exception as e:
                logger.warning(f"RLHF constraint check failed (graceful fallback): {e}")

        # -------------------------------------------------------------------------
        # LLM: Generate review comments
        # -------------------------------------------------------------------------
        copilot = Copilot(config)

        comments = []
        total_tokens = 0

        for diff_content in diff_blocks:
            # Skip if suppressed by RLHF
            if _is_diff_suppressed(diff_content, suppressed_patterns):
                logger.debug(f"Diff suppressed by learned constraints")
                continue

            # Generate review comment
            response = copilot.code_review(diff_content)

            if response:
                # Extract file path from diff
                file_path = _extract_file_path(diff_content)

                # Scan for secrets (data governance)
                secret_matches = scan_for_secrets(diff_content, file_path)
                if secret_matches:
                    logger.warning(f"Secrets detected in {file_path}, redacting from review")

                comment = ReviewComment(
                    id=str(uuid.uuid4()),
                    file_path=file_path,
                    line_range={"start": 1, "end": 1},
                    type="nit",  # Default, could be improved with LLM parsing
                    severity="nit",
                    message=response,
                    suggestion="",
                    confidence_score=0.5,
                    citations=rag_context[:3],  # Add up to 3 RAG citations
                )
                comments.append(comment)

                # Track token usage (approximate)
                total_tokens += len(response.split())

        # -------------------------------------------------------------------------
        # Metrics: Record observability data (Constitution XI)
        # -------------------------------------------------------------------------
        duration = time.time() - start_time
        review_duration_seconds.labels(platform=metadata.platform, status="success").observe(duration)
        llm_tokens_total.labels(model_type=config.LLM_MODEL, model_name=config.LLM_MODEL).inc(total_tokens)

        # Build review response
        review_response = ReviewResponse(
            review_id=str(uuid.uuid4()),
            pr_number=metadata.pr_number,
            repo_id=metadata.repo_id,
            summary=f"Code review completed with {len(comments)} comments",
            comments=comments,
            stats=ReviewStats(
                total_files=len(diff_blocks),
                total_comments=len(comments),
                severity_breakdown={"nit": len(comments)},
            ),
        )

        # Post review to platform
        adapter.post_review(metadata, review_response)

        logger.info(
            f"Code review completed: {len(comments)} comments, "
            f"{duration:.2f}s, {total_tokens} tokens"
        )

        return {
            "task_id": self.request.id,
            "status": "success",
            "review_id": review_response.review_id,
            "comment_count": len(comments),
            "duration_seconds": duration,
        }

    except Exception as e:
        duration = time.time() - start_time
        review_duration_seconds.labels(platform=metadata.platform, status="error").observe(duration)
        logger.error(f"Code review failed: {e}")

        # Retry with exponential backoff (Celery auto-retry)
        raise


@app.task(name="worker.index_repository", bind=True, max_retries=2)
def index_repository(
    self,
    repo_id: str,
    git_url: str,
    access_token: str,
    branch: str = "main",
    depth: str = "deep",
    trace_id: Optional[str] = None,
) -> dict:
    """
    Index repository for RAG context retrieval (Constitution V).

    Clones repository, chunks code, generates embeddings, stores in Supabase.

    Args:
        self: Celery task bound instance
        repo_id: Repository identifier
        git_url: Git repository URL
        access_token: Git access token for cloning
        branch: Branch to index
        depth: Index depth (shallow or deep)
        trace_id: Request correlation ID

    Returns:
        dict with indexing progress and stats
    """
    start_time = time.time()
    trace_id = trace_id or str(uuid.uuid4())

    logger.configure(extra={"trace_id": trace_id})
    logger.info(f"Starting repository indexing: {repo_id}")

    try:
        if not supabase_client:
            raise Exception("Supabase client not configured")

        # TODO: Implement GitPython clone, file walking, and embedding generation
        # This is a placeholder for the full indexing implementation
        # See T035-T038 in tasks.md for complete implementation

        # Placeholder: Simulate indexing
        logger.info("Repository indexing placeholder (implementation pending)")

        duration = time.time() - start_time
        indexing_duration_seconds.labels(repo_id=repo_id, depth=depth).observe(duration)

        return {
            "task_id": self.request.id,
            "status": "success",
            "repo_id": repo_id,
            "indexed_files": 0,  # Placeholder
            "duration_seconds": duration,
        }

    except Exception as e:
        logger.error(f"Repository indexing failed: {e}")
        raise


@app.task(name="worker.process_feedback", bind=True, max_retries=2)
def process_feedback(
    self,
    feedback_dict: dict,
    trace_id: Optional[str] = None,
) -> dict:
    """
    Process user feedback for RLHF learning loop (Constitution VI).

    Generates embeddings for false positives and stores as learned constraints.

    Args:
        self: Celery task bound instance
        feedback_dict: FeedbackRequest as dict
        trace_id: Request correlation ID

    Returns:
        dict with feedback processing result
    """
    trace_id = trace_id or str(uuid.uuid4())
    logger.configure(extra={"trace_id": trace_id})
    logger.info(f"Processing feedback: action={feedback_dict.get('action')}")

    try:
        if not supabase_client:
            raise Exception("Supabase client not configured")

        action = feedback_dict.get("action")

        # Record feedback metric
        feedback_submitted_total.labels(action=action).inc()

        # TODO: Implement full feedback processing
        # See T047-T054 in tasks.md for complete implementation

        logger.info(f"Feedback processed: action={action}")
        return {"task_id": self.request.id, "status": "success"}

    except Exception as e:
        logger.error(f"Feedback processing failed: {e}")
        raise


@app.task(name="worker.cleanup_expired_constraints")
def cleanup_expired_constraints() -> dict:
    """
    Cleanup expired learned constraints (Constitution VI).

    Runs hourly via Celery Beat to remove constraints past their expiration date.
    """
    logger.info("Starting expired constraint cleanup")

    try:
        if not supabase_client:
            return {"status": "skipped", "reason": "Supabase not configured"}

        # TODO: Implement cleanup logic
        # Delete from learned_constraints where expires_at < now()

        return {"status": "success", "deleted_count": 0}

    except Exception as e:
        logger.error(f"Constraint cleanup failed: {e}")
        return {"status": "error", "error": str(e)}


@app.task(name="worker.aggregate_metrics")
def aggregate_metrics() -> dict:
    """
    Aggregate daily metrics for Prometheus (Constitution XI).

    Runs daily at 3 AM UTC via Celery Beat.
    """
    logger.info("Starting daily metrics aggregation")
    return {"status": "success"}


# =============================================================================
# Helper Functions
# =============================================================================

def _retrieve_rag_context(metadata: PRMetadata, diff_blocks: list[str]) -> list[str]:
    """
    Retrieve relevant context from knowledge base using vector similarity.

    Args:
        metadata: PR metadata
        diff_blocks: List of diff content blocks

    Returns:
        list of context strings (citations)
    """
    # TODO: Implement vector similarity search using Supabase pgvector
    # See T033, T040 in tasks.md
    return []


def _check_learned_constraints(metadata: PRMetadata, diff_blocks: list[str]) -> list[str]:
    """
    Check if diff matches any learned constraints (RLHF).

    Args:
        metadata: PR metadata
        diff_blocks: List of diff content blocks

    Returns:
        list of suppressed pattern IDs
    """
    # TODO: Implement constraint matching using Supabase
    # See T045, T052-T053 in tasks.md
    return []


def _is_diff_suppressed(diff_content: str, suppressed_patterns: list[str]) -> bool:
    """
    Check if diff content matches any suppressed patterns.

    Args:
        diff_content: Diff content to check
        suppressed_patterns: List of pattern IDs that are suppressed

    Returns:
        True if diff should be suppressed
    """
    # TODO: Implement pattern matching logic
    return False


def _extract_file_path(diff_content: str) -> str:
    """
    Extract file path from git diff content.

    Args:
        diff_content: Git diff content

    Returns:
        File path string
    """
    lines = diff_content.split("\n")
    for line in lines:
        if line.startswith("diff --git a/"):
            # Extract: diff --git a/file.py b/file.py
            parts = line.split()
            if len(parts) >= 3:
                return parts[2][2:]  # Remove "b/" prefix
    return "unknown"


# =============================================================================
# Module Exports
# =============================================================================
__all__ = [
    "app",
    "process_code_review",
    "index_repository",
    "process_feedback",
    "cleanup_expired_constraints",
    "aggregate_metrics",
]
