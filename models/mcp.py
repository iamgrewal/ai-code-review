"""
MCP (Model Context Protocol) models for CortexReview.

Defines JSON-RPC tool schemas for AI IDE agent integration.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field


class MCPTool(BaseModel):
    """
    Definition of an MCP tool available to IDE agents.

    Each tool represents an action that can be invoked by AI IDEs
    like Cursor, Windsurf, or other MCP-compatible agents.
    """

    name: str = Field(..., description="Tool identifier (snake_case)")
    description: str = Field(..., description="Human-readable tool description")
    input_schema: dict[str, Any] = Field(..., description="JSON-RPC input schema (JSON Schema format)")


class MCPManifest(BaseModel):
    """
    MCP manifest describing available tools for IDE agent integration.

    This manifest is exposed at GET /mcp/manifest and allows IDE agents
    to discover and invoke CortexReview capabilities directly.
    """

    name: str = Field(default="CortexReview-Agent", description="Agent name")
    version: str = Field(default="1.0.0", description="Agent version")
    description: str = Field(
        default="AI-powered code review platform with RAG and RLHF",
        description="Agent description",
    )
    tools: list[MCPTool] = Field(default_factory=list, description="Available tools")

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "name": "CortexReview-Agent",
                    "version": "1.0.0",
                    "description": "AI-powered code review platform with RAG and RLHF",
                    "tools": [
                        {
                            "name": "analyze_diff",
                            "description": "Analyzes a code diff for issues",
                            "input_schema": {
                                "type": "object",
                                "properties": {
                                    "diff": {"type": "string"},
                                    "config": {"type": "object"},
                                },
                                "required": ["diff"],
                            },
                        }
                    ],
                }
            ]
        }
