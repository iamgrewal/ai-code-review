"""
T032 - Unit Tests for GiteaAdapter

Tests the GiteaAdapter.parse_webhook() method with sample push webhook
payloads. Verifies it returns correct PRMetadata and extraction of
owner/repo/sha.

These tests MUST FAIL because they test the contract implementation
in adapters/gitea.py. The implementation may be incomplete or
have bugs that cause test failures.
"""

from unittest.mock import MagicMock, patch

import pytest

from adapters.gitea import GiteaAdapter
from models.platform import PRMetadata


class TestGiteaAdapterParseWebhook:
    """
    Test GiteaAdapter.parse_webhook() method.

    These tests verify the adapter correctly normalizes Gitea
    webhook payloads to PRMetadata format.
    """

    # -------------------------------------------------------------------------
    # Push Event Tests
    # -------------------------------------------------------------------------

    def test_parse_push_event(self, gitea_push_payload):
        """
        GIVEN a Gitea push webhook payload
        WHEN calling parse_webhook()
        THEN it should return correct PRMetadata with push data
        """
        # Arrange
        adapter = GiteaAdapter(host="gitea.example.com:3000", token="test_token")
        payload = gitea_push_payload

        # Act
        metadata = adapter.parse_webhook(payload, platform="gitea")

        # Assert
        assert isinstance(metadata, PRMetadata)
        assert metadata.repo_id == "octocat/test-repo"
        assert metadata.pr_number == 1  # Push event with no PR number in commit message uses default 1
        assert metadata.base_sha == "a" * 40
        assert metadata.head_sha == "b" * 40
        assert metadata.author == "octocat"
        assert metadata.platform == "gitea"
        assert metadata.source == "webhook"

    def test_parse_push_event_extracts_owner_and_repo(self):
        """
        GIVEN a Gitea push webhook with full_name format
        WHEN calling parse_webhook()
        THEN it should correctly extract owner and repo from full_name
        """
        # Arrange
        adapter = GiteaAdapter(host="gitea.example.com:3000", token="test_token")
        payload = {
            "repository": {
                "full_name": "mycompany/myproject",
            },
            "after": "c" * 40,
        }

        # Act
        metadata = adapter.parse_webhook(payload, platform="gitea")

        # Assert
        assert metadata.repo_id == "mycompany/myproject"

    def test_parse_push_event_with_title_from_commits(self):
        """
        GIVEN a Gitea push event with commit message
        WHEN calling parse_webhook()
        THEN it should extract title from commits array
        """
        # Arrange
        adapter = GiteaAdapter(host="gitea.example.com:3000", token="test_token")
        payload = {
            "repository": {"full_name": "octocat/test-repo"},
            "after": "b" * 40,
            "commits": [{"message": "Add authentication feature"}],
        }

        # Act
        metadata = adapter.parse_webhook(payload, platform="gitea")

        # Assert
        assert metadata.title == "Add authentication feature"

    # -------------------------------------------------------------------------
    # Pull Request Event Tests
    # -------------------------------------------------------------------------

    def test_parse_pr_opened_event(self, gitea_pr_payload):
        """
        GIVEN a Gitea pull_request opened webhook payload
        WHEN calling parse_webhook()
        THEN it should return PRMetadata with PR data
        """
        # Arrange
        adapter = GiteaAdapter(host="gitea.example.com:3000", token="test_token")
        payload = gitea_pr_payload

        # Act
        metadata = adapter.parse_webhook(payload, platform="gitea")

        # Assert
        assert isinstance(metadata, PRMetadata)
        assert metadata.repo_id == "octocat/test-repo"
        assert metadata.pr_number == 42
        assert metadata.base_sha == "a" * 40
        assert metadata.head_sha == "b" * 40
        assert metadata.author == "octocat"
        assert metadata.platform == "gitea"
        assert metadata.title == "Add new feature"

    def test_parse_pr_synchronized_event(self):
        """
        GIVEN a Gitea pull_request synchronized webhook payload
        WHEN calling parse_webhook()
        THEN it should return PRMetadata for synchronized PR
        """
        # Arrange
        adapter = GiteaAdapter(host="gitea.example.com:3000", token="test_token")
        payload = {
            "action": "synchronized",
            "repository": {"full_name": "octocat/test-repo"},
            "pull_request": {
                "number": 23,
                "title": "Updated feature",
                "user": {"login": "contributor"},
                "base": {"sha": "d" * 40},
                "head": {"sha": "e" * 40},
            },
        }

        # Act
        metadata = adapter.parse_webhook(payload, platform="gitea")

        # Assert
        assert metadata.pr_number == 23
        assert metadata.title == "Updated feature"
        assert metadata.author == "contributor"

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
        adapter = GiteaAdapter(host="gitea.example.com:3000", token="test_token")
        payload = {
            # repository missing
            "after": "b" * 40,
        }

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            adapter.parse_webhook(payload, platform="gitea")

        assert (
            "repository" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()
        )

    def test_parse_invalid_repository_full_name(self):
        """
        GIVEN a webhook with invalid full_name format (no slash)
        WHEN calling parse_webhook()
        THEN it should raise ValueError

        FAIL EXPECTED: Validates repository name parsing
        """
        # Arrange
        adapter = GiteaAdapter(host="gitea.example.com:3000", token="test_token")
        payload = {
            "repository": {
                "full_name": "invalid-repo-name",  # Missing slash
            },
            "after": "b" * 40,
        }

        # Act & Assert
        with pytest.raises(ValueError):
            adapter.parse_webhook(payload, platform="gitea")

    def test_parse_invalid_commit_sha_in_push(self):
        """
        GIVEN a push event with invalid SHA format
        WHEN calling parse_webhook()
        THEN it should raise ValueError

        FAIL EXPECTED: Validates SHA format validation
        """
        # Arrange
        adapter = GiteaAdapter(host="gitea.example.com:3000", token="test_token")
        payload = {
            "repository": {"full_name": "octocat/test-repo"},
            "after": "tooshort",  # Invalid SHA
        }

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            adapter.parse_webhook(payload, platform="gitea")

        assert "sha" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()

    def test_parse_wrong_platform(self, gitea_pr_payload):
        """
        GIVEN a Gitea webhook payload
        WHEN calling parse_webhook() with platform="github"
        THEN it should raise ValueError

        FAIL EXPECTED: Validates platform parameter enforcement
        """
        # Arrange
        adapter = GiteaAdapter(host="gitea.example.com:3000", token="test_token")

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            adapter.parse_webhook(gitea_pr_payload, platform="github")

        assert "gitea" in str(exc_info.value).lower()

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
        adapter = GiteaAdapter(host="gitea.example.com:3000", token="test_token")
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
        metadata = adapter.parse_webhook(payload, platform="gitea")

        # Assert
        assert metadata.title is None
        assert metadata.author is None


class TestGiteaAdapterGetDiff:
    """
    Test GiteaAdapter.get_diff() method.

    These tests verify the adapter correctly fetches diff content
    from Gitea API.
    """

    @patch("adapters.gitea.requests.get")
    def test_get_diff_successful(self, mock_get):
        """
        GIVEN a valid metadata
        WHEN calling get_diff()
        THEN it should fetch diff from Gitea API
        """
        # Arrange
        adapter = GiteaAdapter(host="gitea.example.com:3000", token="test_token")

        # Mock API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """diff --git a/file.py b/file.py
@@ -1,1 +1,2 @@
-old line
+new line
"""
        mock_get.return_value = mock_response

        metadata = PRMetadata(
            repo_id="octocat/test-repo",
            pr_number=1,  # Valid pr_number per spec (ge=1)
            base_sha="a" * 40,
            head_sha="b" * 40,
            platform="gitea",
        )

        # Act
        diff_blocks = adapter.get_diff(metadata)

        # Assert
        assert len(diff_blocks) > 0
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "gitea.example.com" in call_args[0][0]
        assert metadata.head_sha in call_args[0][0]

    @patch("adapters.gitea.requests.get")
    def test_get_diff_api_error(self, mock_get):
        """
        GIVEN a metadata that causes API error
        WHEN calling get_diff()
        THEN it should raise HTTPError

        FAIL EXPECTED: Validates API error handling
        """
        # Arrange
        adapter = GiteaAdapter(host="gitea.example.com:3000", token="test_token")

        # Mock API error response
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_response.raise_for_status.side_effect = Exception("404 Not Found")
        mock_get.return_value = mock_response

        metadata = PRMetadata(
            repo_id="octocat/test-repo",
            pr_number=1,  # Valid pr_number per spec (ge=1)
            base_sha="a" * 40,
            head_sha="b" * 40,
            platform="gitea",
        )

        # Act & Assert
        with pytest.raises(Exception):
            adapter.get_diff(metadata)


class TestGiteaAdapterVerifySignature:
    """
    Test GiteaAdapter.verify_signature() method.

    These tests verify HMAC-SHA256 signature verification for
    Gitea webhooks.
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

        adapter = GiteaAdapter(
            host="gitea.example.com:3000", token="test_token", verify_signature=True
        )
        payload = b'{"test": "data"}'
        secret = "webhook_secret"
        signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

        # Gitea format: sha256=<hash>
        gitea_signature = f"sha256={signature}"

        # Act
        result = adapter.verify_signature(payload, gitea_signature, secret)

        # Assert
        assert result is True

    def test_verify_invalid_signature(self):
        """
        GIVEN a webhook payload with incorrect signature
        WHEN calling verify_signature()
        THEN it should return False
        """
        # Arrange
        adapter = GiteaAdapter(
            host="gitea.example.com:3000", token="test_token", verify_signature=True
        )
        payload = b'{"test": "data"}'
        secret = "webhook_secret"
        invalid_signature = "sha256=wronghash"

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
        adapter = GiteaAdapter(
            host="gitea.example.com:3000", token="test_token", verify_signature=False
        )
        payload = b'{"test": "data"}'

        # Act
        result = adapter.verify_signature(payload, "any_signature", "any_secret")

        # Assert
        assert result is True

    def test_verify_missing_signature(self):
        """
        GIVEN a webhook payload without signature
        WHEN calling verify_signature()
        THEN it should return False
        """
        # Arrange
        adapter = GiteaAdapter(
            host="gitea.example.com:3000", token="test_token", verify_signature=True
        )
        payload = b'{"test": "data"}'

        # Act
        result = adapter.verify_signature(payload, "", "secret")

        # Assert
        assert result is False
