"""
MCP (Model Context Protocol) models for CortexReview.

Defines JSON-RPC tool schemas for AI IDE agent integration.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MCPTool(BaseModel):
    """
    Definition of an MCP tool available to IDE agents.

    Each tool represents an action that can be invoked by AI IDEs
    like Cursor, Windsurf, or other MCP-compatible agents.
    """

    name: str = Field(..., description="Tool identifier (snake_case)")
    description: str = Field(..., description="Human-readable tool description")
    input_schema: dict[str, Any] = Field(
        ..., description="JSON-RPC input schema (JSON Schema format)"
    )


class MCPManifest(BaseModel):
    """
    MCP manifest describing available tools for IDE agent integration.

    This manifest is exposed at GET /mcp/manifest and allows IDE agents
    to discover and invoke CortexReview capabilities directly.

    Available tools:
    - analyze_diff: Analyze code diff and provide review comments
    - index_repository: Trigger repository indexing for RAG context
    - submit_feedback: Submit feedback on review comments for RLHF
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "CortexReview-Agent",
                    "version": "1.0.0",
                    "description": "AI-powered code review platform with RAG and RLHF",
                    "server_info": {
                        "name": "CortexReview Platform",
                        "version": "2.0.0",
                        "protocol_version": "2024-11-05",
                    },
                    "tools": [
                        {
                            "name": "analyze_diff",
                            "description": "Analyze code diff and provide review comments",
                            "input_schema": {
                                "type": "object",
                                "properties": {
                                    "diff": {
                                        "type": "string",
                                        "description": "Code diff to analyze (unified diff format)",
                                    },
                                    "repo_id": {
                                        "type": "string",
                                        "description": "Repository identifier (owner/repo) for RAG context",
                                    },
                                    "config": {
                                        "type": "object",
                                        "description": "Optional review configuration",
                                        "properties": {
                                            "use_rag_context": {"type": "boolean"},
                                            "severity_threshold": {"type": "string"},
                                            "include_auto_fix_patches": {"type": "boolean"},
                                        },
                                    },
                                },
                            },
                        },
                        {
                            "name": "index_repository",
                            "description": "Trigger repository indexing for RAG knowledge base",
                            "input_schema": {
                                "type": "object",
                                "properties": {
                                    "git_url": {
                                        "type": "string",
                                        "description": "Git repository HTTPS URL",
                                    },
                                    "access_token": {
                                        "type": "string",
                                        "description": "Personal access token for cloning",
                                    },
                                    "branch": {
                                        "type": "string",
                                        "description": "Branch to index (default: main)",
                                    },
                                    "index_depth": {
                                        "type": "string",
                                        "enum": ["shallow", "deep"],
                                        "description": "Indexing mode (default: deep)",
                                    },
                                },
                                "required": ["git_url", "access_token"],
                            },
                        },
                        {
                            "name": "submit_feedback",
                            "description": "Submit feedback on review comments for RLHF learning",
                            "input_schema": {
                                "type": "object",
                                "properties": {
                                    "comment_id": {
                                        "type": "string",
                                        "description": "Review comment ID being feedback upon",
                                    },
                                    "action": {
                                        "type": "string",
                                        "enum": ["accepted", "rejected", "modified"],
                                        "description": "Action taken on the comment",
                                    },
                                    "reason": {
                                        "type": "string",
                                        "enum": [
                                            "false_positive",
                                            "logic_error",
                                            "style_preference",
                                            "hallucination",
                                        ],
                                        "description": "Reason category for feedback",
                                    },
                                    "developer_comment": {
                                        "type": "string",
                                        "description": "Free-form explanation (1-1000 characters)",
                                    },
                                    "final_code_snapshot": {
                                        "type": "string",
                                        "description": "Final committed code snippet",
                                    },
                                },
                                "required": [
                                    "comment_id",
                                    "action",
                                    "reason",
                                    "developer_comment",
                                    "final_code_snapshot",
                                ],
                            },
                        },
                    ],
                }
            ]
        }
    )

    name: str = Field(default="CortexReview-Agent", description="Agent name")
    version: str = Field(default="1.0.0", description="Agent version")
    description: str = Field(
        default="AI-powered code review platform with RAG and RLHF",
        description="Agent description",
    )
    tools: list[MCPTool] = Field(default_factory=list, description="Available tools")
    server_info: dict[str, Any] = Field(
        default_factory=lambda: {
            "name": "CortexReview Platform",
            "version": "2.0.0",
            "protocol_version": "2024-11-05",
            "capabilities": {
                "tools": True,
                "resources": False,
                "prompts": False,
            },
        },
        description="Server information and capabilities",
    )


class MCPToolRequest(BaseModel):
    """
    Request model for invoking MCP tools.

    IDE agents send tool invocation requests using this schema.
    """

    tool_name: str = Field(
        ...,
        description="Tool to invoke (analyze_diff, index_repository, submit_feedback)",
    )
    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Tool-specific arguments (must match tool's input_schema)",
    )
    request_id: str | None = Field(None, description="Optional request ID for correlation")


class MCPToolResponse(BaseModel):
    """
    Response model for MCP tool invocations.

    Returns the result of tool execution or error details.
    """

    request_id: str | None = Field(None, description="Request ID from input")
    tool_name: str = Field(..., description="Tool that was invoked")
    success: bool = Field(..., description="Whether tool execution succeeded")
    result: Any | None = Field(None, description="Tool execution result (if successful)")
    error: str | None = Field(None, description="Error message (if failed)")
    task_id: str | None = Field(None, description="Celery task ID (for async operations)")


# Tool definitions for easy access
MCP_TOOLS: list[MCPTool] = [
    MCPTool(
        name="analyze_diff",
        description="Analyze code diff and provide review comments using AI with RAG context",
        input_schema={
            "type": "object",
            "properties": {
                "diff": {
                    "type": "string",
                    "description": "Code diff to analyze (unified diff format)",
                },
                "repo_id": {
                    "type": "string",
                    "description": "Repository identifier (owner/repo) for RAG context",
                },
                "config": {
                    "type": "object",
                    "description": "Optional review configuration",
                    "properties": {
                        "use_rag_context": {"type": "boolean"},
                        "severity_threshold": {"type": "string"},
                        "include_auto_fix_patches": {"type": "boolean"},
                    },
                },
            },
            "required": ["diff"],
        },
    ),
    MCPTool(
        name="index_repository",
        description="Trigger repository indexing for RAG knowledge base (async task)",
        input_schema={
            "type": "object",
            "properties": {
                "git_url": {
                    "type": "string",
                    "description": "Git repository HTTPS URL",
                },
                "access_token": {
                    "type": "string",
                    "description": "Personal access token for cloning",
                },
                "branch": {
                    "type": "string",
                    "description": "Branch to index (default: main)",
                },
                "index_depth": {
                    "type": "string",
                    "enum": ["shallow", "deep"],
                    "description": "Indexing mode (default: deep)",
                },
            },
            "required": ["git_url", "access_token"],
        },
    ),
    MCPTool(
        name="submit_feedback",
        description="Submit feedback on review comments for RLHF learning loop",
        input_schema={
            "type": "object",
            "properties": {
                "comment_id": {
                    "type": "string",
                    "description": "Review comment ID being feedback upon",
                },
                "action": {
                    "type": "string",
                    "enum": ["accepted", "rejected", "modified"],
                    "description": "Action taken on the comment",
                },
                "reason": {
                    "type": "string",
                    "enum": ["false_positive", "logic_error", "style_preference", "hallucination"],
                    "description": "Reason category for feedback",
                },
                "developer_comment": {
                    "type": "string",
                    "description": "Free-form explanation (1-1000 characters)",
                    "minLength": 1,
                    "maxLength": 1000,
                },
                "final_code_snapshot": {
                    "type": "string",
                    "description": "Final committed code snippet",
                },
            },
            "required": [
                "comment_id",
                "action",
                "reason",
                "developer_comment",
                "final_code_snapshot",
            ],
        },
    ),
]
