"""
Feedback models for CortexReview.

Defines data structures for RLHF (Reinforcement Learning from Human Feedback)
learning loop functionality.
"""

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


class FeedbackRequest(BaseModel):
    """
    Request to submit feedback on a review comment.

    User feedback drives the learning loop - rejected comments create
    learned constraints that suppress similar false positives in future reviews.
    """

    comment_id: str = Field(..., description="Review comment ID being feedback upon")
    action: Literal["accepted", "rejected", "modified"] = Field(
        ..., description="Action taken on the comment"
    )
    reason: Literal["false_positive", "logic_error", "style_preference", "hallucination"] = Field(
        ..., description="Reason category for feedback"
    )
    developer_comment: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Free-form explanation (1-1000 characters)",
    )
    final_code_snapshot: str = Field(..., description="Final committed code snippet")
    user_id: Optional[str] = Field(None, description="User identifier for audit trail")
    trace_id: Optional[str] = Field(None, description="Correlation ID from original review")


class FeedbackRecord(BaseModel):
    """
    Audit log entry tracking user feedback for compliance.

    All feedback submissions are logged to support debugging,
    compliance review, and learning loop analysis.
    """

    id: str = Field(..., description="Unique feedback record identifier")
    review_id: str = Field(..., description="Associated review ID")
    comment_id: str = Field(..., description="Review comment ID")
    user_id: str = Field(..., description="User who submitted feedback")
    action: Literal["accepted", "rejected", "modified"] = Field(..., description="Action taken")
    reason: str = Field(..., description="User-provided reason")
    developer_comment: str = Field(..., description="Full developer explanation")
    final_code_snapshot: str = Field(..., description="Final code after user changes")
    trace_id: str = Field(..., description="Correlation ID for distributed tracing")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Feedback submission timestamp")


class LearnedConstraint(BaseModel):
    """
    Negative example from rejected feedback with embedding.

    When users reject review comments, the pattern is stored as a
    learned constraint with an embedding. Similar patterns in future
    reviews are checked against these constraints to suppress false positives.
    """

    id: str = Field(..., description="Unique constraint identifier")
    repo_id: str = Field(..., description="Repository identifier (owner/repo)")
    violation_reason: str = Field(..., description="Original violation reason from review")
    code_pattern: str = Field(..., description="Code pattern that was flagged")
    user_reason: str = Field(..., description="User's explanation for rejection")
    embedding: list[float] = Field(..., description="Vector embedding (1536-dimensional)")
    confidence_score: float = Field(default=0.5, ge=0.0, le=1.0, description="Constraint confidence (0.5-1.0)")
    expires_at: Optional[datetime] = Field(None, description="Auto-expiration timestamp (90-day default)")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Constraint creation timestamp")
    version: int = Field(default=1, ge=1, description="Constraint version for updates")
