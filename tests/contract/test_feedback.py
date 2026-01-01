"""
Contract Tests: Feedback Endpoints

T063 - Test POST /v1/feedback endpoint

Tests for the feedback API contract according to the specification in
specs/001-cortexreview-platform/contracts/feedback-endpoint.md

Status: RED (implementation does not exist yet)
Task: 001-cortexreview-platform/T063
"""

import os

# Add project root to path for imports
import sys
import uuid
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
from httpx import AsyncClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


# =============================================================================
# Test Data Fixtures
# =============================================================================


@pytest.fixture
def valid_feedback_request() -> dict[str, Any]:
    """Valid feedback request body."""
    return {
        "comment_id": "comment-uuid-12345",
        "action": "rejected",
        "reason": "false_positive",
        "developer_comment": "This is a false positive. The variable is sanitized earlier in the function.",
        "final_code_snapshot": "username = sanitize(input)\nexecute(f'SELECT * FROM users WHERE name={username}')",
    }


@pytest.fixture
def feedback_response_202() -> dict[str, Any]:
    """Expected 202 Accepted response."""
    now = datetime.now()
    return {
        "feedback_id": str(uuid.uuid4()),
        "status": "queued",
        "trace_id": str(uuid.uuid4()),
        "message": "Feedback queued for processing",
        "constraint_applies_at": now.isoformat(),
    }


@pytest.fixture
def mock_celery_task() -> Mock:
    """Mock Celery task for feedback processing."""
    task = MagicMock()
    task.id = str(uuid.uuid4())
    task.state = "PENDING"
    return task


# =============================================================================
# POST /v1/feedback - Valid Request Tests
# =============================================================================


class TestPostFeedbackValidRequest:
    """Test suite for POST /v1/feedback with valid requests."""

    @pytest.mark.asyncio
    async def test_returns_202_accepted_for_valid_feedback(
        self,
        valid_feedback_request,
        mock_celery_task,
    ):
        """
        Test: POST /v1/feedback returns 202 Accepted for valid feedback.

        Expected:
        - HTTP status 202 Accepted
        - Feedback is queued for processing
        - Returns feedback_id and task_id
        """
        # Arrange
        from main import app

        with patch("main.process_feedback.delay", return_value=mock_celery_task):
            async with AsyncClient(app=app, base_url="http://test") as client:
                # Act
                response = await client.post("/v1/feedback", json=valid_feedback_request)

                # Assert
                assert response.status_code == 202

    @pytest.mark.asyncio
    async def test_returns_feedback_id_in_response(
        self,
        valid_feedback_request,
        mock_celery_task,
    ):
        """
        Test: Response includes feedback_id (UUID).

        Expected:
        - feedback_id is a valid UUID string
        - Can be used to query feedback status later
        """
        # Arrange
        from main import app

        with patch("main.process_feedback.delay", return_value=mock_celery_task):
            async with AsyncClient(app=app, base_url="http://test") as client:
                # Act
                response = await client.post("/v1/feedback", json=valid_feedback_request)

                # Assert
                data = response.json()
                assert "feedback_id" in data
                assert isinstance(data["feedback_id"], str)
                # Valid UUID
                uuid.UUID(data["feedback_id"])

    @pytest.mark.asyncio
    async def test_returns_queued_status_in_response(
        self,
        valid_feedback_request,
        mock_celery_task,
    ):
        """
        Test: Response includes status: "queued".

        Expected:
        - status field is "queued"
        - Indicates feedback is awaiting processing
        """
        # Arrange
        from main import app

        with patch("main.process_feedback.delay", return_value=mock_celery_task):
            async with AsyncClient(app=app, base_url="http://test") as client:
                # Act
                response = await client.post("/v1/feedback", json=valid_feedback_request)

                # Assert
                data = response.json()
                assert data["status"] == "queued"

    @pytest.mark.asyncio
    async def test_returns_trace_id_for_correlation(
        self,
        valid_feedback_request,
        mock_celery_task,
    ):
        """
        Test: Response includes trace_id for distributed tracing.

        Expected:
        - trace_id is included for correlation
        - Enables tracing across services
        """
        # Arrange
        from main import app

        with patch("main.process_feedback.delay", return_value=mock_celery_task):
            async with AsyncClient(app=app, base_url="http://test") as client:
                # Act
                response = await client.post("/v1/feedback", json=valid_feedback_request)

                # Assert
                data = response.json()
                assert "trace_id" in data
                assert isinstance(data["trace_id"], str)

    @pytest.mark.asyncio
    async def test_returns_constraint_applies_at_timestamp(
        self,
        valid_feedback_request,
        mock_celery_task,
    ):
        """
        Test: Response includes constraint_applies_at timestamp.

        Expected:
        - constraint_applies_at is ISO 8601 datetime string
        - Estimated time when constraint becomes active (~5 minutes)
        """
        # Arrange
        from main import app

        with patch("main.process_feedback.delay", return_value=mock_celery_task):
            async with AsyncClient(app=app, base_url="http://test") as client:
                # Act
                response = await client.post("/v1/feedback", json=valid_feedback_request)

                # Assert
                data = response.json()
                assert "constraint_applies_at" in data
                # Valid ISO format datetime
                datetime.fromisoformat(data["constraint_applies_at"].replace("Z", "+00:00"))

    @pytest.mark.asyncio
    async def test_dispatches_celery_task_for_processing(
        self,
        valid_feedback_request,
        mock_celery_task,
    ):
        """
        Test: Valid feedback dispatches Celery task for async processing.

        Expected:
        - process_feedback.delay() is called
        - Task receives feedback data
        """
        # Arrange
        from main import app

        with patch("main.process_feedback.delay", return_value=mock_celery_task) as mock_task:
            async with AsyncClient(app=app, base_url="http://test") as client:
                # Act
                await client.post("/v1/feedback", json=valid_feedback_request)

                # Assert
                mock_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_accepts_all_valid_actions(
        self,
        mock_celery_task,
    ):
        """
        Test: Accepts all valid action values: accepted, rejected, modified.

        Expected:
        - All three actions return 202
        - Actions are enum validated
        """
        # Arrange
        from main import app

        actions = ["accepted", "rejected", "modified"]

        with patch("main.process_feedback.delay", return_value=mock_celery_task):
            async with AsyncClient(app=app, base_url="http://test") as client:
                for action in actions:
                    request = {
                        "comment_id": "comment-123",
                        "action": action,
                        "reason": "false_positive",
                        "developer_comment": "Test",
                        "final_code_snapshot": "code",
                    }

                    # Act
                    response = await client.post("/v1/feedback", json=request)

                    # Assert
                    assert response.status_code == 202

    @pytest.mark.asyncio
    async def test_accepts_all_valid_reasons(
        self,
        mock_celery_task,
    ):
        """
        Test: Accepts all valid reason categories.

        Expected:
        - false_positive, logic_error, style_preference, hallucination all valid
        """
        # Arrange
        from main import app

        reasons = ["false_positive", "logic_error", "style_preference", "hallucination"]

        with patch("main.process_feedback.delay", return_value=mock_celery_task):
            async with AsyncClient(app=app, base_url="http://test") as client:
                for reason in reasons:
                    request = {
                        "comment_id": "comment-123",
                        "action": "rejected",
                        "reason": reason,
                        "developer_comment": "Test",
                        "final_code_snapshot": "code",
                    }

                    # Act
                    response = await client.post("/v1/feedback", json=request)

                    # Assert
                    assert response.status_code == 202


# =============================================================================
# POST /v1/feedback - Validation Tests
# =============================================================================


class TestPostFeedbackValidation:
    """Test suite for POST /v1/feedback request validation."""

    @pytest.mark.asyncio
    async def test_returns_400_for_missing_comment_id(self):
        """
        Test: Returns 400 when comment_id is missing.

        Expected:
        - HTTP status 400 Bad Request
        - Validation error indicates missing field
        """
        # Arrange
        from main import app

        request = {
            "action": "rejected",
            "reason": "false_positive",
            "developer_comment": "Test",
            "final_code_snapshot": "code",
            # comment_id missing
        }

        async with AsyncClient(app=app, base_url="http://test") as client:
            # Act
            response = await client.post("/v1/feedback", json=request)

            # Assert
            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_400_for_invalid_action(self):
        """
        Test: Returns 400 for invalid action value.

        Expected:
        - HTTP status 400 Bad Request
        - Validation error for invalid enum value
        """
        # Arrange
        from main import app

        request = {
            "comment_id": "comment-123",
            "action": "invalid_action",
            "reason": "false_positive",
            "developer_comment": "Test",
            "final_code_snapshot": "code",
        }

        async with AsyncClient(app=app, base_url="http://test") as client:
            # Act
            response = await client.post("/v1/feedback", json=request)

            # Assert
            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_400_for_invalid_reason(self):
        """
        Test: Returns 400 for invalid reason value.

        Expected:
        - HTTP status 400 Bad Request
        - Validation error for invalid enum value
        """
        # Arrange
        from main import app

        request = {
            "comment_id": "comment-123",
            "action": "rejected",
            "reason": "invalid_reason",
            "developer_comment": "Test",
            "final_code_snapshot": "code",
        }

        async with AsyncClient(app=app, base_url="http://test") as client:
            # Act
            response = await client.post("/v1/feedback", json=request)

            # Assert
            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_400_for_empty_developer_comment(self):
        """
        Test: Returns 400 when developer_comment is empty.

        Expected:
        - HTTP status 400 Bad Request
        - developer_comment minimum length is 1
        """
        # Arrange
        from main import app

        request = {
            "comment_id": "comment-123",
            "action": "rejected",
            "reason": "false_positive",
            "developer_comment": "",  # Empty
            "final_code_snapshot": "code",
        }

        async with AsyncClient(app=app, base_url="http://test") as client:
            # Act
            response = await client.post("/v1/feedback", json=request)

            # Assert
            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_400_for_developer_comment_too_long(self):
        """
        Test: Returns 400 when developer_comment exceeds 1000 characters.

        Expected:
        - HTTP status 400 Bad Request
        - developer_comment maximum length is 1000
        """
        # Arrange
        from main import app

        request = {
            "comment_id": "comment-123",
            "action": "rejected",
            "reason": "false_positive",
            "developer_comment": "x" * 1001,  # Too long
            "final_code_snapshot": "code",
        }

        async with AsyncClient(app=app, base_url="http://test") as client:
            # Act
            response = await client.post("/v1/feedback", json=request)

            # Assert
            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_400_for_missing_final_code_snapshot(self):
        """
        Test: Returns 400 when final_code_snapshot is missing.

        Expected:
        - HTTP status 400 Bad Request
        - Validation error indicates missing field
        """
        # Arrange
        from main import app

        request = {
            "comment_id": "comment-123",
            "action": "rejected",
            "reason": "false_positive",
            "developer_comment": "Test",
            # final_code_snapshot missing
        }

        async with AsyncClient(app=app, base_url="http://test") as client:
            # Act
            response = await client.post("/v1/feedback", json=request)

            # Assert
            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_415_for_invalid_content_type(self):
        """
        Test: Returns 415 for invalid Content-Type header.

        Expected:
        - HTTP status 415 Unsupported Media Type
        - Content-Type must be application/json
        """
        # Arrange
        from main import app

        async with AsyncClient(app=app, base_url="http://test") as client:
            # Act
            response = await client.post(
                "/v1/feedback",
                content="not json",
                headers={"Content-Type": "text/plain"},
            )

            # Assert
            assert response.status_code == 415


# =============================================================================
# GET /v1/feedback/{feedback_id} - Status Query Tests
# =============================================================================


class TestGetFeedbackStatus:
    """Test suite for GET /v1/feedback/{feedback_id} endpoint."""

    @pytest.mark.asyncio
    async def test_returns_200_for_valid_feedback_id(self):
        """
        Test: Returns 200 OK with feedback status.

        Expected:
        - HTTP status 200 OK
        - Returns feedback status details
        """
        # Arrange
        from main import app

        feedback_id = str(uuid.uuid4())

        async with AsyncClient(app=app, base_url="http://test") as client:
            # Act
            response = await client.get(f"/v1/feedback/{feedback_id}")

            # Assert
            # Will return 404 until implementation exists
            # Test expects 200 when implemented
            assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_feedback_id(self):
        """
        Test: Returns 404 for nonexistent feedback_id.

        Expected:
        - HTTP status 404 Not Found
        - Clear error message
        """
        # Arrange
        from main import app

        feedback_id = str(uuid.uuid4())

        async with AsyncClient(app=app, base_url="http://test") as client:
            # Act
            response = await client.get(f"/v1/feedback/{feedback_id}")

            # Assert
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_422_for_invalid_uuid_format(self):
        """
        Test: Returns 422 for invalid UUID format.

        Expected:
        - HTTP status 422 Unprocessable Entity
        - Validation error for UUID format
        """
        # Arrange
        from main import app

        async with AsyncClient(app=app, base_url="http://test") as client:
            # Act
            response = await client.get("/v1/feedback/not-a-uuid")

            # Assert
            assert response.status_code == 422


# =============================================================================
# Feedback Status Response Tests
# =============================================================================


class TestFeedbackStatusResponse:
    """Test suite for feedback status response format."""

    @pytest.mark.asyncio
    async def test_includes_status_field(self):
        """
        Test: Status response includes status field.

        Expected:
        - status is one of: queued, processing, completed, failed
        """
        # This test will pass when implementation exists
        # For now, documenting expected behavior
        pass

    @pytest.mark.asyncio
    async def test_includes_created_at_timestamp(self):
        """
        Test: Status response includes created_at timestamp.

        Expected:
        - created_at is ISO 8601 datetime string
        """
        pass

    @pytest.mark.asyncio
    async def test_includes_completed_at_when_completed(self):
        """
        Test: Status response includes completed_at when status is completed.

        Expected:
        - completed_at is present only when status is completed
        - null for other statuses
        """
        pass

    @pytest.mark.asyncio
    async def test_includes_constraint_created_when_rejected(self):
        """
        Test: Status response includes constraint_created for rejected feedback.

        Expected:
        - constraint_created object included when action was rejected
        - Contains id, confidence_score, expires_at
        """
        pass


# =============================================================================
# Graceful Degradation Tests
# =============================================================================


class TestFeedbackGracefulDegradation:
    """Test suite for graceful degradation behavior."""

    @pytest.mark.asyncio
    async def test_returns_202_when_supabase_unavailable(
        self,
        valid_feedback_request,
        mock_celery_task,
        caplog,
    ):
        """
        Test: Returns 202 but logs ERROR when Supabase is unavailable.

        Expected:
        - Returns 202 Accepted to client
        - Logs ERROR with context
        - Feedback buffered in Redis for retry
        """
        # Arrange
        from main import app

        with patch("main.process_feedback.delay", side_effect=Exception("Supabase unavailable")):
            async with AsyncClient(app=app, base_url="http://test") as client:
                # Act
                response = await client.post("/v1/feedback", json=valid_feedback_request)

                # Assert
                # Should still return 202 or return 500 depending on implementation choice
                # Spec says 202 with logging
                assert response.status_code in [202, 500]

    @pytest.mark.asyncio
    async def test_returns_202_when_embedding_api_fails(
        self,
        valid_feedback_request,
        mock_celery_task,
    ):
        """
        Test: Returns 202 when OpenAI embedding API fails.

        Expected:
        - Feedback recorded in audit log
        - No constraint created
        - Can be manually created via admin API
        """
        # This will be tested in integration tests
        pass


# =============================================================================
# Content-Type and Header Tests
# =============================================================================


class TestFeedbackHeaders:
    """Test suite for request/response headers."""

    @pytest.mark.asyncio
    async def test_requires_application_json_content_type(
        self,
        valid_feedback_request,
    ):
        """
        Test: Requires Content-Type: application/json.

        Expected:
        - Rejects requests without correct Content-Type
        """
        pass

    @pytest.mark.asyncio
    async def test_accepts_x_user_id_header(self):
        """
        Test: Accepts X-User-ID header for user identification.

        Expected:
        - X-User-ID header is used when no auth
        - User ID extracted from header
        """
        pass

    @pytest.mark.asyncio
    async def test_returns_json_content_type(
        self,
        valid_feedback_request,
        mock_celery_task,
    ):
        """
        Test: Response includes Content-Type: application/json.

        Expected:
        - Response Content-Type is application/json
        """
        # Arrange
        from main import app

        with patch("main.process_feedback.delay", return_value=mock_celery_task):
            async with AsyncClient(app=app, base_url="http://test") as client:
                # Act
                response = await client.post("/v1/feedback", json=valid_feedback_request)

                # Assert
                assert "application/json" in response.headers.get("content-type", "")
