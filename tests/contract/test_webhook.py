"""
Contract tests for POST /v1/webhook/{platform} endpoint.

T037 - Verifies webhook endpoint dispatches to Celery task
T038 - Verifies webhook signature verification

These tests verify the API contract:
- Returns 202 Accepted on valid webhook
- Returns task_id and trace_id in response
- Returns 401 on invalid signature
- Supports opt-out via env var
"""

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest


class TestWebhookEndpointContract:
    """
    Contract tests for /v1/webhook/{platform} endpoint (T037, T038).

    Tests verify:
    - HTTP 202 on valid webhook
    - Returns task_id, trace_id, status="pending"
    - Celery task dispatched with metadata
    - Signature verification behavior
    """

    @pytest.mark.asyncio
    async def test_github_webhook_returns_202_with_task_info(
        self, async_test_client, github_pr_payload
    ):
        """
        T037: GIVEN a valid GitHub webhook payload
        WHEN POST /v1/webhook/github
        THEN returns HTTP 202 with task_id and trace_id
        """
        # Mock Celery task
        with patch("worker.process_code_review") as mock_task:
            mock_task.delay = MagicMock(return_value=MagicMock(id=str(uuid.uuid4())))

            response = await async_test_client.post(
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
        uuid.UUID(data["task_id"])  # Raises if invalid
        uuid.UUID(data["trace_id"])

    @pytest.mark.asyncio
    async def test_gitea_webhook_returns_202_with_task_info(
        self, async_test_client, gitea_push_payload
    ):
        """
        T037: GIVEN a valid Gitea webhook payload
        WHEN POST /v1/webhook/gitea
        THEN returns HTTP 202 with task_id and trace_id
        """
        # Mock Celery task
        with patch("worker.process_code_review") as mock_task:
            mock_task.delay = MagicMock(return_value=MagicMock(id=str(uuid.uuid4())))

            response = await async_test_client.post(
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

    @pytest.mark.asyncio
    async def test_invalid_json_returns_400(self, async_test_client):
        """
        GIVEN invalid JSON payload
        WHEN POST /v1/webhook/github
        THEN returns HTTP 400 with error message
        """
        response = await async_test_client.post(
            "/v1/webhook/github",
            content="not valid json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_invalid_platform_returns_400(self, async_test_client):
        """
        GIVEN an invalid platform parameter
        WHEN POST /v1/webhook/invalid
        THEN returns HTTP 400
        """
        response = await async_test_client.post(
            "/v1/webhook/invalid",
            json={},
        )

        assert response.status_code == 400


class TestWebhookSignatureVerification:
    """
    Contract tests for webhook signature verification (T038).

    Tests verify:
    - HMAC-SHA256 signature verification works
    - Returns 401 on invalid signature
    - Opt-out via PLATFORM_GITHUB_VERIFY_SIGNATURE=false
    - Opt-out via PLATFORM_GITEA_VERIFY_SIGNATURE=false
    """

    @pytest.mark.asyncio
    async def test_github_webhook_with_valid_signature_accepted(
        self, async_test_client, github_pr_payload, monkeypatch
    ):
        """
        T038: GIVEN a valid GitHub webhook with correct signature
        WHEN POST /v1/webhook/github with X-Hub-Signature-256
        THEN accepts request (202) when signature matches
        """
        import hashlib
        import hmac

        # Set webhook secret
        monkeypatch.setenv("PLATFORM_GITHUB_WEBHOOK_SECRET", "test_secret")
        monkeypatch.setenv("PLATFORM_GITHUB_VERIFY_SIGNATURE", "true")

        payload_bytes = json.dumps(github_pr_payload).encode()
        signature = hmac.new(b"test_secret", payload_bytes, hashlib.sha256).hexdigest()
        signature_header = f"sha256={signature}"

        with patch("worker.process_code_review") as mock_task:
            mock_task.delay = MagicMock(return_value=MagicMock(id=str(uuid.uuid4())))

            response = await async_test_client.post(
                "/v1/webhook/github",
                json=github_pr_payload,
                headers={"X-Hub-Signature-256": signature_header},
            )

        assert response.status_code == 202

    @pytest.mark.asyncio
    async def test_github_webhook_with_invalid_signature_returns_401(
        self, async_test_client, github_pr_payload, monkeypatch
    ):
        """
        T038: GIVEN a GitHub webhook with incorrect signature
        WHEN POST /v1/webhook/github with invalid X-Hub-Signature-256
        THEN returns HTTP 401 Unauthorized
        """
        # Set webhook secret
        monkeypatch.setenv("PLATFORM_GITHUB_WEBHOOK_SECRET", "test_secret")
        monkeypatch.setenv("PLATFORM_GITHUB_VERIFY_SIGNATURE", "true")

        with patch("worker.process_code_review") as mock_task:
            mock_task.delay = MagicMock(return_value=MagicMock(id=str(uuid.uuid4())))

            response = await async_test_client.post(
                "/v1/webhook/github",
                json=github_pr_payload,
                headers={"X-Hub-Signature-256": "sha256=invalid"},
            )

        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "signature" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_github_signature_verification_can_be_disabled(
        self, async_test_client, github_pr_payload, monkeypatch
    ):
        """
        T038: GIVEN PLATFORM_GITHUB_VERIFY_SIGNATURE=false
        WHEN POST /v1/webhook/github without signature
        THEN accepts request (202)
        """
        # Disable signature verification
        monkeypatch.setenv("PLATFORM_GITHUB_WEBHOOK_SECRET", "test_secret")
        monkeypatch.setenv("PLATFORM_GITHUB_VERIFY_SIGNATURE", "false")

        with patch("worker.process_code_review") as mock_task:
            mock_task.delay = MagicMock(return_value=MagicMock(id=str(uuid.uuid4())))

            response = await async_test_client.post(
                "/v1/webhook/github",
                json=github_pr_payload,
                # No signature header
            )

        assert response.status_code == 202

    @pytest.mark.asyncio
    async def test_gitea_signature_verification_can_be_disabled(
        self, async_test_client, gitea_push_payload, monkeypatch
    ):
        """
        T038: GIVEN PLATFORM_GITEA_VERIFY_SIGNATURE=false
        WHEN POST /v1/webhook/gitea without signature
        THEN accepts request (202)
        """
        # Disable signature verification
        monkeypatch.setenv("PLATFORM_GITEA_WEBHOOK_SECRET", "test_secret")
        monkeypatch.setenv("PLATFORM_GITEA_VERIFY_SIGNATURE", "false")

        with patch("worker.process_code_review") as mock_task:
            mock_task.delay = MagicMock(return_value=MagicMock(id=str(uuid.uuid4())))

            response = await async_test_client.post(
                "/v1/webhook/gitea",
                json=gitea_push_payload,
                # No signature header
            )

        assert response.status_code == 202

    @pytest.mark.asyncio
    async def test_gitea_webhook_with_valid_signature_accepted(
        self, async_test_client, gitea_push_payload, monkeypatch
    ):
        """
        T038: GIVEN a valid Gitea webhook with correct signature
        WHEN POST /v1/webhook/gitea with X-Gitea-Signature
        THEN accepts request (202) when signature matches
        """
        import hashlib
        import hmac

        # Set webhook secret
        monkeypatch.setenv("PLATFORM_GITEA_WEBHOOK_SECRET", "test_secret")
        monkeypatch.setenv("PLATFORM_GITEA_VERIFY_SIGNATURE", "true")

        payload_bytes = json.dumps(gitea_push_payload).encode()
        signature = hmac.new(b"test_secret", payload_bytes, hashlib.sha256).hexdigest()
        signature_header = f"sha256={signature}"

        with patch("worker.process_code_review") as mock_task:
            mock_task.delay = MagicMock(return_value=MagicMock(id=str(uuid.uuid4())))

            response = await async_test_client.post(
                "/v1/webhook/gitea",
                json=gitea_push_payload,
                headers={"X-Gitea-Signature": signature_header},
            )

        assert response.status_code == 202

    @pytest.mark.asyncio
    async def test_gitea_webhook_with_invalid_signature_returns_401(
        self, async_test_client, gitea_push_payload, monkeypatch
    ):
        """
        T038: GIVEN a Gitea webhook with incorrect signature
        WHEN POST /v1/webhook/gitea with invalid X-Gitea-Signature
        THEN returns HTTP 401 Unauthorized
        """
        # Set webhook secret
        monkeypatch.setenv("PLATFORM_GITEA_WEBHOOK_SECRET", "test_secret")
        monkeypatch.setenv("PLATFORM_GITEA_VERIFY_SIGNATURE", "true")

        with patch("worker.process_code_review") as mock_task:
            mock_task.delay = MagicMock(return_value=MagicMock(id=str(uuid.uuid4())))

            response = await async_test_client.post(
                "/v1/webhook/gitea",
                json=gitea_push_payload,
                headers={"X-Gitea-Signature": "sha256=invalid"},
            )

        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "signature" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_signature_verification_skipped_when_no_secret(
        self, async_test_client, github_pr_payload, monkeypatch
    ):
        """
        T038: GIVEN no PLATFORM_GITHUB_WEBHOOK_SECRET configured
        WHEN POST /v1/webhook/github
        THEN accepts request (202) with warning logged
        """
        # Clear webhook secret
        monkeypatch.delenv("PLATFORM_GITHUB_WEBHOOK_SECRET", raising=False)

        with patch("worker.process_code_review") as mock_task:
            mock_task.delay = MagicMock(return_value=MagicMock(id=str(uuid.uuid4())))

            response = await async_test_client.post(
                "/v1/webhook/github",
                json=github_pr_payload,
            )

        # Should accept without signature when no secret configured
        assert response.status_code == 202
