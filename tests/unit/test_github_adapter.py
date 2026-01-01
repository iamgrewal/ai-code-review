"""
T031 - Unit Tests for GitHubAdapter

Tests the GitHubAdapter.parse_webhook() method with sample pull_request
and push webhook payloads. Verifies it returns correct PRMetadata for
opened/edited/synchronize events.

These tests MUST FAIL because they test the contract implementation
in adapters/github.py. The implementation may be incomplete or
have bugs that cause test failures.
"""

from unittest.mock import MagicMock, patch

import pytest

from adapters.github import GitHubAdapter
from models.platform import PRMetadata


class TestGitHubAdapterParseWebhook:
    """
    Test GitHubAdapter.parse_webhook() method.

    These tests verify the adapter correctly normalizes GitHub
    webhook payloads to PRMetadata format.
    """

    # -------------------------------------------------------------------------
    # Pull Request Event Tests
    # -------------------------------------------------------------------------

    def test_parse_pr_opened_event(self, github_pr_webhook_payload):
        """
        GIVEN a GitHub pull_request opened webhook payload
        WHEN calling parse_webhook()
        THEN it should return correct PRMetadata with PR data
        """
        # Arrange
        adapter = GitHubAdapter(token="test_token")
        payload = github_pr_webhook_payload

        # Act
        metadata = adapter.parse_webhook(payload, platform="github")

        # Assert
        assert isinstance(metadata, PRMetadata)
        assert metadata.repo_id == "octocat/test-repo"
        assert metadata.pr_number == 42
        assert metadata.base_sha == "a" * 40
        assert metadata.head_sha == "b" * 40
        assert metadata.author == "octocat"
        assert metadata.platform == "github"
        assert metadata.title == "Add new feature"
        assert metadata.source == "webhook"

    def test_parse_pr_edited_event(self):
        """
        GIVEN a GitHub pull_request edited webhook payload
        WHEN calling parse_webhook()
        THEN it should return PRMetadata for the edited PR
        """
        # Arrange
        adapter = GitHubAdapter(token="test_token")
        payload = {
            "action": "edited",
            "repository": {
                "full_name": "octocat/test-repo",
            },
            "pull_request": {
                "number": 15,
                "title": "Updated PR title",
                "user": {"login": "contributor"},
                "base": {"sha": "c" * 40},
                "head": {"sha": "d" * 40},
            },
        }

        # Act
        metadata = adapter.parse_webhook(payload, platform="github")

        # Assert
        assert metadata.pr_number == 15
        assert metadata.title == "Updated PR title"
        assert metadata.author == "contributor"
        assert metadata.base_sha == "c" * 40
        assert metadata.head_sha == "d" * 40

    def test_parse_pr_synchronize_event(self):
        """
        GIVEN a GitHub pull_request synchronize webhook payload
        WHEN calling parse_webhook()
        THEN it should return PRMetadata for the synchronized PR
        """
        # Arrange
        adapter = GitHubAdapter(token="test_token")
        payload = {
            "action": "synchronize",
            "repository": {
                "full_name": "octocat/test-repo",
            },
            "pull_request": {
                "number": 7,
                "title": "Feature in progress",
                "user": {"login": "developer"},
                "base": {"sha": "e" * 40},
                "head": {"sha": "f" * 40},
            },
        }

        # Act
        metadata = adapter.parse_webhook(payload, platform="github")

        # Assert
        assert metadata.pr_number == 7
        assert metadata.title == "Feature in progress"
        assert metadata.author == "developer"

    # -------------------------------------------------------------------------
    # Push Event Tests
    # -------------------------------------------------------------------------

    def test_parse_push_event(self, github_push_webhook_payload):
        """
        GIVEN a GitHub push webhook payload
        WHEN calling parse_webhook()
        THEN it should return PRMetadata with pr_number=0
        """
        # Arrange
        adapter = GitHubAdapter(token="test_token")
        payload = github_push_webhook_payload

        # Act
        metadata = adapter.parse_webhook(payload, platform="github")

        # Assert
        assert isinstance(metadata, PRMetadata)
        assert metadata.repo_id == "octocat/test-repo"
        assert metadata.pr_number == 0  # Push event has no PR
        assert metadata.base_sha == "a" * 40
        assert metadata.head_sha == "b" * 40
        assert metadata.author == "octocat"
        assert metadata.platform == "github"

    # -------------------------------------------------------------------------
    # Invalid Payload Tests
    # -------------------------------------------------------------------------

    def test_parse_missing_repository(self):
        """
        GIVEN a webhook payload without repository field
        WHEN calling parse_webhook()
        THEN it should raise ValueError

        FAIL EXPECTED: Validates error handling for malformed payloads
        """
        # Arrange
        adapter = GitHubAdapter(token="test_token")
        payload = {
            # repository missing
            "pull_request": {
                "number": 42,
            },
        }

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            adapter.parse_webhook(payload, platform="github")

        assert "repository" in str(exc_info.value).lower()

    def test_parse_missing_pull_request_and_after(self):
        """
        GIVEN a payload without pull_request or after field
        WHEN calling parse_webhook()
        THEN it should raise ValueError

        FAIL EXPECTED: Validates error handling for incomplete payloads
        """
        # Arrange
        adapter = GitHubAdapter(token="test_token")
        payload = {
            "repository": {"full_name": "octocat/test-repo"},
            # No pull_request or after fields
        }

        # Act & Assert
        with pytest.raises(ValueError):
            adapter.parse_webhook(payload, platform="github")

    def test_parse_invalid_commit_sha(self):
        """
        GIVEN a push event with invalid SHA format
        WHEN calling parse_webhook()
        THEN it should raise ValueError

        FAIL EXPECTED: Validates SHA format validation
        """
        # Arrange
        adapter = GitHubAdapter(token="test_token")
        payload = {
            "repository": {"full_name": "octocat/test-repo"},
            "after": "short",  # Invalid SHA
        }

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            adapter.parse_webhook(payload, platform="github")

        assert "sha" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()

    def test_parse_wrong_platform(self, github_pr_webhook_payload):
        """
        GIVEN a GitHub webhook payload
        WHEN calling parse_webhook() with platform="gitea"
        THEN it should raise ValueError

        FAIL EXPECTED: Validates platform parameter enforcement
        """
        # Arrange
        adapter = GitHubAdapter(token="test_token")

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            adapter.parse_webhook(github_pr_webhook_payload, platform="gitea")

        assert "github" in str(exc_info.value).lower()

    # -------------------------------------------------------------------------
    # Optional Field Tests
    # -------------------------------------------------------------------------

    def test_parse_missing_optional_fields(self):
        """
        GIVEN a webhook payload without optional fields
        WHEN calling parse_webhook()
        THEN it should return PRMetadata with None for missing fields
        """
        # Arrange
        adapter = GitHubAdapter(token="test_token")
        payload = {
            "repository": {"full_name": "octocat/test-repo"},
            "pull_request": {
                "number": 42,
                "base": {"sha": "a" * 40},
                "head": {"sha": "b" * 40},
                # No title, user
            },
        }

        # Act
        metadata = adapter.parse_webhook(payload, platform="github")

        # Assert
        assert metadata.title is None
        assert metadata.author is None


class TestGitHubAdapterGetDiff:
    """
    Test GitHubAdapter.get_diff() method.

    These tests verify the adapter correctly fetches diff content
    from GitHub API for both PRs and push events.
    """

    @patch("adapters.github.Github")
    def test_get_diff_for_pr(self, mock_github_class):
        """
        GIVEN a PR metadata
        WHEN calling get_diff()
        THEN it should fetch PR diff from GitHub API
        """
        # Arrange
        adapter = GitHubAdapter(token="test_token")

        # Setup mocks
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_file = MagicMock()
        mock_file.patch = "@@ file.py @@\n+new line"
        mock_file.filename = "src/file.py"

        mock_pr.get_files.return_value = [mock_file]
        mock_repo.get_pull.return_value = mock_pr
        mock_github_instance = MagicMock()
        mock_github_instance.get_repo.return_value = mock_repo
        mock_github_class.return_value = mock_github_instance

        metadata = PRMetadata(
            repo_id="octocat/test-repo",
            pr_number=42,
            base_sha="a" * 40,
            head_sha="b" * 40,
            platform="github",
        )

        # Act
        diff_blocks = adapter.get_diff(metadata)

        # Assert
        assert len(diff_blocks) > 0
        mock_github_instance.get_repo.assert_called_once_with("octocat/test-repo")
        mock_repo.get_pull.assert_called_once_with(42)

    @patch("adapters.github.Github")
    def test_get_diff_for_push_event(self, mock_github_class):
        """
        GIVEN a push event metadata (pr_number=0)
        WHEN calling get_diff()
        THEN it should fetch commit diff from GitHub API
        """
        # Arrange
        adapter = GitHubAdapter(token="test_token")

        # Setup mocks
        mock_repo = MagicMock()
        mock_commit = MagicMock()
        mock_file = MagicMock()
        mock_file.patch = "@@ file.py @@\n+new line"

        mock_commit.files = [mock_file]
        mock_repo.get_commit.return_value = mock_commit
        mock_github_instance = MagicMock()
        mock_github_instance.get_repo.return_value = mock_repo
        mock_github_class.return_value = mock_github_instance

        metadata = PRMetadata(
            repo_id="octocat/test-repo",
            pr_number=0,  # Push event
            base_sha="a" * 40,
            head_sha="b" * 40,
            platform="github",
        )

        # Act
        diff_blocks = adapter.get_diff(metadata)

        # Assert
        mock_repo.get_commit.assert_called_once_with(metadata.head_sha)


class TestGitHubAdapterVerifySignature:
    """
    Test GitHubAdapter.verify_signature() method.

    These tests verify HMAC-SHA256 signature verification for
    GitHub webhooks.
    """

    def test_verify_valid_signature(self):
        """
        GIVEN a valid webhook payload and signature
        WHEN calling verify_signature()
        THEN it should return True
        """
        # Arrange
        import hashlib
        import hmac

        adapter = GitHubAdapter(token="test_token", verify_signature=True)
        payload = b'{"test": "data"}'
        secret = "webhook_secret"
        signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

        # GitHub format: sha256=<hash>
        github_signature = f"sha256={signature}"

        # Act
        result = adapter.verify_signature(payload, github_signature, secret)

        # Assert
        assert result is True

    def test_verify_invalid_signature(self):
        """
        GIVEN a webhook payload with incorrect signature
        WHEN calling verify_signature()
        THEN it should return False
        """
        # Arrange
        adapter = GitHubAdapter(token="test_token", verify_signature=True)
        payload = b'{"test": "data"}'
        secret = "webhook_secret"
        invalid_signature = "sha256=invalidhash"

        # Act
        result = adapter.verify_signature(payload, invalid_signature, secret)

        # Assert
        assert result is False

    def test_verify_signature_disabled(self):
        """
        GIVEN signature verification disabled
        WHEN calling verify_signature()
        THEN it should return True regardless of signature
        """
        # Arrange
        adapter = GitHubAdapter(token="test_token", verify_signature=False)
        payload = b'{"test": "data"}'

        # Act
        result = adapter.verify_signature(payload, "invalid", "secret")

        # Assert
        assert result is True

    def test_verify_missing_signature(self):
        """
        GIVEN a webhook payload without signature
        WHEN calling verify_signature()
        THEN it should return False
        """
        # Arrange
        adapter = GitHubAdapter(token="test_token", verify_signature=True)
        payload = b'{"test": "data"}'

        # Act
        result = adapter.verify_signature(payload, "", "secret")

        # Assert
        assert result is False
