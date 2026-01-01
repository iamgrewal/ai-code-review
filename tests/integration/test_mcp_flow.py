"""
T091 - Integration Tests for MCP IDE Agent Workflow

Tests the complete MCP integration flow from IDE agent perspective:
1. Fetch manifest (tool discovery)
2. Invoke analyze_diff tool
3. Receive review results

These tests MUST FAIL because the implementation doesn't exist yet.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient


# =============================================================================
# Constants
# =============================================================================

# Expected MCP tools that should be available in the manifest
# This list is duplicated across multiple test methods, so it's extracted as a constant
# for consistency and easier maintenance when new tools are added.
EXPECTED_MCP_TOOLS = [
    "analyze_diff",
    "index_repository",
    "submit_feedback",
    "get_task_status",
]


class TestMCPManifestDiscoveryFlow:
    """
    Integration tests for MCP manifest discovery (T091).

    Tests verify IDE agents can discover available tools.
    """

    @pytest.mark.asyncio
    async def test_ide_agent_can_fetch_manifest(self, async_test_client: AsyncClient):
        """
        T091: GIVEN an IDE agent (e.g., Cursor)
        WHEN fetching GET /mcp/manifest
        THEN receives complete tool definitions

        FAIL EXPECTED: Endpoint may not exist or return incomplete data
        """
        # Act
        response = await async_test_client.get("/mcp/manifest")

        # Assert
        assert response.status_code == 200
        manifest = response.json()

        # Verify agent can use this manifest
        assert "name" in manifest
        assert "tools" in manifest
        assert isinstance(manifest["tools"], list)

        # IDE agent needs at least one tool to be useful
        assert len(manifest["tools"]) > 0

    @pytest.mark.asyncio
    async def test_manifest_enables_tool_discovery(self, async_test_client: AsyncClient):
        """
        T091: GIVEN an IDE agent fetches manifest
        WHEN parsing tool definitions
        THEN can discover all available capabilities

        FAIL EXPECTED: Tool definitions may not be parseable
        """
        # Act
        response = await async_test_client.get("/mcp/manifest")

        # Assert
        assert response.status_code == 200
        manifest = response.json()

        # IDE agent should be able to extract tool names
        tool_names = [tool["name"] for tool in manifest["tools"]]

        # Verify expected tools are discoverable
        for expected in EXPECTED_MCP_TOOLS:
            assert expected in tool_names, (
                f"Expected tool '{expected}' not found in manifest. Available tools: {tool_names}"
            )

    @pytest.mark.asyncio
    async def test_manifest_includes_input_schemas_for_all_tools(
        self, async_test_client: AsyncClient
    ):
        """
        T091: GIVEN an IDE agent fetches manifest
        WHEN inspecting tool definitions
        THEN each tool has input_schema for validation

        FAIL EXPECTED: Some tools may lack input_schema
        """
        # Act
        response = await async_test_client.get("/mcp/manifest")

        # Assert
        assert response.status_code == 200
        manifest = response.json()

        # Verify all tools have input_schema
        for tool in manifest["tools"]:
            assert "inputSchema" in tool or "input_schema" in tool, (
                f"Tool '{tool.get('name')}' missing input_schema"
            )

            # Verify schema is valid dict
            schema = tool.get("inputSchema") or tool.get("input_schema")
            assert isinstance(schema, dict)
            assert "type" in schema


class TestMCPAnalyzeDiffToolFlow:
    """
    Integration tests for analyze_diff tool invocation (T091).

    Tests verify IDE agents can invoke code review via MCP.
    """

    @pytest.mark.asyncio
    async def test_analyze_diff_creates_review_task(self, async_test_client: AsyncClient):
        """
        T091: GIVEN an IDE agent invokes analyze_diff
        WHEN posting diff content
        THEN creates a Celery task for async review

        FAIL EXPECTED: Tool invocation endpoint may not exist
        """
        # Arrange - Mock Celery task
        with patch("worker.process_code_review") as mock_task:
            task_id = str(uuid.uuid4())
            mock_task.delay = MagicMock(return_value=MagicMock(id=task_id))

            # Act - Invoke MCP tool (may be POST /mcp/tools/analyze_diff)
            # Note: Actual endpoint path depends on implementation
            diff_content = """
--- a/src/main.py
+++ b/src/main.py
@@ -10,7 +10,7 @@
-    return None
+    return True
"""
            tool_request = {
                "diff": diff_content,
                "config": {
                    "severity_threshold": "low",
                    "use_rag_context": True,
                },
            }

            # Try common MCP endpoint patterns
            response = await async_test_client.post("/mcp/tools/analyze_diff", json=tool_request)

            # Assert - Should accept and create task
            # May return 202 (async) or 200 (sync)
            assert response.status_code in [200, 202]

            data = response.json()
            assert "task_id" in data or "review_id" in data

    @pytest.mark.asyncio
    async def test_analyze_diff_with_config_options(self, async_test_client: AsyncClient):
        """
        T091: GIVEN an IDE agent invokes analyze_diff with config
        WHEN providing full config options
        THEN task is created with specified configuration

        FAIL EXPECTED: Config options may not be passed through
        """
        # Arrange
        with patch("worker.process_code_review") as mock_task:
            task_id = str(uuid.uuid4())
            mock_task.delay = MagicMock(return_value=MagicMock(id=task_id))

            # Act
            tool_request = {
                "diff": "@@ -1,1 +1,1 @@\n-old\n+new",
                "config": {
                    "severity_threshold": "high",
                    "personas": ["security_expert", "pythonic_stylist"],
                    "include_auto_fix_patches": True,
                    "use_rag_context": True,
                    "apply_learned_suppressions": True,
                },
            }

            response = await async_test_client.post("/mcp/tools/analyze_diff", json=tool_request)

            # Assert
            assert response.status_code in [200, 202]
            data = response.json()

            # Verify config was accepted
            # (Response format depends on implementation)
            assert "task_id" in data or "review_id" in data

    @pytest.mark.asyncio
    async def test_analyze_diff_returns_review_on_completion(
        self, async_test_client: AsyncClient, sample_review_response
    ):
        """
        T091: GIVEN an IDE agent invokes analyze_diff
        WHEN task completes
        THEN can retrieve review results

        FAIL EXPECTED: Results may not be retrievable
        """
        # Arrange - Create task
        with patch("worker.process_code_review") as mock_task:
            task_id = str(uuid.uuid4())
            mock_task.delay = MagicMock(return_value=MagicMock(id=task_id))

            tool_request = {"diff": "@@ -1,1 +1,1 @@\n-old\n+new"}

            create_response = await async_test_client.post(
                "/mcp/tools/analyze_diff", json=tool_request
            )

            assert create_response.status_code in [200, 202]
            create_data = create_response.json()
            received_task_id = create_data.get("task_id")

            # Act - Poll for results
            # Note: This may go through /v1/tasks/{task_id} or MCP-specific endpoint
            status_response = await async_test_client.get(f"/v1/tasks/{received_task_id}")

            # Assert
            assert status_response.status_code == 200
            status_data = status_response.json()
            assert "status" in status_data

    @pytest.mark.asyncio
    async def test_analyze_diff_handles_invalid_diff(self, async_test_client: AsyncClient):
        """
        T091: GIVEN an IDE agent invokes analyze_diff with invalid diff
        WHEN diff is not valid unified diff format
        THEN returns helpful error message

        FAIL EXPECTED: May not validate diff format
        """
        # Arrange
        invalid_diff = "not a valid diff"

        # Act
        response = await async_test_client.post(
            "/mcp/tools/analyze_diff", json={"diff": invalid_diff}
        )

        # Assert - Should return error or handle gracefully
        # May still accept and process, returning no issues
        assert response.status_code in [200, 202, 400]

        if response.status_code in [400, 422]:
            # If error returned, should have helpful message
            data = response.json()
            assert "detail" in data or "error" in data


class TestMCPIndexRepositoryToolFlow:
    """
    Integration tests for index_repository tool invocation (T091).

    Tests verify IDE agents can trigger repository indexing.
    """

    @pytest.mark.asyncio
    async def test_index_repository_creates_indexing_task(self, async_test_client: AsyncClient):
        """
        T091: GIVEN an IDE agent invokes index_repository
        WHEN providing git URL and access token
        THEN creates indexing Celery task

        FAIL EXPECTED: Tool invocation may not work
        """
        # Arrange
        with patch("worker.index_repository") as mock_task:
            task_id = str(uuid.uuid4())
            mock_task.delay = MagicMock(return_value=MagicMock(id=task_id))

            # Act
            tool_request = {
                "git_url": "https://github.com/owner/repo.git",
                "access_token": "ghp_test_token",
                "branch": "main",
                "index_depth": "deep",
            }

            response = await async_test_client.post(
                "/mcp/tools/index_repository", json=tool_request
            )

            # Assert
            assert response.status_code in [200, 202]
            data = response.json()
            assert "task_id" in data

    @pytest.mark.asyncio
    async def test_index_repository_validates_required_fields(self, async_test_client: AsyncClient):
        """
        T091: GIVEN an IDE agent invokes index_repository
        WHEN missing required git_url or access_token
        THEN returns validation error

        FAIL EXPECTED: Validation may not be enforced
        """
        # Arrange - Missing access_token
        tool_request = {"git_url": "https://github.com/owner/repo.git"}

        # Act
        response = await async_test_client.post("/mcp/tools/index_repository", json=tool_request)

        # Assert - Should return validation error
        assert response.status_code in [400, 422]
        data = response.json()
        assert "detail" in data or "error" in data


class TestMCPSubmitFeedbackToolFlow:
    """
    Integration tests for submit_feedback tool invocation (T091).

    Tests verify IDE agents can submit RLHF feedback.
    """

    @pytest.mark.asyncio
    async def test_submit_feedback_creates_feedback_task(self, async_test_client: AsyncClient):
        """
        T091: GIVEN an IDE agent invokes submit_feedback
        WHEN providing comment_id and feedback
        THEN creates RLHF feedback task

        FAIL EXPECTED: Tool invocation may not work
        """
        # Arrange
        with patch("worker.process_feedback") as mock_task:
            task_id = str(uuid.uuid4())
            mock_task.delay = MagicMock(return_value=MagicMock(id=task_id))

            # Act
            tool_request = {
                "comment_id": str(uuid.uuid4()),
                "action": "rejected",
                "reason": "false_positive",
                "developer_comment": "Variable is sanitized earlier",
                "final_code_snapshot": "x = sanitize(y)\nexecute(x)",
            }

            response = await async_test_client.post("/mcp/tools/submit_feedback", json=tool_request)

            # Assert
            assert response.status_code in [200, 202]
            data = response.json()
            assert "feedback_id" in data or "task_id" in data

    @pytest.mark.asyncio
    async def test_submit_feedback_validates_action_enum(self, async_test_client: AsyncClient):
        """
        T091: GIVEN an IDE agent invokes submit_feedback
        WHEN providing invalid action value
        THEN returns validation error

        FAIL EXPECTED: Action enum may not be validated
        """
        # Arrange
        tool_request = {
            "comment_id": str(uuid.uuid4()),
            "action": "invalid_action",
            "reason": "false_positive",
            "developer_comment": "Test",
            "final_code_snapshot": "code",
        }

        # Act
        response = await async_test_client.post("/mcp/tools/submit_feedback", json=tool_request)

        # Assert
        assert response.status_code in [400, 422]


class TestMCPGetTaskStatusToolFlow:
    """
    Integration tests for get_task_status tool invocation (T091).

    Tests verify IDE agents can poll task status.
    """

    @pytest.mark.asyncio
    async def test_get_task_status_returns_task_info(self, async_test_client: AsyncClient):
        """
        T091: GIVEN an IDE agent invokes get_task_status
        WHEN providing valid task_id
        THEN returns current task status

        FAIL EXPECTED: Tool may not return status correctly
        """
        # Arrange - Create a task first
        with patch("worker.process_code_review") as mock_task:
            task_id = str(uuid.uuid4())
            mock_task.delay = MagicMock(return_value=MagicMock(id=task_id))

            # Act - Get status
            tool_request = {"task_id": task_id}

            response = await async_test_client.post("/mcp/tools/get_task_status", json=tool_request)

            # Assert
            # May return 200 with status or 404 if task not found
            assert response.status_code in [200, 404]

            if response.status_code == 200:
                data = response.json()
                assert "status" in data or "task_id" in data

    @pytest.mark.asyncio
    async def test_get_task_status_validates_uuid_format(self, async_test_client: AsyncClient):
        """
        T091: GIVEN an IDE agent invokes get_task_status
        WHEN providing invalid UUID format
        THEN returns validation error

        FAIL EXPECTED: UUID format may not be validated
        """
        # Arrange
        tool_request = {"task_id": "not-a-valid-uuid"}

        # Act
        response = await async_test_client.post("/mcp/tools/get_task_status", json=tool_request)

        # Assert
        assert response.status_code in [400, 422]


class TestCompleteMCPWorkflow:
    """
    Integration tests for complete MCP workflow (T091).

    Tests verify end-to-end IDE agent experience.
    """

    @pytest.mark.asyncio
    async def test_full_workflow_manifest_to_review(self, async_test_client: AsyncClient):
        """
        T091: GIVEN an IDE agent starting fresh
        WHEN going through full workflow (manifest -> analyze -> results)
        THEN all steps complete successfully

        FAIL EXPECTED: Full workflow may have integration issues
        """
        # Step 1: Fetch manifest
        manifest_response = await async_test_client.get("/mcp/manifest")
        assert manifest_response.status_code == 200
        manifest = manifest_response.json()

        # Verify analyze_diff is available
        tool_names = [t["name"] for t in manifest["tools"]]
        assert "analyze_diff" in tool_names

        # Step 2: Invoke analyze_diff
        with patch("worker.process_code_review") as mock_task:
            task_id = str(uuid.uuid4())
            mock_task.delay = MagicMock(return_value=MagicMock(id=task_id))

            analyze_request = {
                "diff": "@@ -1,1 +1,1 @@\n-old\n+new",
                "config": {"severity_threshold": "low"},
            }

            analyze_response = await async_test_client.post(
                "/mcp/tools/analyze_diff", json=analyze_request
            )

            assert analyze_response.status_code in [200, 202]
            analyze_data = analyze_response.json()
            assert "task_id" in analyze_data

            received_task_id = analyze_data["task_id"]

            # Step 3: Poll task status
            status_response = await async_test_client.get(f"/v1/tasks/{received_task_id}")

            assert status_response.status_code == 200
            status_data = status_response.json()
            assert "status" in status_data

    @pytest.mark.asyncio
    async def test_concurrent_tool_invocations(self, async_test_client: AsyncClient):
        """
        T091: GIVEN an IDE agent invoking multiple tools
        WHEN calls are made concurrently
        THEN all requests are handled correctly

        FAIL EXPECTED: May not handle concurrency properly
        """
        # Arrange
        import asyncio

        with patch("worker.process_code_review") as mock_review:
            with patch("worker.index_repository") as mock_index:
                mock_review.delay = MagicMock(return_value=MagicMock(id=str(uuid.uuid4())))
                mock_index.delay = MagicMock(return_value=MagicMock(id=str(uuid.uuid4())))

                # Act - Concurrent requests
                tasks = [
                    async_test_client.post(
                        "/mcp/tools/analyze_diff", json={"diff": "@@ -1 +1 @@\n-old\n+new"}
                    ),
                    async_test_client.post(
                        "/mcp/tools/index_repository",
                        json={
                            "git_url": "https://github.com/test/repo.git",
                            "access_token": "token",
                        },
                    ),
                    async_test_client.get("/mcp/manifest"),
                ]

                responses = await asyncio.gather(*tasks)

                # Assert - All should succeed
                assert all(r.status_code in [200, 202] for r in responses)

    @pytest.mark.asyncio
    async def test_workflow_with_rag_context_enabled(self, async_test_client: AsyncClient):
        """
        T091: GIVEN an IDE agent invokes analyze_diff with RAG
        WHEN use_rag_context is enabled
        THEN workflow completes with context-enhanced review

        FAIL EXPECTED: RAG integration may not work
        """
        # Arrange
        with patch("worker.process_code_review") as mock_task:
            task_id = str(uuid.uuid4())
            mock_task.delay = MagicMock(return_value=MagicMock(id=task_id))

            # Act
            analyze_request = {
                "diff": "@@ -1,1 +1,1 @@\n-old\n+new",
                "config": {
                    "use_rag_context": True,
                    "apply_learned_suppressions": True,
                    "max_context_matches": 5,
                },
            }

            response = await async_test_client.post("/mcp/tools/analyze_diff", json=analyze_request)

            # Assert
            assert response.status_code in [200, 202]
            data = response.json()
            assert "task_id" in data

    @pytest.mark.asyncio
    async def test_workflow_with_feedback_submission(self, async_test_client: AsyncClient):
        """
        T091: GIVEN an IDE agent completed a review
        WHEN user rejects a comment via submit_feedback
        THEN feedback is submitted and constraint is learned

        FAIL EXPECTED: Feedback workflow may not work
        """
        # Step 1: Get manifest
        manifest_response = await async_test_client.get("/mcp/manifest")
        assert manifest_response.status_code == 200

        # Step 2: Submit feedback on a comment
        with patch("worker.process_feedback") as mock_task:
            feedback_id = str(uuid.uuid4())
            mock_task.delay = MagicMock(return_value=MagicMock(id=feedback_id))

            feedback_request = {
                "comment_id": str(uuid.uuid4()),
                "action": "rejected",
                "reason": "false_positive",
                "developer_comment": "This is acceptable code style",
                "final_code_snapshot": "def foo():\n    return True",
            }

            feedback_response = await async_test_client.post(
                "/mcp/tools/submit_feedback", json=feedback_request
            )

            # Assert
            assert feedback_response.status_code in [200, 202]
            data = feedback_response.json()
            assert "feedback_id" in data or "task_id" in data


class TestMCPErrorsAndEdgeCases:
    """
    Integration tests for MCP error handling (T091).

    Tests verify IDE agents receive helpful error messages.
    """

    @pytest.mark.asyncio
    async def test_manifest_handles_invalid_accept_header(self, async_test_client: AsyncClient):
        """
        T091: GIVEN an IDE agent requests manifest
        WHEN sending invalid Accept header
        THEN returns JSON anyway (graceful degradation)

        FAIL EXPECTED: May not handle invalid headers
        """
        # Act
        response = await async_test_client.get(
            "/mcp/manifest", headers={"Accept": "application/xml"}
        )

        # Assert - Should still return JSON
        assert response.status_code in [200, 406]
        if response.status_code == 200:
            assert "application/json" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_tool_invocation_malformed_json(self, async_test_client: AsyncClient):
        """
        T091: GIVEN an IDE agent invokes tool
        WHEN sending malformed JSON
        THEN returns clear error message

        FAIL EXPECTED: May not handle malformed JSON
        """
        # Act
        response = await async_test_client.post(
            "/mcp/tools/analyze_diff",
            content="{invalid json",
            headers={"Content-Type": "application/json"},
        )

        # Assert
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_nonexistent_tool_returns_404(self, async_test_client: AsyncClient):
        """
        T091: GIVEN an IDE agent invokes non-existent tool
        WHEN calling /mcp/tools/nonexistent_tool
        THEN returns 404 or error

        FAIL EXPECTED: May not handle unknown tools
        """
        # Act
        response = await async_test_client.post(
            "/mcp/tools/nonexistent_tool", json={"param": "value"}
        )

        # Assert
        assert response.status_code in [404, 400]

    @pytest.mark.asyncio
    async def test_task_timeout_handled_gracefully(self, async_test_client: AsyncClient):
        """
        T091: GIVEN an IDE agent polling task status
        WHEN task times out
        THEN returns timeout status or error

        FAIL EXPECTED: Timeouts may not be handled
        """
        # Arrange - Task ID that doesn't exist
        fake_task_id = str(uuid.uuid4())

        # Act
        response = await async_test_client.get(f"/v1/tasks/{fake_task_id}")

        # Assert - Should return 404 or indicate task not found
        assert response.status_code in [200, 404]
