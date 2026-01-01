"""
Platform models for CortexReview.

Defines normalized webhook payload abstraction for multi-platform support.
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Severity(str, Enum):
    """Severity levels for review comments."""

    NIT = "nit"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReviewStatus(str, Enum):
    """Status of async review tasks."""

    QUEUED = "queued"  # In Redis queue
    PROCESSING = "processing"  # Worker executing
    COMPLETED = "completed"  # Success with result
    FAILED = "failed"  # Permanent failure


class FeedbackAction(str, Enum):
    """User feedback actions on review comments."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MODIFIED = "modified"


class PRMetadata(BaseModel):
    """
    Normalized webhook payload abstracting platform-specific differences.

    This model provides a unified interface for GitHub and Gitea webhooks,
    enabling platform-agnostic business logic in the service layer.
    """

    model_config = ConfigDict(frozen=True)  # Immutable after creation

    repo_id: str = Field(..., description="Repository owner/name")
    pr_number: int = Field(..., ge=1, description="Pull request number")
    base_sha: str = Field(..., min_length=40, max_length=40, description="Base commit SHA")
    head_sha: str = Field(..., min_length=40, max_length=40, description="Head commit SHA")
    author: str | None = Field(None, description="Commit author username")
    platform: Literal["github", "gitea"] = Field(..., description="Source platform identifier")
    title: str | None = Field(None, description="PR/commit title")
    source: Literal["webhook", "cli", "mcp"] = Field(
        default="webhook", description="Request source"
    )
    callback_url: str | None = Field(None, description="Optional webhook callback URL")
