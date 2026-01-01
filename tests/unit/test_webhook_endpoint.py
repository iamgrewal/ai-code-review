"""
Unit tests for POST /v1/webhook/{platform} endpoint (T037, T038).

Tests verify:
- Webhook endpoint returns 202 with task_id and trace_id
- Celery task is dispatched with correct metadata
- Signature verification works correctly
- Env var opt-out for signature verification
"""

import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


class TestWebhookEndpointUnit:
    """
    Unit tests for /v1/webhook/{platform} endpoint (T037, T038).
    """

    def test_github_webhook_returns_202_with_task_info(
        self, github_pr_payload, monkeypatch
    ):
        """
        T037: GIVEN a valid GitHub webhook payload
        WHEN POST /v1/webhook/github
        THEN returns HTTP 202 with task_id and trace_id
        """
        # Set required environment before importing main
        monkeypatch.setenv("GITHUB_TOKEN", "test_token")
        monkeypatch.setenv("GITEA_TOKEN", "test_token")
        monkeypatch.setenv("GITEA_HOST", "gitea.example.com:3000")
        monkeypatch.setenv("LLM_API_KEY", "test_llm_key")
        monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

        from main import app

        # Mock Celery task
        with patch("worker.process_code_review") as mock_task:
            task_id = str(uuid.uuid4())
            mock_result = MagicMock(id=task_id)
            mock_task.delay = MagicMock(return_value=mock_result)

            with TestClient(app) as client:
                response = client.post(
                    "/v1/webhook/github",
                    json=github_pr_payload,
                )

        # Verify HTTP 202
        assert response.status_code == 202

        # Verify response structure
        data = response.json()
        assert "task_id" in data
        assert "trace_id" in data
        assert data["status"] == "pending"
        assert "message" in data

        # Verify task_id is valid UUID
        uuid.UUID(data["task_id"])
        uuid.UUID(data["trace_id"])

    def test_gitea_webhook_returns_202_with_task_info(
        self, gitea_push_payload, monkeypatch
    ):
        """
        T037: GIVEN a valid Gitea webhook payload
        WHEN POST /v1/webhook/gitea
        THEN returns HTTP 202 with task_id and trace_id
        """
        # Set required environment before importing main
        monkeypatch.setenv("GITHUB_TOKEN", "test_token")
        monkeypatch.setenv("GITEA_TOKEN", "test_token")
        monkeypatch.setenv("GITEA_HOST", "gitea.example.com:3000")
        monkeypatch.setenv("LLM_API_KEY", "test_llm_key")
        monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

        from main import app

        # Mock Celery task
        with patch("worker.process_code_review") as mock_task:
            task_id = str(uuid.uuid4())
            mock_result = MagicMock(id=task_id)
            mock_task.delay = MagicMock(return_value=mock_result)

            with TestClient(app) as client:
                response = client.post(
                    "/v1/webhook/gitea",
                    json=gitea_push_payload,
                )

        # Verify HTTP 202
        assert response.status_code == 202

        # Verify response structure
        data = response.json()
        assert "task_id" in data
        assert "trace_id" in data
        assert data["status"] == "pending"

    def test_invalid_json_returns_400(self, monkeypatch):
        """
        GIVEN invalid JSON payload
        WHEN POST /v1/webhook/github
        THEN returns HTTP 400 with error message
        """
        # Set required environment before importing main
        monkeypatch.setenv("GITHUB_TOKEN", "test_token")
        monkeypatch.setenv("GITEA_TOKEN", "test_token")
        monkeypatch.setenv("GITEA_HOST", "gitea.example.com:3000")
        monkeypatch.setenv("LLM_API_KEY", "test_llm_key")
        monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

        from main import app

        with patch("worker.process_code_review") as mock_task:
            mock_task.delay = MagicMock(return_value=MagicMock(id=str(uuid.uuid4())))

            with TestClient(app) as client:
                response = client.post(
                    "/v1/webhook/github",
                    content="not valid json",
                    headers={"Content-Type": "application/json"},
                )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data

    def test_invalid_platform_returns_400(self, monkeypatch):
        """
        GIVEN an invalid platform parameter
        WHEN POST /v1/webhook/invalid
        THEN returns HTTP 400
        """
        # Set required environment before importing main
        monkeypatch.setenv("GITHUB_TOKEN", "test_token")
        monkeypatch.setenv("GITEA_TOKEN", "test_token")
        monkeypatch.setenv("GITEA_HOST", "gitea.example.com:3000")
        monkeypatch.setenv("LLM_API_KEY", "test_llm_key")
        monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

        from main import app

        with patch("worker.process_code_review") as mock_task:
            mock_task.delay = MagicMock(return_value=MagicMock(id=str(uuid.uuid4())))

            with TestClient(app) as client:
                response = client.post(
                    "/v1/webhook/invalid",
                    json={},
                )

        assert response.status_code == 400

    def test_webhook_dispatches_celery_task(self, github_pr_payload, monkeypatch):
        """
        T037: GIVEN a valid webhook payload
        WHEN POST /v1/webhook/github
        THEN Celery process_code_review.delay() is called with PRMetadata
        """
        # Set required environment before importing main
        monkeypatch.setenv("GITHUB_TOKEN", "test_token")
        monkeypatch.setenv("GITEA_TOKEN", "test_token")
        monkeypatch.setenv("GITEA_HOST", "gitea.example.com:3000")
        monkeypatch.setenv("LLM_API_KEY", "test_llm_key")
        monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

        from main import app

        with patch("worker.process_code_review") as mock_task:
            task_id = str(uuid.uuid4())
            mock_result = MagicMock(id=task_id)
            mock_task.delay = MagicMock(return_value=mock_result)

            with TestClient(app) as client:
                response = client.post(
                    "/v1/webhook/github",
                    json=github_pr_payload,
                )

            # Verify Celery task was called
            mock_task.delay.assert_called_once()

            # Verify call arguments
            call_args = mock_task.delay.call_args
            metadata_dict = call_args[0][0]
            trace_id = call_args[0][1]

            # Verify PRMetadata structure
            assert metadata_dict["repo_id"] == "octocat/test-repo"
            assert metadata_dict["pr_number"] == 42
            assert metadata_dict["platform"] == "github"

            # Verify trace_id format
            assert isinstance(trace_id, str)
            uuid.UUID(trace_id)


class TestWebhookSignatureVerification:
    """
    Unit tests for webhook signature verification (T038).
    """

    def test_github_webhook_with_valid_signature_accepted(
        self, github_pr_payload, monkeypatch
    ):
        """
        T038: GIVEN a valid GitHub webhook with correct signature
        WHEN POST /v1/webhook/github with X-Hub-Signature-256
        THEN accepts request (202) when signature matches
        """
        import hashlib
        import hmac

        # Set required environment before importing main
        monkeypatch.setenv("GITHUB_TOKEN", "test_token")
        monkeypatch.setenv("GITEA_TOKEN", "test_token")
        monkeypatch.setenv("GITEA_HOST", "gitea.example.com:3000")
        monkeypatch.setenv("LLM_API_KEY", "test_llm_key")
        monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
        monkeypatch.setenv("PLATFORM_GITHUB_WEBHOOK_SECRET", "test_secret")
        monkeypatch.setenv("PLATFORM_GITHUB_VERIFY_SIGNATURE", "true")

        from main import app

        payload_bytes = str(github_pr_payload).encode()
        signature = hmac.new(b"test_secret", payload_bytes, hashlib.sha256).hexdigest()
        signature_header = f"sha256={signature}"

        with patch("worker.process_code_review") as mock_task:
            mock_task.delay = MagicMock(return_value=MagicMock(id=str(uuid.uuid4())))

            with TestClient(app) as client:
                response = client.post(
                    "/v1/webhook/github",
                    json=github_pr_payload,
                    headers={"X-Hub-Signature-256": signature_header},
                )

        assert response.status_code == 202

    def test_github_webhook_with_invalid_signature_returns_401(
        self, github_pr_payload, monkeypatch
    ):
        """
        T038: GIVEN a GitHub webhook with incorrect signature
        WHEN POST /v1/webhook/github with invalid X-Hub-Signature-256
        THEN returns HTTP 401 Unauthorized
        """
        # Set required environment before importing main
        monkeypatch.setenv("GITHUB_TOKEN", "test_token")
        monkeypatch.setenv("GITEA_TOKEN", "test_token")
        monkeypatch.setenv("GITEA_HOST", "gitea.example.com:3000")
        monkeypatch.setenv("LLM_API_KEY", "test_llm_key")
        monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
        monkeypatch.setenv("PLATFORM_GITHUB_WEBHOOK_SECRET", "test_secret")
        monkeypatch.setenv("PLATFORM_GITHUB_VERIFY_SIGNATURE", "true")

        from main import app

        with patch("worker.process_code_review") as mock_task:
            mock_task.delay = MagicMock(return_value=MagicMock(id=str(uuid.uuid4())))

            with TestClient(app) as client:
                response = client.post(
                    "/v1/webhook/github",
                    json=github_pr_payload,
                    headers={"X-Hub-Signature-256": "sha256=invalid"},
                )

        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "signature" in data["detail"].lower()

    def test_github_signature_verification_can_be_disabled(
        self, github_pr_payload, monkeypatch
    ):
        """
        T038: GIVEN PLATFORM_GITHUB_VERIFY_SIGNATURE=false
        WHEN POST /v1/webhook/github without signature
        THEN accepts request (202)
        """
        # Set required environment before importing main
        monkeypatch.setenv("GITHUB_TOKEN", "test_token")
        monkeypatch.setenv("GITEA_TOKEN", "test_token")
        monkeypatch.setenv("GITEA_HOST", "gitea.example.com:3000")
        monkeypatch.setenv("LLM_API_KEY", "test_llm_key")
        monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
        monkeypatch.setenv("PLATFORM_GITHUB_WEBHOOK_SECRET", "test_secret")
        monkeypatch.setenv("PLATFORM_GITHUB_VERIFY_SIGNATURE", "false")

        from main import app

        with patch("worker.process_code_review") as mock_task:
            mock_task.delay = MagicMock(return_value=MagicMock(id=str(uuid.uuid4())))

            with TestClient(app) as client:
                response = client.post(
                    "/v1/webhook/github",
                    json=github_pr_payload,
                )

        assert response.status_code == 202

    def test_gitea_signature_verification_can_be_disabled(
        self, gitea_push_payload, monkeypatch
    ):
        """
        T038: GIVEN PLATFORM_GITEA_VERIFY_SIGNATURE=false
        WHEN POST /v1/webhook/gitea without signature
        THEN accepts request (202)
        """
        # Set required environment before importing main
        monkeypatch.setenv("GITHUB_TOKEN", "test_token")
        monkeypatch.setenv("GITEA_TOKEN", "test_token")
        monkeypatch.setenv("GITEA_HOST", "gitea.example.com:3000")
        monkeypatch.setenv("LLM_API_KEY", "test_llm_key")
        monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
        monkeypatch.setenv("PLATFORM_GITEA_WEBHOOK_SECRET", "test_secret")
        monkeypatch.setenv("PLATFORM_GITEA_VERIFY_SIGNATURE", "false")

        from main import app

        with patch("worker.process_code_review") as mock_task:
            mock_task.delay = MagicMock(return_value=MagicMock(id=str(uuid.uuid4())))

            with TestClient(app) as client:
                response = client.post(
                    "/v1/webhook/gitea",
                    json=gitea_push_payload,
                )

        assert response.status_code == 202

    def test_gitea_webhook_with_valid_signature_accepted(
        self, gitea_push_payload, monkeypatch
    ):
        """
        T038: GIVEN a valid Gitea webhook with correct signature
        WHEN POST /v1/webhook/gitea with X-Gitea-Signature
        THEN accepts request (202) when signature matches
        """
        import hashlib
        import hmac

        # Set required environment before importing main
        monkeypatch.setenv("GITHUB_TOKEN", "test_token")
        monkeypatch.setenv("GITEA_TOKEN", "test_token")
        monkeypatch.setenv("GITEA_HOST", "gitea.example.com:3000")
        monkeypatch.setenv("LLM_API_KEY", "test_llm_key")
        monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
        monkeypatch.setenv("PLATFORM_GITEA_WEBHOOK_SECRET", "test_secret")
        monkeypatch.setenv("PLATFORM_GITEA_VERIFY_SIGNATURE", "true")

        from main import app

        payload_bytes = str(gitea_push_payload).encode()
        signature = hmac.new(b"test_secret", payload_bytes, hashlib.sha256).hexdigest()
        signature_header = f"sha256={signature}"

        with patch("worker.process_code_review") as mock_task:
            mock_task.delay = MagicMock(return_value=MagicMock(id=str(uuid.uuid4())))

            with TestClient(app) as client:
                response = client.post(
                    "/v1/webhook/gitea",
                    json=gitea_push_payload,
                    headers={"X-Gitea-Signature": signature_header},
                )

        assert response.status_code == 202

    def test_gitea_webhook_with_invalid_signature_returns_401(
        self, gitea_push_payload, monkeypatch
    ):
        """
        T038: GIVEN a Gitea webhook with incorrect signature
        WHEN POST /v1/webhook/gitea with invalid X-Gitea-Signature
        THEN returns HTTP 401 Unauthorized
        """
        # Set required environment before importing main
        monkeypatch.setenv("GITHUB_TOKEN", "test_token")
        monkeypatch.setenv("GITEA_TOKEN", "test_token")
        monkeypatch.setenv("GITEA_HOST", "gitea.example.com:3000")
        monkeypatch.setenv("LLM_API_KEY", "test_llm_key")
        monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
        monkeypatch.setenv("PLATFORM_GITEA_WEBHOOK_SECRET", "test_secret")
        monkeypatch.setenv("PLATFORM_GITEA_VERIFY_SIGNATURE", "true")

        from main import app

        with patch("worker.process_code_review") as mock_task:
            mock_task.delay = MagicMock(return_value=MagicMock(id=str(uuid.uuid4())))

            with TestClient(app) as client:
                response = client.post(
                    "/v1/webhook/gitea",
                    json=gitea_push_payload,
                    headers={"X-Gitea-Signature": "sha256=invalid"},
                )

        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "signature" in data["detail"].lower()

    def test_signature_verification_skipped_when_no_secret(
        self, github_pr_payload, monkeypatch
    ):
        """
        T038: GIVEN no PLATFORM_GITHUB_WEBHOOK_SECRET configured
        WHEN POST /v1/webhook/github
        THEN accepts request (202) with warning logged
        """
        # Set required environment before importing main (no secret)
        monkeypatch.setenv("GITHUB_TOKEN", "test_token")
        monkeypatch.setenv("GITEA_TOKEN", "test_token")
        monkeypatch.setenv("GITEA_HOST", "gitea.example.com:3000")
        monkeypatch.setenv("LLM_API_KEY", "test_llm_key")
        monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
        # Clear webhook secret (should already be cleared in test env)
        monkeypatch.delenv("PLATFORM_GITHUB_WEBHOOK_SECRET", raising=False)

        from main import app

        with patch("worker.process_code_review") as mock_task:
            mock_task.delay = MagicMock(return_value=MagicMock(id=str(uuid.uuid4())))

            with TestClient(app) as client:
                response = client.post(
                    "/v1/webhook/github",
                    json=github_pr_payload,
                )

        # Should accept without signature when no secret configured
        assert response.status_code == 202
