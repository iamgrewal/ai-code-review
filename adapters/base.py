"""
Base adapter interface for Git platform abstraction.

Defines the contract that all platform adapters must implement,
enabling platform-agnostic business logic in the service layer.
"""

from abc import ABC, abstractmethod
from typing import Optional

from models.platform import PRMetadata
from models.review import ReviewResponse


class GitPlatformAdapter(ABC):
    """
    Abstract base class for Git platform adapters.

    This interface defines all platform operations required by CortexReview,
    enabling a single codebase to work with GitHub, Gitea, and future platforms.
    """

    @abstractmethod
    def parse_webhook(self, payload: dict, platform: str) -> PRMetadata:
        """
        Parse and normalize webhook payload to PRMetadata.

        Args:
            payload: Raw webhook payload from the platform
            platform: Platform identifier ("github" or "gitea")

        Returns:
            Normalized PRMetadata with platform-specific differences abstracted

        Raises:
            ValueError: If payload is invalid or missing required fields
        """
        pass

    @abstractmethod
    def get_diff(self, metadata: PRMetadata) -> list[str]:
        """
        Fetch code diff for the PR/commit.

        Args:
            metadata: Normalized PR metadata

        Returns:
            List of diff blocks (file-specific diff strings)

        Raises:
            requests.HTTPError: If API call fails
        """
        pass

    @abstractmethod
    def post_review(self, metadata: PRMetadata, review: ReviewResponse) -> None:
        """
        Post review comments to the platform.

        Args:
            metadata: Normalized PR metadata
            review: Review response with comments to post

        Raises:
            requests.HTTPError: If API call fails
        """
        pass

    @abstractmethod
    def verify_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """
        Verify webhook signature for HMAC-SHA256.

        Args:
            payload: Raw request body bytes
            signature: Signature header value
            secret: Webhook secret for verification

        Returns:
            True if signature is valid, False otherwise

        Note:
            Returns True if verification is disabled via environment variable
        """
        pass
