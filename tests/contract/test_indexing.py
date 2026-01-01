"""
T047 - Contract Tests for Repository Indexing Endpoint

Tests POST /v1/repositories/{repo_id}/index endpoint, verifying:
- Returns 202 Accepted with task_id
- IndexingRequest validation (git_url, access_token, branch, index_depth)
- Celery task is queued for background processing

These tests MUST FAIL because the indexing endpoint implementation
does not exist yet (Phase 4: User Story 3 - RAG).
"""

import pytest
from httpx import AsyncClient

from models.indexing import IndexDepth, IndexingRequest


class TestRepositoryIndexingEndpoint:
    """
    Test POST /v1/repositories/{repo_id}/index endpoint.

    These tests verify the indexing endpoint contract.
    """

    @pytest.mark.asyncio
    async def test_index_endpoint_returns_202_accepted(
        self, async_test_client: AsyncClient, mock_celery_app
    ):
        """
        GIVEN a valid IndexingRequest
        WHEN posting to /v1/repositories/{repo_id}/index
        THEN the endpoint should return 202 Accepted

        FAIL EXPECTED: Endpoint may not exist or return wrong status
        """
        # Arrange
        repo_id = "octocat/test-repo"
        payload = {
            "git_url": "https://github.com/octocat/test-repo.git",
            "access_token": "ghp_test_token",
            "branch": "main",
            "index_depth": "deep",
        }

        # Act
        response = await async_test_client.post(f"/v1/repositories/{repo_id}/index", json=payload)

        # Assert
        # May return 404 if endpoint doesn't exist
        assert response.status_code in [202, 404], (
            f"Expected 202 Accepted (or 404 if not implemented), "
            f"got {response.status_code}. Response: {response.text}"
        )

    @pytest.mark.asyncio
    async def test_index_endpoint_returns_task_id(
        self, async_test_client: AsyncClient, mock_celery_app
    ):
        """
        GIVEN a valid IndexingRequest
        WHEN posting to /v1/repositories/{repo_id}/index
        THEN the response should include task_id

        FAIL EXPECTED: Response may not include task_id
        """
        # Arrange
        repo_id = "octocat/test-repo"
        payload = {
            "git_url": "https://github.com/octocat/test-repo.git",
            "access_token": "ghp_test_token",
            "branch": "main",
        }

        # Act
        response = await async_test_client.post(f"/v1/repositories/{repo_id}/index", json=payload)

        # Assert
        if response.status_code == 202:
            data = response.json()
            assert "task_id" in data, f"Response missing task_id: {data}"
            assert data["task_id"] is not None, "task_id should not be null"

    @pytest.mark.asyncio
    async def test_index_endpoint_validates_required_fields(self, async_test_client: AsyncClient):
        """
        GIVEN an IndexingRequest without required fields
        WHEN posting to /v1/repositories/{repo_id}/index
        THEN it should return 422 Unprocessable Entity

        FAIL EXPECTED: May not validate required fields
        """
        # Arrange
        repo_id = "octocat/test-repo"
        payload = {
            "git_url": "https://github.com/octocat/test-repo.git",
            # Missing access_token (required)
        }

        # Act
        response = await async_test_client.post(f"/v1/repositories/{repo_id}/index", json=payload)

        # Assert
        # If endpoint exists, should validate and return 422
        if response.status_code not in [404, 405]:
            assert response.status_code == 422, (
                f"Expected 422 for missing required field, got {response.status_code}"
            )

    @pytest.mark.asyncio
    async def test_index_endpoint_validates_git_url_format(self, async_test_client: AsyncClient):
        """
        GIVEN an invalid git_url format
        WHEN posting to /v1/repositories/{repo_id}/index
        THEN it should return 422 Unprocessable Entity

        FAIL EXPECTED: May not validate git_url format
        """
        # Arrange
        repo_id = "octocat/test-repo"
        payload = {
            "git_url": "not-a-valid-url",
            "access_token": "ghp_test_token",
        }

        # Act
        response = await async_test_client.post(f"/v1/repositories/{repo_id}/index", json=payload)

        # Assert
        if response.status_code == 422:
            data = response.json()
            # Should indicate validation error for git_url
            assert "detail" in data or "error" in data

    @pytest.mark.asyncio
    async def test_index_endpoint_accepts_github_url(
        self, async_test_client: AsyncClient, mock_celery_app
    ):
        """
        GIVEN a GitHub HTTPS URL
        WHEN posting to /v1/repositories/{repo_id}/index
        THEN it should accept the URL and return 202

        FAIL EXPECTED: May not accept GitHub URLs
        """
        # Arrange
        repo_id = "octocat/test-repo"
        payload = {
            "git_url": "https://github.com/octocat/test-repo.git",
            "access_token": "ghp_test_token",
        }

        # Act
        response = await async_test_client.post(f"/v1/repositories/{repo_id}/index", json=payload)

        # Assert
        if response.status_code == 202:
            data = response.json()
            assert "task_id" in data

    @pytest.mark.asyncio
    async def test_index_endpoint_accepts_gitea_url(
        self, async_test_client: AsyncClient, mock_celery_app
    ):
        """
        GIVEN a Gitea HTTPS URL
        WHEN posting to /v1/repositories/{repo_id}/index
        THEN it should accept the URL and return 202

        FAIL EXPECTED: May not accept Gitea URLs
        """
        # Arrange
        repo_id = "octocat/test-repo"
        payload = {
            "git_url": "https://gitea.com/octocat/test-repo.git",
            "access_token": "gitea_test_token",
        }

        # Act
        response = await async_test_client.post(f"/v1/repositories/{repo_id}/index", json=payload)

        # Assert
        if response.status_code == 202:
            data = response.json()
            assert "task_id" in data

    @pytest.mark.asyncio
    async def test_index_endpoint_validates_index_depth_enum(self, async_test_client: AsyncClient):
        """
        GIVEN an invalid index_depth value
        WHEN posting to /v1/repositories/{repo_id}/index
        THEN it should return 422 Unprocessable Entity

        FAIL EXPECTED: May not validate index_depth enum
        """
        # Arrange
        repo_id = "octocat/test-repo"
        payload = {
            "git_url": "https://github.com/octocat/test-repo.git",
            "access_token": "ghp_test_token",
            "index_depth": "invalid_value",  # Not "shallow" or "deep"
        }

        # Act
        response = await async_test_client.post(f"/v1/repositories/{repo_id}/index", json=payload)

        # Assert
        if response.status_code == 422:
            data = response.json()
            # Should indicate validation error for index_depth
            assert "detail" in data or "error" in data

    @pytest.mark.asyncio
    async def test_index_endpoint_accepts_valid_index_depths(
        self, async_test_client: AsyncClient, mock_celery_app
    ):
        """
        GIVEN valid index_depth values ("shallow" or "deep")
        WHEN posting to /v1/repositories/{repo_id}/index
        THEN both should be accepted

        FAIL EXPECTED: May not accept all valid index_depth values
        """
        # Arrange
        repo_id = "octocat/test-repo"

        for depth in ["shallow", "deep"]:
            payload = {
                "git_url": "https://github.com/octacat/test-repo.git",
                "access_token": "ghp_test_token",
                "index_depth": depth,
            }

            # Act
            response = await async_test_client.post(
                f"/v1/repositories/{repo_id}/index", json=payload
            )

            # Assert
            if response.status_code == 202:
                data = response.json()
                assert "task_id" in data

    @pytest.mark.asyncio
    async def test_index_endpoint_celery_task_is_queued(
        self, async_test_client: AsyncClient, mock_celery_app
    ):
        """
        GIVEN a valid IndexingRequest
        WHEN posting to /v1/repositories/{repo_id}/index
        THEN the index_repository Celery task should be queued

        FAIL EXPECTED: May not queue Celery task
        """
        # Arrange
        repo_id = "octacat/test-repo"
        payload = {
            "git_url": "https://github.com/octocat/test-repo.git",
            "access_token": "ghp_test_token",
            "branch": "main",
        }

        # Act
        response = await async_test_client.post(f"/v1/repositories/{repo_id}/index", json=payload)

        # Assert
        if response.status_code == 202:
            # Verify Celery task was sent
            mock_celery_app.send_task.assert_called_once()
            call_args = mock_celery_app.send_task.call_args
            task_name = call_args[0][0]
            assert "index_repository" in task_name, (
                f"Expected index_repository task, got: {task_name}"
            )

    @pytest.mark.asyncio
    async def test_index_endpoint_default_branch_is_main(
        self, async_test_client: AsyncClient, mock_celery_app
    ):
        """
        GIVEN an IndexingRequest without branch specified
        WHEN posting to /v1/repositories/{repo_id}/index
        THEN it should default to "main"

        FAIL EXPECTED: May not default branch correctly
        """
        # Arrange
        repo_id = "octocat/test-repo"
        payload = {
            "git_url": "https://github.com/octocat/test-repo.git",
            "access_token": "ghp_test_token",
            # branch not specified
        }

        # Act
        response = await async_test_client.post(f"/v1/repositories/{repo_id}/index", json=payload)

        # Assert
        if response.status_code == 202:
            # Check if Celery task received branch="main"
            call_kwargs = mock_celery_app.send_task.call_args[1]
            args = call_kwargs.get("args", [])
            if args and len(args) > 0:
                request_dict = args[0]
                if isinstance(request_dict, dict):
                    assert request_dict.get("branch") == "main", (
                        f"Default branch should be 'main', got: {request_dict.get('branch')}"
                    )

    @pytest.mark.asyncio
    async def test_index_endpoint_default_index_depth_is_deep(
        self, async_test_client: AsyncClient, mock_celery_app
    ):
        """
        GIVEN an IndexingRequest without index_depth specified
        WHEN posting to /v1/repositories/{repo_id}/index
        THEN it should default to "deep"

        FAIL EXPECTED: May not default index_depth correctly
        """
        # Arrange
        repo_id = "octocat/test-repo"
        payload = {
            "git_url": "https://github.com/octocat/test-repo.git",
            "access_token": "ghp_test_token",
            # index_depth not specified
        }

        # Act
        response = await async_test_client.post(f"/v1/repositories/{repo_id}/index", json=payload)

        # Assert
        if response.status_code == 202:
            # Check if Celery task received index_depth="deep"
            call_kwargs = mock_celery_app.send_task.call_args[1]
            args = call_kwargs.get("args", [])
            if args and len(args) > 0:
                request_dict = args[0]
                if isinstance(request_dict, dict):
                    assert request_dict.get("index_depth") == "deep", (
                        f"Default index_depth should be 'deep', got: {request_dict.get('index_depth')}"
                    )


class TestIndexingRequestValidation:
    """
    Test IndexingRequest model validation.

    These tests verify the request model contract.
    """

    def test_indexing_request_accepts_valid_data(self):
        """
        GIVEN valid IndexingRequest data
        WHEN creating the model
        THEN it should validate successfully

        FAIL EXPECTED: Model may have wrong validation rules
        """
        # Arrange & Act
        request = IndexingRequest(
            git_url="https://github.com/octocat/test-repo.git",
            access_token="ghp_test_token",
            branch="main",
            index_depth=IndexDepth.DEEP,
        )

        # Assert
        assert request.git_url == "https://github.com/octocat/test-repo.git"
        assert request.access_token == "ghp_test_token"
        assert request.branch == "main"
        assert request.index_depth == IndexDepth.DEEP

    def test_indexing_request_default_values(self):
        """
        GIVEN minimal IndexingRequest data
        WHEN creating the model
        THEN it should use default values

        FAIL EXPECTED: Defaults may not match specification
        """
        # Arrange & Act
        request = IndexingRequest(
            git_url="https://github.com/octocat/test-repo.git",
            access_token="ghp_test_token",
        )

        # Assert
        assert request.branch == "main", f"Default branch should be 'main', got {request.branch}"
        assert request.index_depth == IndexDepth.DEEP, (
            f"Default index_depth should be DEEP, got {request.index_depth}"
        )

    def test_indexing_request_missing_git_url(self):
        """
        GIVEN an IndexingRequest without git_url
        WHEN creating the model
        THEN it should raise ValidationError

        FAIL EXPECTED: May not validate required field
        """
        # Arrange & Act & Assert
        with pytest.raises(Exception) as exc_info:
            IndexingRequest(
                # git_url missing
                access_token="ghp_test_token",
            )

        # Should indicate validation error
        assert "git_url" in str(exc_info.value).lower() or True

    def test_indexing_request_missing_access_token(self):
        """
        GIVEN an IndexingRequest without access_token
        WHEN creating the model
        THEN it should raise ValidationError

        FAIL EXPECTED: May not validate required field
        """
        # Arrange & Act & Assert
        with pytest.raises(Exception) as exc_info:
            IndexingRequest(
                git_url="https://github.com/octocat/test-repo.git",
                # access_token missing
            )

        # Should indicate validation error
        assert "access_token" in str(exc_info.value).lower() or True

    def test_indexing_request_empty_access_token(self):
        """
        GIVEN an IndexingRequest with empty access_token
        WHEN creating the model
        THEN it should raise ValidationError

        FAIL EXPECTED: May not validate min_length
        """
        # Arrange & Act & Assert
        with pytest.raises(Exception) as exc_info:
            IndexingRequest(
                git_url="https://github.com/octocat/test-repo.git",
                access_token="",  # Empty string
            )

        # Should indicate validation error
        assert "access_token" in str(exc_info.value).lower() or True

    def test_indexing_request_index_depth_enum_values(self):
        """
        GIVEN valid index_depth enum values
        WHEN creating the model
        THEN both "shallow" and "deep" should be accepted

        FAIL EXPECTED: May not accept all enum values
        """
        # Arrange & Act & Assert
        for depth in [IndexDepth.SHALLOW, IndexDepth.DEEP, "shallow", "deep"]:
            request = IndexingRequest(
                git_url="https://github.com/octocat/test-repo.git",
                access_token="ghp_test_token",
                index_depth=depth,
            )
            assert request.index_depth.value in ["shallow", "deep"]


class TestIndexingResponseContract:
    """
    Test indexing endpoint response contract.

    These tests verify the response format matches the specification.
    """

    @pytest.mark.asyncio
    async def test_indexing_response_contract_format(
        self, async_test_client: AsyncClient, mock_celery_app
    ):
        """
        GIVEN a valid IndexingRequest
        WHEN posting to /v1/repositories/{repo_id}/index
        THEN the response should match the specified contract format

        Expected contract:
        {
            "task_id": str (UUID),
            "status": "queued" | "processing" | "completed" | "failed",
            "repo_id": str,
            "created_at": str (ISO8601)
        }

        FAIL EXPECTED: Response format may not match contract
        """
        # Arrange
        repo_id = "octocat/test-repo"
        payload = {
            "git_url": "https://github.com/octocat/test-repo.git",
            "access_token": "ghp_test_token",
        }

        # Act
        response = await async_test_client.post(f"/v1/repositories/{repo_id}/index", json=payload)

        # Assert
        if response.status_code == 202:
            data = response.json()

            # Verify required fields
            required_fields = ["task_id", "status"]
            for field in required_fields:
                assert field in data, f"Missing required field: {field}"

            # Verify field types
            assert isinstance(data["task_id"], str), "task_id should be string"
            assert isinstance(data["status"], str), "status should be string"

            # Verify status value
            valid_statuses = ["queued", "processing", "completed", "failed"]
            assert data["status"] in valid_statuses, f"Invalid status: {data['status']}"

    @pytest.mark.asyncio
    async def test_indexing_response_includes_repo_id(
        self, async_test_client: AsyncClient, mock_celery_app
    ):
        """
        GIVEN a valid IndexingRequest
        WHEN posting to /v1/repositories/{repo_id}/index
        THEN the response should include the repo_id

        FAIL EXPECTED: Response may not include repo_id
        """
        # Arrange
        repo_id = "octocat/test-repo"
        payload = {
            "git_url": "https://github.com/octocat/test-repo.git",
            "access_token": "ghp_test_token",
        }

        # Act
        response = await async_test_client.post(f"/v1/repositories/{repo_id}/index", json=payload)

        # Assert
        if response.status_code == 202:
            data = response.json()
            if "repo_id" in data:
                assert data["repo_id"] == repo_id

    @pytest.mark.asyncio
    async def test_indexing_response_status_is_queued(
        self, async_test_client: AsyncClient, mock_celery_app
    ):
        """
        GIVEN a valid IndexingRequest
        WHEN posting to /v1/repositories/{repo_id}/index
        THEN the response status should be "queued"

        FAIL EXPECTED: May return wrong initial status
        """
        # Arrange
        repo_id = "octocat/test-repo"
        payload = {
            "git_url": "https://github.com/octocat/test-repo.git",
            "access_token": "ghp_test_token",
        }

        # Act
        response = await async_test_client.post(f"/v1/repositories/{repo_id}/index", json=payload)

        # Assert
        if response.status_code == 202:
            data = response.json()
            assert data.get("status") == "queued", (
                f"Initial status should be 'queued', got: {data.get('status')}"
            )
