"""
GitHub platform adapter implementation.

Implements GitPlatformAdapter for GitHub, handling webhook parsing,
diff fetching, review posting, and signature verification.
"""

import hashlib
import hmac

from github import Github, GithubException
from loguru import logger

from adapters.base import GitPlatformAdapter
from models.platform import PRMetadata
from models.review import ReviewResponse


class GitHubAdapter(GitPlatformAdapter):
    """
    GitHub implementation of GitPlatformAdapter.

    Handles all GitHub-specific API interactions including webhook
    payload parsing, diff retrieval, pull request review comments,
    and HMAC signature verification.
    """

    def __init__(self, token: str, verify_signature: bool = True):
        """
        Initialize GitHub adapter.

        Args:
            token: GitHub personal access token
            verify_signature: Enable/disable webhook signature verification
        """
        self.token = token
        self.verify_signature = verify_signature
        self.client = Github(token)

    def parse_webhook(self, payload: dict, platform: str = "github") -> PRMetadata:
        """
        Parse GitHub webhook payload to PRMetadata.

        Handles both pull_request events and push events, normalizing
        them to the unified PRMetadata format.

        Args:
            payload: GitHub webhook payload
            platform: Platform identifier (should be "github")

        Returns:
            Normalized PRMetadata

        Raises:
            ValueError: If payload is missing required fields
        """
        if platform != "github":
            raise ValueError(f"Expected platform='github', got '{platform}'")

        # Extract repository info
        try:
            repo_full_name = payload["repository"]["full_name"]
        except KeyError as e:
            raise ValueError(f"Missing repository in payload: {e}")

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
                author = payload.get("pusher", {}).get("name")
                # Validate SHA format
                if not head_sha or len(head_sha) < 40:
                    raise ValueError("Invalid commit SHA in payload")
            except (KeyError, IndexError) as e:
                raise ValueError(f"Invalid push event payload: {e}")

        return PRMetadata(
            repo_id=repo_full_name,
            pr_number=pr_number,
            base_sha=base_sha[:40],
            head_sha=head_sha[:40],
            author=author,
            platform="github",
            title=title,
        )

    def get_diff(self, metadata: PRMetadata) -> list[str]:
        """
        Fetch diff content from GitHub API.

        Args:
            metadata: Normalized PR metadata

        Returns:
            List of diff blocks (file-specific chunks)

        Raises:
            GithubException: If API call fails
        """
        try:
            repo = self.client.get_repo(metadata.repo_id)

            if metadata.pr_number > 0:
                # PR event - get diff from pull request
                pr = repo.get_pull(metadata.pr_number)
                diff_content = pr.get_files().raw_data
                # GitHub API returns file list, not unified diff
                # Construct diff blocks from files
                diff_blocks = []
                for file in pr.get_files():
                    if file.patch:
                        diff_blocks.append(
                            f"diff --git a/{file.filename} b/{file.filename}\n{file.patch}"
                        )
                return diff_blocks
            else:
                # Push event - get commit diff
                commit = repo.get_commit(metadata.head_sha)
                # GitHub doesn't provide direct diff endpoint for commits
                # Use files() to get changed files with patches
                diff_blocks = []
                for file in commit.files:
                    if file.patch:
                        diff_blocks.append(
                            f"diff --git a/{file.filename} b/{file.filename}\n{file.patch}"
                        )
                return diff_blocks

        except GithubException as e:
            logger.error(f"GitHub API error: {e}")
            raise

    def post_review(self, metadata: PRMetadata, review: ReviewResponse) -> None:
        """
        Post review comments as GitHub pull request review.

        Args:
            metadata: Normalized PR metadata
            review: Review response with comments

        Raises:
            GithubException: If API call fails
        """
        try:
            repo = self.client.get_repo(metadata.repo_id)

            if metadata.pr_number > 0:
                # PR event - create review comments
                pr = repo.get_pull(metadata.pr_number)

                # Convert ReviewComment to GitHub review comments
                comments = []
                for comment in review.comments:
                    comments.append(
                        {
                            "path": comment.file_path,
                            "line": comment.line_range.get("start", 1),
                            "body": self._format_comment_body(comment),
                        }
                    )

                # Create pull request review
                pr.create_review(
                    body=review.summary,
                    comments=comments,
                    event="COMMENT",  # Use COMMENT to not approve/request changes
                )

                logger.info(f"Created GitHub PR review for {review.review_id}")
            else:
                # Push event - create issue with review
                issue_title = f"Code Review: {metadata.title or f'Commit {metadata.head_sha[:7]}'}"
                issue_body = self._format_issue_body(review)

                repo.create_issue(
                    title=issue_title,
                    body=issue_body,
                    assignees=[metadata.author] if metadata.author else [],
                )

                logger.info(f"Created GitHub issue for review {review.review_id}")

        except GithubException as e:
            logger.error(f"Failed to post GitHub review: {e}")
            raise

    def _format_comment_body(self, comment) -> str:
        """Format individual review comment for GitHub."""
        parts = [
            f"**{comment.severity.value.upper()}:** {comment.message}",
        ]
        if comment.suggestion:
            parts.append(f"**Suggestion:** {comment.suggestion}")
        if comment.citations:
            parts.append(f"**Citations:** {', '.join(comment.citations)}")
        return "\n\n".join(parts)

    def _format_issue_body(self, review: ReviewResponse) -> str:
        """Format review as issue body with AI banner."""
        banner = "\n---\n*This review was generated by [CortexReview](https://github.com/bestK/gitea-ai-codereview)*\n"

        sections = [
            f"## {review.summary}",
            f"**Statistics:** {review.stats.total_issues} issues found",
        ]

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
        Verify GitHub webhook HMAC-SHA256 signature.

        Args:
            payload: Raw request body bytes
            signature: X-Hub-Signature-256 header value
            secret: Webhook secret

        Returns:
            True if signature valid or verification disabled, False otherwise
        """
        if not self.verify_signature:
            return True

        if not signature or not secret:
            logger.warning("Missing signature or secret for verification")
            return False

        # GitHub uses format: sha256=<hash>
        if not signature.startswith("sha256="):
            logger.warning(f"Invalid signature format: {signature[:20]}...")
            return False

        signature_hash = signature.split("=")[1]

        # Compute HMAC-SHA256
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

        is_valid = hmac.compare_digest(expected, signature_hash)
        if not is_valid:
            logger.warning("Invalid GitHub webhook signature")

        return is_valid
