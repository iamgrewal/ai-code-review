"""
Models package for CortexReview Platform.

Exports all Pydantic models for API contracts and data validation.
"""

# Platform models (normalized webhook payloads, enums)
# Feedback models (RLHF learning loop)
from .feedback import (
    FeedbackRecord,
    FeedbackRequest,
    LearnedConstraint,
)

# Indexing models (repository indexing)
from .indexing import (
    IndexDepth,
    IndexingProgress,
    IndexingRequest,
)

# MCP models (IDE integration)
from .mcp import (
    MCP_TOOLS,
    MCPManifest,
    MCPTool,
    MCPToolRequest,
    MCPToolResponse,
)
from .platform import FeedbackAction, PRMetadata, ReviewStatus, Severity

# Review models (review responses, comments, config)
from .review import (
    ReviewComment,
    ReviewConfig,
    ReviewResponse,
    ReviewStats,
    ReviewTask,
)

__all__ = [
    # Platform
    "Severity",
    "ReviewStatus",
    "FeedbackAction",
    "PRMetadata",
    # Review
    "ReviewConfig",
    "ReviewComment",
    "ReviewStats",
    "ReviewResponse",
    "ReviewTask",
    # Feedback
    "FeedbackRequest",
    "FeedbackRecord",
    "LearnedConstraint",
    # Indexing
    "IndexDepth",
    "IndexingRequest",
    "IndexingProgress",
    # MCP
    "MCPTool",
    "MCPManifest",
    "MCPToolRequest",
    "MCPToolResponse",
    "MCP_TOOLS",
]
