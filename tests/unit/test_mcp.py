"""
T090 - Unit Tests for MCP Models

Tests the MCPTool and MCPManifest models that define the JSON-RPC
tool schemas for AI IDE agent integration.

These tests MUST FAIL because the implementation may not exist or
have incorrect validation/behavior.
"""

import pytest
from pydantic import ValidationError

from models.mcp import MCPManifest, MCPTool


class TestMCPToolModel:
    """
    Unit tests for MCPTool model (T090).

    Tests verify:
    - Model validates required fields correctly
    - Field types match specification
    - JSON Schema serialization works
    """

    def test_mcp_tool_requires_name_field(self):
        """
        T090: GIVEN MCPTool model
        WHEN creating without name field
        THEN raises ValidationError

        FAIL EXPECTED: Validation may not be enforced
        """
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            MCPTool(description="Test tool", input_schema={"type": "object"})

        # Verify error mentions name
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("name",) for e in errors)

    def test_mcp_tool_requires_description_field(self):
        """
        T090: GIVEN MCPTool model
        WHEN creating without description field
        THEN raises ValidationError

        FAIL EXPECTED: Validation may not be enforced
        """
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            MCPTool(name="test_tool", input_schema={"type": "object"})

        # Verify error mentions description
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("description",) for e in errors)

    def test_mcp_tool_requires_input_schema_field(self):
        """
        T090: GIVEN MCPTool model
        WHEN creating without input_schema field
        THEN raises ValidationError

        FAIL EXPECTED: Validation may not be enforced
        """
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            MCPTool(name="test_tool", description="Test tool")

        # Verify error mentions input_schema
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("input_schema",) for e in errors)

    def test_mcp_tool_accepts_valid_data(self):
        """
        T090: GIVEN valid MCPTool data
        WHEN creating the model
        THEN validates successfully

        FAIL EXPECTED: Model may reject valid data
        """
        # Arrange & Act
        tool = MCPTool(
            name="test_tool",
            description="A test tool for unit testing",
            input_schema={
                "type": "object",
                "properties": {
                    "param1": {"type": "string"},
                    "param2": {"type": "integer"},
                },
                "required": ["param1"],
            },
        )

        # Assert
        assert tool.name == "test_tool"
        assert tool.description == "A test tool for unit testing"
        assert tool.input_schema["type"] == "object"
        assert "param1" in tool.input_schema["properties"]

    def test_mcp_tool_serializes_to_json(self):
        """
        T090: GIVEN a valid MCPTool model
        WHEN calling model_dump()
        THEN returns dict with all fields

        FAIL EXPECTED: Serialization may not work correctly
        """
        # Arrange
        tool = MCPTool(name="test_tool", description="Test tool", input_schema={"type": "object"})

        # Act
        data = tool.model_dump()

        # Assert
        assert isinstance(data, dict)
        assert "name" in data
        assert "description" in data
        assert "input_schema" in data
        assert data["name"] == "test_tool"

    def test_mcp_tool_input_schema_accepts_any_dict(self):
        """
        T090: GIVEN MCPTool input_schema field
        WHEN providing any valid dict (JSON Schema)
        THEN accepts the schema

        FAIL EXPECTED: May restrict valid JSON Schema values
        """
        # Arrange & Act - Various valid JSON Schema patterns
        schemas = [
            {"type": "string"},
            {"type": "object", "properties": {"x": {"type": "number"}}},
            {
                "type": "object",
                "properties": {
                    "required_field": {"type": "string"},
                    "optional_field": {"type": "boolean"},
                },
                "required": ["required_field"],
            },
            {"type": "array", "items": {"type": "string"}},
        ]

        # Assert - All should validate
        for schema in schemas:
            tool = MCPTool(name="test_tool", description="Test", input_schema=schema)
            assert tool.input_schema == schema

    def test_mcp_tool_field_types_match_spec(self):
        """
        T090: GIVEN MCPTool model
        WHEN checking field types
        THEN name and description are str, input_schema is dict

        FAIL EXPECTED: Field types may not match specification
        """
        # Arrange & Act
        tool = MCPTool(
            name="test_tool", description="Test description", input_schema={"type": "object"}
        )

        # Assert
        assert isinstance(tool.name, str)
        assert isinstance(tool.description, str)
        assert isinstance(tool.input_schema, dict)

    def test_mcp_tool_name_field_description_exists(self):
        """
        T090: GIVEN MCPTool model definition
        WHEN checking Field metadata
        THEN name field has description

        FAIL EXPECTED: Field descriptions may not be defined
        """
        # This tests the model definition has proper documentation
        # Accessing field metadata through model_fields
        field_info = MCPTool.model_fields["name"]
        assert field_info.description is not None
        assert "Tool identifier" in field_info.description or "snake_case" in field_info.description


class TestMCPManifestModel:
    """
    Unit tests for MCPManifest model (T090).

    Tests verify:
    - Default values are set correctly
    - Tools array handling
    - JSON serialization
    - Required vs optional fields
    """

    def test_mcp_manifest_has_default_name(self):
        """
        T090: GIVEN MCPManifest model
        WHEN creating without name field
        THEN uses default "CortexReview-Agent"

        FAIL EXPECTED: Default may not be set correctly
        """
        # Arrange & Act
        manifest = MCPManifest()

        # Assert
        assert manifest.name == "CortexReview-Agent"

    def test_mcp_manifest_has_default_version(self):
        """
        T090: GIVEN MCPManifest model
        WHEN creating without version field
        THEN uses default "1.0.0"

        FAIL EXPECTED: Default may not be set correctly
        """
        # Arrange & Act
        manifest = MCPManifest()

        # Assert
        assert manifest.version == "1.0.0"

    def test_mcp_manifest_has_default_description(self):
        """
        T090: GIVEN MCPManifest model
        WHEN creating without description field
        THEN uses default about "AI-powered code review"

        FAIL EXPECTED: Default may not be set correctly
        """
        # Arrange & Act
        manifest = MCPManifest()

        # Assert
        assert "AI" in manifest.description or "code review" in manifest.description.lower()

    def test_mcp_manifest_has_default_empty_tools_list(self):
        """
        T090: GIVEN MCPManifest model
        WHEN creating without tools field
        THEN uses empty list as default

        FAIL EXPECTED: Default may not be set correctly
        """
        # Arrange & Act
        manifest = MCPManifest()

        # Assert
        assert manifest.tools == []
        assert isinstance(manifest.tools, list)

    def test_mcp_manifest_accepts_custom_name(self):
        """
        T090: GIVEN MCPManifest model
        WHEN creating with custom name
        THEN uses the custom name

        FAIL EXPECTED: Custom value may not override default
        """
        # Arrange & Act
        manifest = MCPManifest(name="Custom-Agent-Name")

        # Assert
        assert manifest.name == "Custom-Agent-Name"

    def test_mcp_manifest_accepts_custom_version(self):
        """
        T090: GIVEN MCPManifest model
        WHEN creating with custom version
        THEN uses the custom version

        FAIL EXPECTED: Custom value may not override default
        """
        # Arrange & Act
        manifest = MCPManifest(version="2.5.0")

        # Assert
        assert manifest.version == "2.5.0"

    def test_mcp_manifest_accepts_tools_list(self):
        """
        T090: GIVEN MCPManifest model
        WHEN creating with tools list
        THEN stores the tools correctly

        FAIL EXPECTED: Tools may not be stored correctly
        """
        # Arrange
        tools = [
            MCPTool(name="tool1", description="First tool", input_schema={"type": "object"}),
            MCPTool(name="tool2", description="Second tool", input_schema={"type": "string"}),
        ]

        # Act
        manifest = MCPManifest(tools=tools)

        # Assert
        assert len(manifest.tools) == 2
        assert manifest.tools[0].name == "tool1"
        assert manifest.tools[1].name == "tool2"

    def test_mcp_manifest_serializes_to_json(self):
        """
        T090: GIVEN a valid MCPManifest model
        WHEN calling model_dump()
        THEN returns dict with all fields

        FAIL EXPECTED: Serialization may not work correctly
        """
        # Arrange
        manifest = MCPManifest(name="Test-Agent", version="1.2.3", description="Test description")

        # Act
        data = manifest.model_dump()

        # Assert
        assert isinstance(data, dict)
        assert "name" in data
        assert "version" in data
        assert "description" in data
        assert "tools" in data
        assert data["name"] == "Test-Agent"
        assert data["tools"] == []

    def test_mcp_manifest_tools_serialize_correctly(self):
        """
        T090: GIVEN MCPManifest with tools
        WHEN serializing to dict
        THEN tools are serialized as dicts

        FAIL EXPECTED: Tools may not serialize correctly
        """
        # Arrange
        manifest = MCPManifest(
            tools=[MCPTool(name="test_tool", description="Test", input_schema={"type": "object"})]
        )

        # Act
        data = manifest.model_dump()

        # Assert
        assert isinstance(data["tools"], list)
        assert len(data["tools"]) == 1
        assert isinstance(data["tools"][0], dict)
        assert data["tools"][0]["name"] == "test_tool"


class TestMCPManifestFactoryMethods:
    """
    Unit tests for MCPManifest factory/convenience methods (T090).

    Tests verify helper methods for creating manifests.
    """

    def test_can_create_manifest_with_multiple_tools(self):
        """
        T090: GIVEN multiple MCPTool definitions
        WHEN creating MCPManifest
        THEN all tools are included

        FAIL EXPECTED: May not handle multiple tools correctly
        """
        # Arrange
        tools = [
            MCPTool(
                name=f"tool_{i}", description=f"Tool number {i}", input_schema={"type": "object"}
            )
            for i in range(5)
        ]

        # Act
        manifest = MCPManifest(tools=tools)

        # Assert
        assert len(manifest.tools) == 5
        for i, tool in enumerate(manifest.tools):
            assert tool.name == f"tool_{i}"

    def test_manifest_adds_tool_dynamically(self):
        """
        T090: GIVEN an existing MCPManifest
        WHEN adding a tool to tools list
        THEN the new tool is included

        FAIL EXPECTED: Tools list may be immutable
        """
        # Arrange
        manifest = MCPManifest()
        new_tool = MCPTool(
            name="new_tool", description="Dynamically added", input_schema={"type": "object"}
        )

        # Act
        manifest.tools.append(new_tool)

        # Assert
        assert len(manifest.tools) == 1
        assert manifest.tools[0].name == "new_tool"


class TestMCPToolInputSchemaValidation:
    """
    Unit tests for MCPTool input_schema validation patterns (T090).

    Tests verify common JSON Schema patterns work correctly.
    """

    def test_input_schema_with_string_type(self):
        """
        T090: GIVEN input_schema with string type
        WHEN creating MCPTool
        THEN validates successfully

        FAIL EXPECTED: May reject valid string schema
        """
        # Arrange & Act
        tool = MCPTool(
            name="string_tool",
            description="Tool with string input",
            input_schema={"type": "string"},
        )

        # Assert
        assert tool.input_schema["type"] == "string"

    def test_input_schema_with_nested_properties(self):
        """
        T090: GIVEN input_schema with nested object properties
        WHEN creating MCPTool
        THEN validates successfully

        FAIL EXPECTED: May reject complex nested schemas
        """
        # Arrange & Act
        tool = MCPTool(
            name="complex_tool",
            description="Tool with complex input",
            input_schema={
                "type": "object",
                "properties": {
                    "config": {"type": "object", "properties": {"nested": {"type": "string"}}},
                    "items": {"type": "array", "items": {"type": "integer"}},
                },
            },
        )

        # Assert
        assert "config" in tool.input_schema["properties"]
        assert "items" in tool.input_schema["properties"]

    def test_input_schema_with_enum_values(self):
        """
        T090: GIVEN input_schema with enum constraint
        WHEN creating MCPTool
        THEN validates successfully

        FAIL EXPECTED: May reject enum constraints
        """
        # Arrange & Act
        tool = MCPTool(
            name="enum_tool",
            description="Tool with enum input",
            input_schema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["create", "update", "delete"]}
                },
            },
        )

        # Assert
        assert "enum" in tool.input_schema["properties"]["action"]
        assert "create" in tool.input_schema["properties"]["action"]["enum"]


class TestMCPManifestJsonSchemaExample:
    """
    Unit tests for MCPManifest json_schema_extra example (T090).

    Tests verify the Config.json_schema_extra example matches spec.
    """

    def test_manifest_has_json_schema_extra_example(self):
        """
        T090: GIVEN MCPManifest model
        WHEN checking Config class
        THEN has json_schema_extra with examples

        FAIL EXPECTED: json_schema_extra may not be defined
        """
        # This tests that the model has example documentation
        # Accessing through model_config or Config inner class
        assert hasattr(MCPManifest, "model_config")

        # The json_schema_extra should exist in config
        config = MCPManifest.model_config.get("json_schema_extra")
        assert config is not None
        assert "examples" in config

    def test_manifest_example_matches_spec(self):
        """
        T090: GIVEN MCPManifest json_schema_extra example
        WHEN checking the example structure
        THEN matches the MCP manifest specification

        FAIL EXPECTED: Example may not match spec
        """
        # Arrange
        config = MCPManifest.model_config.get("json_schema_extra", {})
        examples = config.get("examples", [])

        # Assert - At least one example exists
        assert len(examples) > 0

        # Verify example has required fields
        example = examples[0]
        assert "name" in example
        assert "version" in example
        assert "description" in example
        assert "tools" in example

        # Verify tools in example
        assert isinstance(example["tools"], list)
        if len(example["tools"]) > 0:
            tool_example = example["tools"][0]
            assert "name" in tool_example
            assert "description" in tool_example
            assert "input_schema" in tool_example


class TestMCPToolFieldDescriptions:
    """
    Unit tests for MCPTool field documentation (T090).

    Tests verify field descriptions exist and are accurate.
    """

    def test_mcp_tool_name_field_has_description(self):
        """
        T090: GIVEN MCPTool name field
        WHEN checking field metadata
        THEN has descriptive text

        FAIL EXPECTED: Field may lack description
        """
        field_info = MCPTool.model_fields["name"]
        assert field_info.description is not None
        assert len(field_info.description) > 0

    def test_mcp_tool_description_field_has_description(self):
        """
        T090: GIVEN MCPTool description field
        WHEN checking field metadata
        THEN has descriptive text

        FAIL EXPECTED: Field may lack description
        """
        field_info = MCPTool.model_fields["description"]
        assert field_info.description is not None
        assert len(field_info.description) > 0

    def test_mcp_tool_input_schema_field_has_description(self):
        """
        T090: GIVEN MCPTool input_schema field
        WHEN checking field metadata
        THEN mentions JSON Schema

        FAIL EXPECTED: Field may lack description
        """
        field_info = MCPTool.model_fields["input_schema"]
        assert field_info.description is not None
        assert "JSON" in field_info.description or "schema" in field_info.description.lower()


class TestMCPManifestFieldDescriptions:
    """
    Unit tests for MCPManifest field documentation (T090).

    Tests verify field descriptions exist and are accurate.
    """

    def test_mcp_manifest_name_field_has_description(self):
        """
        T090: GIVEN MCPManifest name field
        WHEN checking field metadata
        THEN has descriptive text

        FAIL EXPECTED: Field may lack description
        """
        field_info = MCPManifest.model_fields["name"]
        assert field_info.description is not None
        assert "Agent" in field_info.description or "name" in field_info.description.lower()

    def test_mcp_manifest_version_field_has_description(self):
        """
        T090: GIVEN MCPManifest version field
        WHEN checking field metadata
        THEN has descriptive text

        FAIL EXPECTED: Field may lack description
        """
        field_info = MCPManifest.model_fields["version"]
        assert field_info.description is not None
        assert "version" in field_info.description.lower()

    def test_mcp_manifest_tools_field_has_description(self):
        """
        T090: GIVEN MCPManifest tools field
        WHEN checking field metadata
        THEN mentions available tools

        FAIL EXPECTED: Field may lack description
        """
        field_info = MCPManifest.model_fields["tools"]
        assert field_info.description is not None
        assert "tool" in field_info.description.lower()
