"""
Test fixtures package for CortexReview Platform tests.

This package contains shared test fixtures used across unit, contract,
and integration tests.
"""

from .test_configs import (
    sample_diff_content,
    sample_review_config,
)
from .webhook_payloads import (
    gitea_pr_webhook_payload,
    gitea_push_webhook_payload,
    github_pr_webhook_payload,
    github_push_webhook_payload,
)

__all__ = [
    "gitea_pr_webhook_payload",
    "gitea_push_webhook_payload",
    "github_pr_webhook_payload",
    "github_push_webhook_payload",
    "sample_diff_content",
    "sample_review_config",
]
