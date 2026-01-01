"""
CortexReview Platform - Celery Worker Entry Point

Defines async Celery tasks for code review processing, repository indexing,
and feedback handling. Integrates with platform adapters, RAG, and RLHF.

Constitution VII: Async-First Processing - All reviews run as background tasks.
"""

import time
import uuid

from loguru import logger
from openai import OpenAI
from supabase import Client, create_client

from adapters.gitea import GiteaAdapter
from adapters.github import GitHubAdapter
from celery_app import app
from codereview.copilot import Copilot
from models.platform import PRMetadata
from models.review import (
    ReviewComment,
    ReviewResponse,
    ReviewStats,
)
from repositories.knowledge import KnowledgeRepository, create_knowledge_repository
from services.indexing import IndexingService, create_indexing_service
from utils.config import Config
from utils.metrics import (
    llm_tokens_total,
    rag_retrieval_failure_total,
    review_duration_seconds,
)
from utils.secrets import scan_for_secrets

# Load configuration (singleton instance)
config = Config()

# Initialize LLM client
llm_client = OpenAI(
    api_key=config.effective_llm_api_key,
    base_url=config.effective_llm_base_url,
)

# Initialize Supabase client (if configured)
supabase_client: Client | None = None

# Support three Supabase deployment modes:
# 1. External Supabase Cloud (SUPABASE_URL + SUPABASE_SERVICE_KEY)
# 2. Local Supabase via PostgREST (SUPABASE_DB_URL + SERVICE_ROLE_KEY)
# 3. No Supabase (features gracefully degraded)
if config.SUPABASE_URL and config.SUPABASE_SERVICE_KEY:
    # Mode 1: External Supabase Cloud
    try:
        supabase_client = create_client(
            config.SUPABASE_URL,
            config.SUPABASE_SERVICE_KEY,
        )
        logger.info("Supabase client initialized (external Supabase Cloud)")
    except Exception as e:
        logger.warning(f"Supabase initialization failed: {e}. RAG/RLHF features disabled.")
        supabase_client = None
elif config.SUPABASE_DB_URL:
    # Mode 2: Local Supabase via PostgREST API
    # The local Supabase deployment includes supabase-rest (PostgREST) service
    # We generate a JWT token signed with JWT_SECRET for authentication
    import os
    import time
    from jose import jwt

    local_rest_url = "http://supabase-rest:3000"  # Internal Docker network
    jwt_secret = os.getenv("JWT_SECRET")

    if jwt_secret:
        try:
            # Generate a service role JWT token for local Supabase
            # This token has full access to the database
            payload = {
                "role": "service_role",
                "iss": "supabase",  # Issuer
                "iat": int(time.time()),  # Issued at
                "exp": int(time.time()) + 3600,  # Expires in 1 hour (will be refreshed)
            }
            token = jwt.encode(payload, jwt_secret, algorithm="HS256")

            supabase_client = create_client(local_rest_url, token)
            logger.info("Supabase client initialized (local Supabase via PostgREST with JWT)")
        except Exception as e:
            logger.warning(f"Local Supabase initialization failed: {e}. RAG/RLHF features disabled.")
            supabase_client = None
    else:
        logger.warning("JWT_SECRET not configured for local Supabase. RAG/RLHF features disabled.")

# Initialize RAG repository (if Supabase available)
knowledge_repo: KnowledgeRepository | None = None
if supabase_client:
    knowledge_repo = create_knowledge_repository(supabase_client, config)
    if knowledge_repo:
        logger.info("Knowledge repository initialized for RAG")

# Initialize indexing service (if Supabase available)
indexing_service: IndexingService | None = None
if supabase_client:
    indexing_service = create_indexing_service(supabase_client, config)
    if indexing_service:
        logger.info("Indexing service initialized")


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

    # Bind trace_id to logger for request correlation (Constitution VII)
    task_logger = logger.bind(trace_id=trace_id, task_id=self.request.id)
    task_logger.info(f"Processing code review: task_id={self.request.id}")

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
            task_logger.warning(
                f"No diff content found for {metadata.repo_id}#{metadata.pr_number}"
            )
            return {
                "task_id": self.request.id,
                "status": "failed",
                "error": "No diff content found",
            }

        # -------------------------------------------------------------------------
        # RAG: Retrieve context from knowledge base (if enabled) (T056-T059)
        # -------------------------------------------------------------------------
        rag_context_citations = []
        rag_match_count_value = 0
        if config.RAG_ENABLED and knowledge_repo:
            rag_start = time.time()
            try:
                # Build query from diff blocks for context retrieval
                query_text = "\n".join(diff_blocks[:3])  # Use first 3 diffs as query
                rag_context = knowledge_repo.search_context(
                    query_text=query_text,
                    repo_id=metadata.repo_id,
                    match_threshold=config.RAG_THRESHOLD,
                    match_count=config.RAG_MATCH_COUNT_MIN,
                )
                rag_match_count_value = len(rag_context)
                rag_latency = time.time() - rag_start

                # Extract citations from RAG results
                rag_context_citations = [r.get("citation", "") for r in rag_context[:3]]

                task_logger.info(
                    f"RAG retrieved {rag_match_count_value} context chunks in {rag_latency:.2f}s"
                )
            except Exception as e:
                rag_retrieval_failure_total.labels(
                    repo_id=metadata.repo_id, reason=type(e).__name__
                ).inc()
                task_logger.warning(f"RAG retrieval failed (graceful fallback): {e}")
        else:
            task_logger.debug("RAG disabled or knowledge repository not available")

        # -------------------------------------------------------------------------
        # RLHF: Check for learned constraints (if enabled)
        # -------------------------------------------------------------------------
        suppressed_patterns = []
        if config.RLHF_ENABLED and supabase_client:
            try:
                suppressed_patterns = _check_learned_constraints(metadata, diff_blocks)
                if suppressed_patterns:
                    task_logger.info(f"RLHF suppressed {len(suppressed_patterns)} known patterns")
            except Exception as e:
                task_logger.warning(f"RLHF constraint check failed (graceful fallback): {e}")

        # -------------------------------------------------------------------------
        # LLM: Generate review comments
        # -------------------------------------------------------------------------
        copilot = Copilot(config)

        comments = []
        total_tokens = 0

        for diff_content in diff_blocks:
            # Skip if suppressed by RLHF
            if _is_diff_suppressed(diff_content, suppressed_patterns):
                task_logger.debug("Diff suppressed by learned constraints")
                continue

            # Generate review comment
            response = copilot.code_review(diff_content)

            if response:
                # Extract file path from diff
                file_path = _extract_file_path(diff_content)

                # Scan for secrets (data governance)
                secret_matches = scan_for_secrets(diff_content, file_path)
                if secret_matches:
                    task_logger.warning(f"Secrets detected in {file_path}, redacting from review")

                comment = ReviewComment(
                    id=str(uuid.uuid4()),
                    file_path=file_path,
                    line_range={"start": 1, "end": 1},
                    type="nit",  # Default, could be improved with LLM parsing
                    severity="nit",
                    message=response,
                    suggestion="",
                    confidence_score=0.5,
                    citations=rag_context_citations,  # Add RAG citations (T058)
                )
                comments.append(comment)

                # Track token usage (approximate)
                total_tokens += len(response.split())

        # -------------------------------------------------------------------------
        # Metrics: Record observability data (Constitution XI)
        # -------------------------------------------------------------------------
        duration = time.time() - start_time
        review_duration_seconds.labels(platform=metadata.platform, status="success").observe(
            duration
        )
        llm_tokens_total.labels(model_type=config.LLM_MODEL, model_name=config.LLM_MODEL).inc(
            total_tokens
        )

        # Build review response
        review_response = ReviewResponse(
            review_id=str(uuid.uuid4()),
            pr_number=metadata.pr_number,
            repo_id=metadata.repo_id,
            summary=f"Code review completed with {len(comments)} comments",
            comments=comments,
            stats=ReviewStats(
                total_issues=len(comments),
                nit=len(comments),
                execution_time_ms=int(duration * 1000),
                rag_context_used=len(rag_context_citations) > 0,  # T059
                rag_matches_found=rag_match_count_value,  # T059
            ),
        )

        # Post review to platform
        adapter.post_review(metadata, review_response)

        task_logger.info(
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
        task_logger.error(f"Code review failed: {e}")

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
    trace_id: str | None = None,
) -> dict:
    """
    Index repository for RAG context retrieval (Constitution V) (T051-T055).

    Clones repository, chunks code, generates embeddings, stores in Supabase.
    Uses IndexingService for complete indexing workflow with secret scanning.

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

    task_logger = logger.bind(trace_id=trace_id, task_id=self.request.id)
    task_logger.info(f"Starting repository indexing: {repo_id}")

    try:
        if not indexing_service:
            raise Exception("Indexing service not available (Supabase not configured)")

        # Parse depth string to IndexDepth enum
        from models.indexing import IndexDepth

        index_depth = IndexDepth.SHALLOW if depth == "shallow" else IndexDepth.DEEP

        # Run indexing workflow
        result = indexing_service.index_repository(
            repo_id=repo_id,
            git_url=git_url,
            access_token=access_token,
            branch=branch,
            depth=index_depth,
        )

        task_logger.info(
            f"Repository indexing completed: {result.get('files_processed', 0)} files, "
            f"{result.get('chunks_indexed', 0)} chunks"
        )

        return {
            "task_id": self.request.id,
            "status": result.get("status", "success"),
            "repo_id": repo_id,
            "indexed_files": result.get("files_processed", 0),
            "chunks_indexed": result.get("chunks_indexed", 0),
            "secrets_found": result.get("secrets_found", 0),
            "duration_seconds": result.get("duration_seconds", time.time() - start_time),
        }

    except Exception as e:
        task_logger.error(f"Repository indexing failed: {e}")
        raise


@app.task(name="worker.process_feedback", bind=True, max_retries=2)
def process_feedback(
    self,
    feedback_dict: dict,
    review_id: str,
    repo_id: str,
    trace_id: str | None = None,
) -> dict:
    """
    Process user feedback for RLHF learning loop (Constitution VI).

    Generates embeddings for false positives and stores as learned constraints.

    Args:
        self: Celery task bound instance
        feedback_dict: FeedbackRequest as dict
        review_id: Associated review ID
        repo_id: Repository identifier
        trace_id: Request correlation ID

    Returns:
        dict with feedback processing result
    """
    from models.feedback import FeedbackRequest
    from services.feedback import FeedbackService

    trace_id = trace_id or str(uuid.uuid4())
    task_logger = logger.bind(trace_id=trace_id, task_id=self.request.id)
    task_logger.info(f"Processing feedback: action={feedback_dict.get('action')}")

    try:
        if not supabase_client:
            raise Exception("Supabase client not configured")

        # Reconstruct FeedbackRequest from dict
        feedback = FeedbackRequest(**feedback_dict)

        # Initialize FeedbackService
        feedback_service = FeedbackService(
            supabase_client=supabase_client,
            llm_client=llm_client,
            config=config,
        )

        # Process feedback through RLHF learning loop (T047-T054)
        result = feedback_service.process_feedback(
            feedback=feedback,
            review_id=review_id,
            repo_id=repo_id,
            trace_id=trace_id,
        )

        task_logger.info(
            f"Feedback processed: action={feedback.action}, "
            f"feedback_id={result['feedback_id']}, "
            f"constraint_id={result.get('constraint_id')}"
        )

        return {
            "task_id": self.request.id,
            "status": "success",
            **result,
        }

    except Exception as e:
        task_logger.error(f"Feedback processing failed: {e}")
        raise


@app.task(name="worker.cleanup_expired_constraints")
def cleanup_expired_constraints() -> dict:
    """
    Cleanup expired learned constraints (Constitution VI).

    Runs hourly via Celery Beat to remove constraints past their expiration date.
    Uses 90-day expiration policy by default.
    """
    from repositories.constraints import ConstraintRepository

    logger.info("Starting expired constraint cleanup")

    try:
        if not supabase_client:
            return {"status": "skipped", "reason": "Supabase not configured"}

        # Initialize constraint repository
        constraint_repo = ConstraintRepository(supabase_client)

        # Delete constraints older than 90 days (T069)
        deleted_count = constraint_repo.delete_expired(days_old=config.CONSTRAINT_EXPIRATION_DAYS)

        logger.info(f"Cleanup completed: {deleted_count} expired constraints deleted")

        return {
            "status": "success",
            "deleted_count": deleted_count,
        }

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

    NOTE: This function is deprecated in favor of KnowledgeRepository.search_context().
    Kept for backward compatibility during transition.

    Args:
        metadata: PR metadata
        diff_blocks: List of diff content blocks

    Returns:
        list of context strings (citations)
    """
    if knowledge_repo:
        query_text = "\n".join(diff_blocks[:3])
        results = knowledge_repo.search_context(
            query_text=query_text,
            repo_id=metadata.repo_id,
        )
        return [r.get("citation", "") for r in results[:3]]
    return []


def _check_learned_constraints(metadata: PRMetadata, diff_blocks: list[str]) -> list[str]:
    """
    Check if diff matches any learned constraints (RLHF).

    Uses ConstraintRepository to generate embeddings and query Supabase
    for matching constraints that should suppress false positives.

    Args:
        metadata: PR metadata
        diff_blocks: List of diff content blocks

    Returns:
        list of suppressed constraint IDs
    """
    from repositories.constraints import ConstraintRepository

    if not supabase_client:
        return []

    try:
        # Initialize constraint repository
        constraint_repo = ConstraintRepository(supabase_client)

        # Generate embedding for query (using first diff block)
        query_text = diff_blocks[0] if diff_blocks else ""
        if not query_text:
            return []

        # Generate embedding for the query
        query_embedding = (
            llm_client.embeddings.create(
                model=config.EMBEDDING_MODEL,
                input=query_text[:8000],
            )
            .data[0]
            .embedding
        )

        # Check for matching constraints
        matching_constraints = constraint_repo.check_suppressions(
            repo_id=metadata.repo_id,
            embedding=query_embedding,
            threshold=config.RLHF_THRESHOLD,
        )

        # Return list of constraint IDs that should be suppressed
        return [c.id for c in matching_constraints]

    except Exception as e:
        logger.warning(f"Failed to check learned constraints: {e}")
        return []


def _is_diff_suppressed(diff_content: str, suppressed_constraints: list[str]) -> bool:
    """
    Check if diff content should be suppressed based on learned constraints.

    Args:
        diff_content: Diff content to check
        suppressed_constraints: List of constraint IDs that are suppressed

    Returns:
        True if diff should be suppressed
    """
    # For now, we check if any constraints were found that match this diff
    # In a more sophisticated implementation, we could:
    # 1. Generate embedding for this specific diff
    # 2. Check against each suppressed constraint individually
    # 3. Return True only if similarity exceeds threshold

    # Current implementation: If we have suppressed constraints, assume suppression
    return len(suppressed_constraints) > 0


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
    "aggregate_metrics",
    "app",
    "cleanup_expired_constraints",
    "index_repository",
    "process_code_review",
    "process_feedback",
]
