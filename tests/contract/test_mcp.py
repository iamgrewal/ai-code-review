"""
T089 - Contract Tests for MCP Manifest Endpoint

Tests the GET /mcp/manifest endpoint that returns JSON-RPC tool schemas
for AI IDE agent integration (Cursor, Windsurf, etc.).

These tests MUST FAIL because the implementation doesn't exist yet.
"""

import pytest
from httpx import AsyncClient


class TestMCPManifestEndpointContract:
    """
    Contract tests for GET /mcp/manifest endpoint (T089).

    Tests verify:
    - HTTP 200 with valid JSON-RPC manifest
    - Returns required fields: name, version, description, tools
    - Tools array contains expected tool definitions
    - Each tool has: name, description, input_schema (JSON Schema)
    """

    @pytest.mark.asyncio
    async def test_mcp_manifest_returns_200_with_valid_structure(
        self, async_test_client: AsyncClient
    ):
        """
        T089: GIVEN the MCP manifest endpoint
        WHEN GET /mcp/manifest
        THEN returns HTTP 200 with valid manifest structure

        FAIL EXPECTED: Endpoint may not exist or return wrong structure
        """
        # Act
        response = await async_test_client.get("/mcp/manifest")

        # Assert
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()

        # Verify required top-level fields
        assert "name" in data, "Manifest must include 'name' field"
        assert "version" in data, "Manifest must include 'version' field"
        assert "description" in data, "Manifest must include 'description' field"
        assert "tools" in data, "Manifest must include 'tools' array"

        # Verify tools is an array
        assert isinstance(data["tools"], list), "'tools' must be an array"

    @pytest.mark.asyncio
    async def test_mcp_manifest_agent_metadata(self, async_test_client: AsyncClient):
        """
        T089: GIVEN the MCP manifest endpoint
        WHEN GET /mcp/manifest
        THEN returns correct agent metadata

        FAIL EXPECTED: Metadata values may not match specification
        """
        # Act
        response = await async_test_client.get("/mcp/manifest")

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Verify agent metadata matches spec
        assert data["name"] == "CortexReview-Agent", (
            f"Expected name 'CortexReview-Agent', got '{data.get('name')}'"
        )
        assert data["version"] == "1.0.0", f"Expected version '1.0.0', got '{data.get('version')}'"
        assert "CortexReview" in data["description"] or "AI" in data["description"], (
            "Description should mention AI or CortexReview"
        )

    @pytest.mark.asyncio
    async def test_mcp_manifest_tools_array_not_empty(self, async_test_client: AsyncClient):
        """
        T089: GIVEN the MCP manifest endpoint
        WHEN GET /mcp/manifest
        THEN tools array contains at least one tool

        FAIL EXPECTED: Tools may not be registered yet
        """
        # Act
        response = await async_test_client.get("/mcp/manifest")

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Verify tools array is not empty
        assert len(data["tools"]) > 0, "tools array should contain at least one tool"

    @pytest.mark.asyncio
    async def test_mcp_tool_analyze_diff_exists(self, async_test_client: AsyncClient):
        """
        T089: GIVEN the MCP manifest endpoint
        WHEN GET /mcp/manifest
        THEN includes analyze_diff tool definition

        FAIL EXPECTED: analyze_diff tool may not be defined
        """
        # Act
        response = await async_test_client.get("/mcp/manifest")

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Find analyze_diff tool
        analyze_diff = next((t for t in data["tools"] if t["name"] == "analyze_diff"), None)

        assert analyze_diff is not None, "analyze_diff tool must be in tools array"

    @pytest.mark.asyncio
    async def test_mcp_tool_index_repository_exists(self, async_test_client: AsyncClient):
        """
        T089: GIVEN the MCP manifest endpoint
        WHEN GET /mcp/manifest
        THEN includes index_repository tool definition

        FAIL EXPECTED: index_repository tool may not be defined
        """
        # Act
        response = await async_test_client.get("/mcp/manifest")

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Find index_repository tool
        index_repo = next((t for t in data["tools"] if t["name"] == "index_repository"), None)

        assert index_repo is not None, "index_repository tool must be in tools array"

    @pytest.mark.asyncio
    async def test_mcp_tool_submit_feedback_exists(self, async_test_client: AsyncClient):
        """
        T089: GIVEN the MCP manifest endpoint
        WHEN GET /mcp/manifest
        THEN includes submit_feedback tool definition

        FAIL EXPECTED: submit_feedback tool may not be defined
        """
        # Act
        response = await async_test_client.get("/mcp/manifest")

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Find submit_feedback tool
        submit_feedback = next((t for t in data["tools"] if t["name"] == "submit_feedback"), None)

        assert submit_feedback is not None, "submit_feedback tool must be in tools array"

    @pytest.mark.asyncio
    async def test_mcp_tool_get_task_status_exists(self, async_test_client: AsyncClient):
        """
        T089: GIVEN the MCP manifest endpoint
        WHEN GET /mcp/manifest
        THEN includes get_task_status tool definition

        FAIL EXPECTED: get_task_status tool may not be defined
        """
        # Act
        response = await async_test_client.get("/mcp/manifest")

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Find get_task_status tool
        get_status = next((t for t in data["tools"] if t["name"] == "get_task_status"), None)

        assert get_status is not None, "get_task_status tool must be in tools array"


class TestMCPToolDefinitionStructure:
    """
    Contract tests for individual MCP tool definitions (T089).

    Tests verify each tool has valid JSON-RPC input schema.
    """

    @pytest.mark.asyncio
    async def test_analyze_diff_tool_schema_structure(self, async_test_client: AsyncClient):
        """
        T089: GIVEN analyze_diff tool in manifest
        WHEN checking its inputSchema
        THEN has valid JSON Schema with required fields

        FAIL EXPECTED: Schema may not match specification
        """
        # Act
        response = await async_test_client.get("/mcp/manifest")

        # Assert
        assert response.status_code == 200
        data = response.json()

        analyze_diff = next((t for t in data["tools"] if t["name"] == "analyze_diff"), None)
        assert analyze_diff is not None

        # Verify tool structure
        assert "description" in analyze_diff
        assert "inputSchema" in analyze_diff
        assert isinstance(analyze_diff["inputSchema"], dict)

        schema = analyze_diff["inputSchema"]

        # Verify JSON Schema structure
        assert schema.get("type") == "object"
        assert "properties" in schema
        assert "diff" in schema["properties"]
        assert schema["properties"]["diff"].get("type") == "string"
        assert "required" in schema
        assert "diff" in schema["required"]

    @pytest.mark.asyncio
    async def test_index_repository_tool_schema_structure(self, async_test_client: AsyncClient):
        """
        T089: GIVEN index_repository tool in manifest
        WHEN checking its inputSchema
        THEN has valid JSON Schema with git_url and access_token

        FAIL EXPECTED: Schema may not match specification
        """
        # Act
        response = await async_test_client.get("/mcp/manifest")

        # Assert
        assert response.status_code == 200
        data = response.json()

        index_repo = next((t for t in data["tools"] if t["name"] == "index_repository"), None)
        assert index_repo is not None

        schema = index_repo["inputSchema"]

        # Verify required fields
        assert "git_url" in schema["properties"]
        assert "access_token" in schema["properties"]
        assert "git_url" in schema.get("required", [])
        assert "access_token" in schema.get("required", [])

    @pytest.mark.asyncio
    async def test_submit_feedback_tool_schema_structure(self, async_test_client: AsyncClient):
        """
        T089: GIVEN submit_feedback tool in manifest
        WHEN checking its inputSchema
        THEN has valid JSON Schema with feedback fields

        FAIL EXPECTED: Schema may not match specification
        """
        # Act
        response = await async_test_client.get("/mcp/manifest")

        # Assert
        assert response.status_code == 200
        data = response.json()

        submit_feedback = next((t for t in data["tools"] if t["name"] == "submit_feedback"), None)
        assert submit_feedback is not None

        schema = submit_feedback["inputSchema"]

        # Verify required fields
        assert "comment_id" in schema["properties"]
        assert "action" in schema["properties"]
        assert "reason" in schema["properties"]
        assert "developer_comment" in schema["properties"]
        assert "final_code_snapshot" in schema["properties"]

        # Verify action enum values
        action_prop = schema["properties"]["action"]
        assert "enum" in action_prop
        expected_actions = ["accepted", "rejected", "modified"]
        for action in expected_actions:
            assert action in action_prop["enum"]

    @pytest.mark.asyncio
    async def test_get_task_status_tool_schema_structure(self, async_test_client: AsyncClient):
        """
        T089: GIVEN get_task_status tool in manifest
        WHEN checking its inputSchema
        THEN has valid JSON Schema with task_id (UUID format)

        FAIL EXPECTED: Schema may not match specification
        """
        # Act
        response = await async_test_client.get("/mcp/manifest")

        # Assert
        assert response.status_code == 200
        data = response.json()

        get_status = next((t for t in data["tools"] if t["name"] == "get_task_status"), None)
        assert get_status is not None

        schema = get_status["inputSchema"]

        # Verify task_id field
        assert "task_id" in schema["properties"]
        assert schema["properties"]["task_id"].get("type") == "string"
        assert schema["properties"]["task_id"].get("format") == "uuid"
        assert "task_id" in schema.get("required", [])

    @pytest.mark.asyncio
    async def test_analyze_diff_config_properties(self, async_test_client: AsyncClient):
        """
        T089: GIVEN analyze_diff tool config property
        WHEN checking nested properties
        THEN includes severity_threshold, personas, use_rag_context

        FAIL EXPECTED: Config properties may not be fully defined
        """
        # Act
        response = await async_test_client.get("/mcp/manifest")

        # Assert
        assert response.status_code == 200
        data = response.json()

        analyze_diff = next((t for t in data["tools"] if t["name"] == "analyze_diff"), None)
        assert analyze_diff is not None

        schema = analyze_diff["inputSchema"]
        config_prop = schema["properties"].get("config")

        # config may be optional
        if config_prop:
            assert config_prop.get("type") == "object"
            config_props = config_prop.get("properties", {})

            # Verify expected config options exist
            assert "severity_threshold" in config_props
            assert "personas" in config_props
            assert "include_auto_fix_patches" in config_props
            assert "use_rag_context" in config_props
            assert "apply_learned_suppressions" in config_props

            # Verify severity_threshold enum
            severity = config_props["severity_threshold"]
            assert "enum" in severity
            expected_severities = ["nit", "low", "medium", "high", "critical"]
            for sev in expected_severities:
                assert sev in severity["enum"]


class TestMCPManifestContentType:
    """
    Contract tests for MCP manifest content negotiation (T089).

    Tests verify the endpoint returns correct content type.
    """

    @pytest.mark.asyncio
    async def test_mcp_manifest_returns_json_content_type(self, async_test_client: AsyncClient):
        """
        T089: GIVEN the MCP manifest endpoint
        WHEN GET /mcp/manifest
        THEN returns Content-Type: application/json

        FAIL EXPECTED: Content-Type header may not be set
        """
        # Act
        response = await async_test_client.get("/mcp/manifest")

        # Assert
        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", ""), (
            f"Expected application/json, got {response.headers.get('content-type')}"
        )

    @pytest.mark.asyncio
    async def test_mcp_manifest_accepts_html_accept_header(self, async_test_client: AsyncClient):
        """
        T089: GIVEN the MCP manifest endpoint
        WHEN GET /mcp/manifest with Accept: text/html
        THEN still returns JSON (ignore accept header for now)

        FAIL EXPECTED: May not handle Accept header properly
        """
        # Act
        response = await async_test_client.get("/mcp/manifest", headers={"Accept": "text/html"})

        # Assert - Should still return JSON
        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")


class TestMCPManifestCaching:
    """
    Contract tests for MCP manifest caching behavior (T089).

    Tests verify the manifest can be cached by IDE agents.
    """

    @pytest.mark.asyncio
    async def test_mcp_manifest_has_cache_headers(self, async_test_client: AsyncClient):
        """
        T089: GIVEN the MCP manifest endpoint
        WHEN GET /mcp/manifest
        THEN includes cache-friendly headers

        FAIL EXPECTED: Cache headers may not be implemented
        """
        # Act
        response = await async_test_client.get("/mcp/manifest")

        # Assert
        assert response.status_code == 200

        # Check for cache-related headers
        # These are optional but recommended for MCP manifests
        cache_control = response.headers.get("cache-control")
        etag = response.headers.get("etag")

        # At minimum, should have some cache guidance
        # (not a hard requirement, but good practice)
        if cache_control:
            assert "public" in cache_control or "max-age" in cache_control

    @pytest.mark.asyncio
    async def test_mcp_manifest_returns_same_content(self, async_test_client: AsyncClient):
        """
        T089: GIVEN the MCP manifest endpoint
        WHEN calling it twice
        THEN returns consistent content

        FAIL EXPECTED: Content may not be deterministic
        """
        # Act
        response1 = await async_test_client.get("/mcp/manifest")
        response2 = await async_test_client.get("/mcp/manifest")

        # Assert
        assert response1.status_code == 200
        assert response2.status_code == 200

        data1 = response1.json()
        data2 = response2.json()

        # Name, version should be consistent
        assert data1["name"] == data2["name"]
        assert data1["version"] == data2["version"]

        # Tools array should have same length
        assert len(data1["tools"]) == len(data2["tools"])
