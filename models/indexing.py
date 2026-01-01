"""
Indexing models for CortexReview.

Defines data structures for repository indexing operations.
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class IndexDepth(str, Enum):
    """Indexing depth modes."""

    SHALLOW = "shallow"  # Index structure only (file paths, imports, function signatures)
    DEEP = "deep"  # Index full code content (default)


class IndexingRequest(BaseModel):
    """
    Request to trigger repository indexing for RAG knowledge base.

    Indexing clones the repository, walks the directory tree, chunks
    large files, generates embeddings, and stores them in Supabase.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "git_url": "https://github.com/owner/repo.git",
                    "access_token": "YOUR_GITHUB_TOKEN_HERE",
                    "branch": "main",
                    "index_depth": "deep",
                }
            ]
        }
    )

    git_url: str = Field(..., description="Git repository HTTPS URL")
    access_token: str = Field(..., min_length=1, description="Personal access token for cloning")
    branch: str = Field(default="main", description="Branch to index")
    index_depth: IndexDepth = Field(default=IndexDepth.DEEP, description="Indexing mode")


class IndexingProgress(BaseModel):
    """Progress tracking for long-running indexing tasks."""

    stage: Literal[
        "queued",
        "cloning",
        "scanning",
        "chunking",
        "secret_scanning",
        "generating_embeddings",
        "storing",
        "completed",
        "failed",
    ] = Field(..., description="Current processing stage")
    files_processed: int = Field(default=0, ge=0, description="Number of files processed")
    total_files: int = Field(default=0, ge=0, description="Estimated total files")
    chunks_indexed: int = Field(default=0, ge=0, description="Number of chunks embedded")
    percentage: float = Field(default=0.0, ge=0.0, le=100.0, description="Progress percentage")
    error_message: str | None = Field(None, description="Error message if failed")
