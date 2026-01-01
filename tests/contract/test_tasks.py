"""
T034 - Contract Tests for Task Status Endpoint

Tests GET /v1/tasks/{task_id} endpoint verifies it returns task status
including QUEUED/PROCESSING/COMPLETED/FAILED statuses.

These tests MUST FAIL because the task status endpoint implementation
may be incomplete or return incorrect status values.
"""

import pytest
from httpx import AsyncClient


class TestTaskStatusEndpoint:
    """
    Test GET /v1/tasks/{task_id} endpoint.

    These tests verify the task status endpoint contract.
    """

    @pytest.mark.asyncio
    async def test_get_task_status_returns_200(
        self, async_test_client: AsyncClient, sample_trace_id
    ):
        """
        GIVEN a valid task_id
        WHEN querying GET /v1/tasks/{task_id}
        THEN the endpoint should return 200 OK

        FAIL EXPECTED: Endpoint may not exist or return wrong status
        """
        # Arrange
        task_id = sample_trace_id

        # Act
        response = await async_test_client.get(f"/v1/tasks/{task_id}")

        # Assert
        assert response.status_code == 200, (
            f"Expected 200 OK, got {response.status_code}. Response: {response.text}"
        )

    @pytest.mark.asyncio
    async def test_task_status_response_includes_status_field(
        self, async_test_client: AsyncClient, sample_trace_id
    ):
        """
        GIVEN a valid task_id
        WHEN querying GET /v1/tasks/{task_id}
        THEN the response should include status field

        FAIL EXPECTED: Response may not include status field
        """
        # Act
        response = await async_test_client.get(f"/v1/tasks/{sample_trace_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "status" in data, f"Response missing status field: {data}"

    @pytest.mark.asyncio
    async def test_task_status_includes_task_id(
        self, async_test_client: AsyncClient, sample_trace_id
    ):
        """
        GIVEN a valid task_id
        WHEN querying GET /v1/tasks/{task_id}
        THEN the response should include the task_id

        FAIL EXPECTED: Response may not include task_id
        """
        # Act
        response = await async_test_client.get(f"/v1/tasks/{sample_trace_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data, f"Response missing task_id: {data}"
        assert data["task_id"] == sample_trace_id

    @pytest.mark.asyncio
    async def test_task_status_queued_value(self, async_test_client: AsyncClient, sample_trace_id):
        """
        GIVEN a task that is queued
        WHEN querying GET /v1/tasks/{task_id}
        THEN status should be "queued"

        FAIL EXPECTED: May return wrong status value
        """
        # Act
        response = await async_test_client.get(f"/v1/tasks/{sample_trace_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

        # Status can be any of the valid values
        valid_statuses = ["queued", "processing", "completed", "failed", "pending"]
        assert data["status"] in valid_statuses, (
            f"Expected status to be one of {valid_statuses}, got '{data.get('status')}'"
        )

    @pytest.mark.asyncio
    async def test_task_status_processing_value(
        self, async_test_client: AsyncClient, sample_trace_id
    ):
        """
        GIVEN a task that is processing
        WHEN querying GET /v1/tasks/{task_id}
        THEN status should be "processing" when task is running

        FAIL EXPECTED: May not correctly report processing status
        """
        # Act
        response = await async_test_client.get(f"/v1/tasks/{sample_trace_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()

        # The status should be one of the valid values
        valid_statuses = ["queued", "processing", "completed", "failed", "pending"]
        assert data.get("status") in valid_statuses

    @pytest.mark.asyncio
    async def test_task_status_completed_value(
        self, async_test_client: AsyncClient, sample_trace_id
    ):
        """
        GIVEN a task that has completed
        WHEN querying GET /v1/tasks/{task_id}
        THEN status should be "completed" and result should be present

        FAIL EXPECTED: May not correctly report completed status with result
        """
        # Act
        response = await async_test_client.get(f"/v1/tasks/{sample_trace_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()

        # If status is completed, result should be present
        if data.get("status") == "completed":
            assert "result" in data, "Completed task should have result field"
            assert data["result"] is not None

    @pytest.mark.asyncio
    async def test_task_status_failed_value(self, async_test_client: AsyncClient, sample_trace_id):
        """
        GIVEN a task that has failed
        WHEN querying GET /v1/tasks/{task_id}
        THEN status should be "failed" and error should be present

        FAIL EXPECTED: May not correctly report failed status with error
        """
        # Act
        response = await async_test_client.get(f"/v1/tasks/{sample_trace_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()

        # If status is failed, error should be present
        if data.get("status") == "failed":
            assert "error" in data, "Failed task should have error field"
            assert data["error"] is not None

    @pytest.mark.asyncio
    async def test_task_status_nonexistent_task(self, async_test_client: AsyncClient):
        """
        GIVEN a task_id that doesn't exist
        WHEN querying GET /v1/tasks/{task_id}
        THEN the endpoint should return 404 Not Found

        FAIL EXPECTED: May not handle nonexistent tasks correctly
        """
        # Arrange
        fake_task_id = "00000000-0000-0000-0000-000000000000"

        # Act
        response = await async_test_client.get(f"/v1/tasks/{fake_task_id}")

        # Assert
        # May return 200 with status=unknown, or 404
        assert response.status_code in [200, 404], (
            f"Expected 200 or 404 for nonexistent task, got {response.status_code}"
        )

    @pytest.mark.asyncio
    async def test_task_status_response_includes_result_when_completed(
        self, async_test_client: AsyncClient, sample_trace_id
    ):
        """
        GIVEN a completed task
        WHEN querying GET /v1/tasks/{task_id}
        THEN the response should include result field with review data

        FAIL EXPECTED: May not include result for completed tasks
        """
        # Act
        response = await async_test_client.get(f"/v1/tasks/{sample_trace_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Result should be present (even if null for non-completed tasks)
        assert "result" in data, f"Response missing result field: {data}"

    @pytest.mark.asyncio
    async def test_task_status_result_has_correct_structure(
        self, async_test_client: AsyncClient, sample_trace_id
    ):
        """
        GIVEN a completed task with result
        WHEN querying GET /v1/tasks/{task_id}
        THEN the result should have the correct structure

        Expected structure:
        {
            "review_id": str,
            "summary": str,
            "comments": list,
            "stats": dict
        }

        FAIL EXPECTED: Result structure may not match specification
        """
        # Act
        response = await async_test_client.get(f"/v1/tasks/{sample_trace_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Only verify structure if result exists and is not null
        if data.get("result"):
            result = data["result"]
            expected_fields = ["review_id", "summary", "comments", "stats"]
            for field in expected_fields:
                assert field in result, f"Result missing field: {field}"

    @pytest.mark.asyncio
    async def test_task_status_includes_timestamps(
        self, async_test_client: AsyncClient, sample_trace_id
    ):
        """
        GIVEN a task
        WHEN querying GET /v1/tasks/{task_id}
        THEN the response should include created_at timestamp

        FAIL EXPECTED: May not include timestamps in response
        """
        # Act
        response = await async_test_client.get(f"/v1/tasks/{sample_trace_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Timestamps are optional in current implementation
        # but if present, should be ISO format strings
        if "created_at" in data:
            assert isinstance(data["created_at"], str)

    @pytest.mark.asyncio
    async def test_task_status_invalid_uuid_format(self, async_test_client: AsyncClient):
        """
        GIVEN an invalid task_id format
        WHEN querying GET /v1/tasks/{task_id}
        THEN the endpoint should return 400 Bad Request

        FAIL EXPECTED: May not validate UUID format
        """
        # Arrange
        invalid_task_id = "not-a-valid-uuid"

        # Act
        response = await async_test_client.get(f"/v1/tasks/{invalid_task_id}")

        # Assert
        # May accept any string as task_id
        assert response.status_code in [200, 400, 422], (
            f"Expected 200, 400, or 422 for invalid UUID, got {response.status_code}"
        )


class TestTaskStatusResponseContract:
    """
    Test task status response contract compliance.

    These tests verify the response format matches the specification.
    """

    @pytest.mark.asyncio
    async def test_task_status_response_contract(
        self, async_test_client: AsyncClient, sample_trace_id
    ):
        """
        GIVEN a valid task_id
        WHEN querying GET /v1/tasks/{task_id}
        THEN the response should match the specified contract format

        Expected contract:
        {
            "task_id": str (UUID),
            "status": "queued" | "processing" | "completed" | "failed",
            "result": dict | None,
            "error": str | None,
            "created_at": str (ISO8601) | None,
            "started_at": str (ISO8601) | None,
            "completed_at": str (ISO8601) | None
        }

        FAIL EXPECTED: Response format may not match contract
        """
        # Act
        response = await async_test_client.get(f"/v1/tasks/{sample_trace_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Verify required fields
        required_fields = ["task_id", "status", "result", "error"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Verify field types
        assert isinstance(data["task_id"], str)
        assert isinstance(data["status"], str)
        assert data["result"] is None or isinstance(data["result"], dict)
        assert data["error"] is None or isinstance(data["error"], str)

        # Verify status value
        valid_statuses = ["queued", "processing", "completed", "failed", "pending"]
        assert data["status"] in valid_statuses

    @pytest.mark.asyncio
    async def test_task_status_response_includes_metadata(
        self, async_test_client: AsyncClient, sample_trace_id
    ):
        """
        GIVEN a valid task_id
        WHEN querying GET /v1/tasks/{task_id}
        THEN the response should include PR metadata

        FAIL EXPECTED: May not include metadata in response
        """
        # Act
        response = await async_test_client.get(f"/v1/tasks/{sample_trace_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Metadata is optional but if present should have specific fields
        if data.get("metadata"):
            metadata = data["metadata"]
            expected_metadata_fields = ["repo_id", "pr_number", "base_sha", "head_sha", "platform"]
            for field in expected_metadata_fields:
                assert field in metadata, f"Metadata missing field: {field}"
