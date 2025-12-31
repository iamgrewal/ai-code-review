"""
Gitea platform adapter implementation.

Implements GitPlatformAdapter for Gitea, handling webhook parsing,
diff fetching, review posting, and signature verification.
"""

import hashlib
import hmac
import re
from typing import Optional

import requests
from loguru import logger

from adapters.base import GitPlatformAdapter
from models.platform import PRMetadata
from models.review import ReviewResponse


class GiteaAdapter(GitPlatformAdapter):
    """
    Gitea implementation of GitPlatformAdapter.

    Handles all Gitea-specific API interactions including webhook
    payload parsing, diff retrieval, issue/comment posting, and
    HMAC signature verification.
    """

    def __init__(self, host: str, token: str, verify_signature: bool = True):
        """
        Initialize Gitea adapter.

        Args:
            host: Gitea server host (e.g., "gitea.example.com:3000")
            token: Gitea API token
            verify_signature: Enable/disable webhook signature verification
        """
        self.host = host
        self.token = token
        self.verify_signature = verify_signature

    def parse_webhook(self, payload: dict, platform: str = "gitea") -> PRMetadata:
        """
        Parse Gitea webhook payload to PRMetadata.

        Handles both pull request events and push events, normalizing
        them to the unified PRMetadata format.

        Args:
            payload: Gitea webhook payload
            platform: Platform identifier (should be "gitea")

        Returns:
            Normalized PRMetadata

        Raises:
            ValueError: If payload is missing required fields
        """
        if platform != "gitea":
            raise ValueError(f"Expected platform='gitea', got '{platform}'")

        # Extract repository info
        try:
            full_name = payload["repository"]["full_name"]
            owner, repo = full_name.split("/")
        except (KeyError, ValueError) as e:
            raise ValueError(f"Invalid repository format: {e}")

        # Extract PR number or commit SHA
        if "pull_request" in payload:
            # PR event
            pr_data = payload["pull_request"]
            pr_number = pr_data["number"]
            base_sha = pr_data["base"]["sha"]
            head_sha = pr_data["head"]["sha"]
            title = pr_data.get("title")
            author = pr_data.get("user", {}).get("login")
        else:
            # Push event - extract from after SHA
            try:
                pr_number = 0  # Push events don't have PR numbers
                base_sha = payload.get("before", "")
                head_sha = payload["after"]
                title = payload.get("commits", [{}])[0].get("message", "")
                author = payload.get("pusher", {}).get("login")
                # Validate SHA format
                if not head_sha or len(head_sha) < 40:
                    raise ValueError("Invalid commit SHA in payload")
            except (KeyError, IndexError) as e:
                raise ValueError(f"Invalid push event payload: {e}")

        return PRMetadata(
            repo_id=full_name,
            pr_number=pr_number,
            base_sha=base_sha[:40],
            head_sha=head_sha[:40],
            author=author,
            platform="gitea",
            title=title,
        )

    def get_diff(self, metadata: PRMetadata) -> list[str]:
        """
        Fetch diff content from Gitea API.

        Args:
            metadata: Normalized PR metadata

        Returns:
            List of diff blocks (file-specific chunks)

        Raises:
            requests.HTTPError: If API call fails
        """
        endpoint = f"https://{self.host}/api/v1/repos/{metadata.repo_id}/git/commits/{metadata.head_sha}.diff"
        params = {"access_token": self.token}

        response = requests.get(endpoint, params=params)
        if response.status_code != 200:
            logger.error(f"Gitea API error {response.status_code}: {response.text}")
            response.raise_for_status()

        # Split diff by file
        diff_blocks = re.split(r"^diff --git ", response.text.strip(), flags=re.MULTILINE)
        return [block for block in diff_blocks if block]

    def post_review(self, metadata: PRMetadata, review: ReviewResponse) -> None:
        """
        Post review comments as a Gitea issue with comments.

        Gitea doesn't have native review comments, so we create an issue
        and add comments for each file reviewed.

        Args:
            metadata: Normalized PR metadata
            review: Review response with comments

        Raises:
            requests.HTTPError: If API call fails
        """
        owner, repo = metadata.repo_id.split("/")

        # Create issue for the review
        issue_title = f"Code Review: {metadata.title or f'Commit {metadata.head_sha[:7]}'}"
        issue_body = self._format_issue_body(review)

        endpoint = f"https://{self.host}/api/v1/repos/{owner}/{repo}/issues"
        params = {"access_token": self.token}

        issue_data = {
            "title": issue_title,
            "body": issue_body,
            "ref": metadata.head_sha,
            "assignees": [metadata.author] if metadata.author else [],
        }

        response = requests.post(endpoint, params=params, json=issue_data)
        if response.status_code != 201:
            logger.error(f"Failed to create issue: {response.status_code} {response.text}")
            response.raise_for_status()

        logger.info(f"Created Gitea issue for review {review.review_id}")

    def _format_issue_body(self, review: ReviewResponse) -> str:
        """Format review as issue body with AI banner."""
        banner = "\n---\n*This review was generated by [CortexReview](https://github.com/bestK/gitea-ai-codereview)*\n"

        sections = [f"## {review.summary}", f"**Statistics:** {review.stats.total_issues} issues found"]

        for comment in review.comments:
            sections.append(f"\n### {comment.file_path}:{comment.line_range.get('start', '?')}\n")
            sections.append(f"**{comment.severity.value.upper()}:** {comment.message}\n")
            if comment.suggestion:
                sections.append(f"**Suggestion:** {comment.suggestion}\n")
            if comment.citations:
                sections.append(f"**Citations:** {', '.join(comment.citations)}\n")

        sections.append(banner)
        return "\n".join(sections)

    def verify_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """
        Verify Gitea webhook HMAC-SHA256 signature.

        Args:
            payload: Raw request body bytes
            signature: X-Gitea-Signature header value
            secret: Webhook secret

        Returns:
            True if signature valid or verification disabled, False otherwise
        """
        if not self.verify_signature:
            return True

        if not signature or not secret:
            logger.warning("Missing signature or secret for verification")
            return False

        # Gitea uses format: sha256=<hash>
        if not signature.startswith("sha256="):
            logger.warning(f"Invalid signature format: {signature[:20]}...")
            return False

        signature_hash = signature.split("=")[1]

        # Compute HMAC-SHA256
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

        is_valid = hmac.compare_digest(expected, signature_hash)
        if not is_valid:
            logger.warning("Invalid Gitea webhook signature")

        return is_valid
