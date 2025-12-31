"""
Review models for CortexReview.

Defines data structures for async task tracking, review configuration,
and review responses with RAG citations.
"""

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field

from .platform import PRMetadata, ReviewStatus, Severity


class ReviewConfig(BaseModel):
    """
    Configuration for code review execution.

    Controls RAG context retrieval, RLHF constraint application,
    and review generation parameters.
    """

    use_rag_context: bool = Field(default=True, description="Enable RAG context retrieval")
    apply_learned_suppressions: bool = Field(default=True, description="Apply RLHF learned constraints")
    severity_threshold: Severity = Field(default=Severity.LOW, description="Minimum severity to include")
    include_auto_fix_patches: bool = Field(default=False, description="Generate git apply patches for fixes")
    personas: list[str] = Field(default_factory=list, description="AI personas to apply (e.g., security_expert)")
    max_context_matches: int = Field(default=10, ge=3, le=10, description="Maximum RAG context matches")


class ReviewComment(BaseModel):
    """
    Individual review comment with optional RAG citations.

    Comments can include citations from repository history when
    RAG context is used, enabling developers to understand the
    reasoning behind suggestions.
    """

    id: str = Field(..., description="Unique comment identifier")
    file_path: str = Field(..., description="Path to the file being reviewed")
    line_range: dict[str, int] = Field(..., description="Line range {start, end}")
    type: Literal["security", "bug", "performance", "style", "nit"] = Field(
        ..., description="Type of issue detected"
    )
    severity: Severity = Field(..., description="Severity level")
    message: str = Field(..., description="Review comment message")
    suggestion: str = Field(default="", description="Suggested fix")
    confidence_score: float = Field(default=0.5, ge=0.0, le=1.0, description="AI confidence in this comment")
    fix_patch: Optional[str] = Field(None, description="Optional git apply patch for suggested fix")
    citations: list[str] = Field(default_factory=list, description="RAG citations (e.g., 'See PR #42')")


class ReviewStats(BaseModel):
    """Statistics about the review execution."""

    total_issues: int = Field(default=0, ge=0, description="Total number of issues found")
    critical: int = Field(default=0, ge=0, description="Count of critical issues")
    high: int = Field(default=0, ge=0, description="Count of high issues")
    medium: int = Field(default=0, ge=0, description="Count of medium issues")
    low: int = Field(default=0, ge=0, description="Count of low issues")
    nit: int = Field(default=0, ge=0, description="Count of nit issues")
    execution_time_ms: int = Field(..., ge=0, description="Execution time in milliseconds")
    rag_context_used: bool = Field(default=False, description="Whether RAG context was retrieved")
    rag_matches_found: int = Field(default=0, ge=0, description="Number of RAG context matches")
    rlhf_constraints_applied: int = Field(default=0, ge=0, description="Number of RLHF constraints applied")
    tokens_used: int = Field(default=0, ge=0, description="LLM tokens consumed")


class ReviewResponse(BaseModel):
    """
    Complete review response from the LLM.

    Contains all review comments, summary statistics, and metadata
    about the review execution.
    """

    review_id: str = Field(..., description="Unique review identifier")
    summary: str = Field(..., description="Human-readable summary of findings")
    comments: list[ReviewComment] = Field(default_factory=list, description="Review comments")
    stats: ReviewStats = Field(..., description="Review execution statistics")


class ReviewTask(BaseModel):
    """
    Async task representation for Celery job tracking.

    This model represents the state of a code review task throughout
    its lifecycle: QUEUED -> PROCESSING -> COMPLETED/FAILED.
    """

    task_id: str = Field(..., description="Celery task UUID")
    status: ReviewStatus = Field(default=ReviewStatus.QUEUED, description="Current task status")
    trace_id: str = Field(..., description="Correlation ID for distributed tracing")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Task creation timestamp")
    started_at: Optional[datetime] = Field(None, description="Worker start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Task completion timestamp")
    metadata: PRMetadata = Field(..., description="Normalized PR metadata")
    config: ReviewConfig = Field(..., description="Review configuration")
    result: Optional[ReviewResponse] = Field(None, description="Final review result")
    error: Optional[str] = Field(None, description="Error message if failed")
    retry_count: int = Field(default=0, ge=0, le=3, description="Number of retry attempts")
