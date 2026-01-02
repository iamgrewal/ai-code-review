"""
CortexReview Platform - FastAPI Application

This module provides the API layer for the CortexReview platform, including:
- Platform-agnostic webhook endpoints (GitHub, Gitea)
- Async task dispatch via Celery
- Task status polling endpoint
- Prometheus metrics endpoint
- MCP manifest for IDE integration

Phase 2 Refactor: Multi-platform support with async processing.
"""

import os
import uuid
from contextlib import asynccontextmanager

import requests
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from loguru import logger

# Import metrics to register them with Prometheus client (T079)
import utils.metrics  # noqa: F401 - Registers metrics on import
from utils.config import Config
from utils.logger import setup_logging

# =============================================================================
# Global Configuration
# =============================================================================

# Load configuration (singleton instance)
config = Config()

# Setup logging
setup_logging()

# Platform adapter selection
PLATFORM = os.getenv("PLATFORM", "gitea").lower()


# =============================================================================
# Application Lifecycle Management
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles startup and shutdown events for:
    - Celery worker connectivity
    - Supabase connection health
    - Platform adapter initialization
    """
    # Startup
    logger.info(f"Starting CortexReview API (platform: {PLATFORM})")

    # Initialize platform adapters lazily on first request
    # (to avoid startup failures if platform APIs are unavailable)

    yield

    # Shutdown
    logger.info("Shutting down CortexReview API")


# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title="CortexReview Platform",
    description="Context-Aware AI Code Review Platform with RAG and RLHF",
    version="2.0.0",
    lifespan=lifespan,
)

# Include API versioning prefix
api_v1_prefix = "/v1"


# =============================================================================
# Dependencies
# =============================================================================


async def get_config() -> Config:
    """
    Dependency injection for Config.

    Returns:
        Config: Application configuration singleton
    """
    return config


async def verify_platform(
    x_platform: str | None = Header(None, alias="X-Platform"),
    platform_override: str | None = None,
) -> str:
    """
    Verify platform from request header or path parameter.

    Args:
        x_platform: Platform from X-Platform header
        platform_override: Platform from path parameter (takes precedence)

    Returns:
        str: Verified platform identifier ("github" or "gitea")

    Raises:
        HTTPException: If platform is invalid or not supported
    """
    # Path parameter takes precedence over header
    platform = platform_override or x_platform or PLATFORM

    if platform not in ("github", "gitea"):
        raise HTTPException(
            status_code=400, detail=f"Invalid platform: {platform}. Must be 'github' or 'gitea'"
        )

    return platform


async def verify_webhook_signature(
    request: Request,
    platform: str = Depends(verify_platform),
    config: Config = Depends(get_config),
) -> bool:
    """
    Verify webhook signature for security.

    Args:
        request: FastAPI request object
        platform: Verified platform identifier
        config: Application configuration

    Returns:
        bool: True if signature valid

    Raises:
        HTTPException: If signature verification fails
    """
    # Get signature header based on platform
    if platform == "github":
        signature = request.headers.get("X-Hub-Signature-256")
        secret = getattr(config, "PLATFORM_GITHUB_WEBHOOK_SECRET", None)
        # Check opt-out env var (T038)
        verify_enabled = getattr(config, "PLATFORM_GITHUB_VERIFY_SIGNATURE", True)
    elif platform == "gitea":
        signature = request.headers.get("X-Gitea-Signature")
        secret = getattr(config, "PLATFORM_GITEA_WEBHOOK_SECRET", None)
        # Check opt-out env var (T038)
        verify_enabled = getattr(config, "PLATFORM_GITEA_VERIFY_SIGNATURE", True)
    else:
        return True  # No verification for unknown platforms

    # Skip verification if disabled via env var (T038)
    if not verify_enabled:
        logger.info(f"Webhook signature verification disabled for {platform} via env var")
        return True

    # Skip verification if secret not configured (development mode)
    if not secret:
        logger.warning(f"Webhook signature verification disabled for {platform} (no secret)")
        return True

    # Get raw payload
    payload = await request.body()

    # Verify signature using platform adapter
    if platform == "github":
        from adapters.github import GitHubAdapter

        adapter = GitHubAdapter(token="", verify_signature=True)
    else:  # gitea
        from adapters.gitea import GiteaAdapter

        adapter = GiteaAdapter(host="", token="", verify_signature=True)

    is_valid = adapter.verify_signature(payload, signature or "", secret)

    if not is_valid:
        logger.warning(f"Invalid webhook signature for {platform}")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    return True


# =============================================================================
# API Endpoints (v1)
# =============================================================================


@app.get("/")
async def root():
    """Root endpoint with API information (T095)."""
    return {
        "name": "CortexReview Platform",
        "version": "2.0.0",
        "status": "operational",
        "platform": PLATFORM,
        "docs": {
            "swagger": "/docs",
            "redoc": "/redoc",
            "openapi_json": "/v1/openapi.json",
            "openapi_yaml": "/v1/openapi.yaml",
        },
        "mcp": {
            "manifest": "/mcp/manifest",
            "tools": {
                "analyze_diff": "/v1/mcp/tools/analyze_diff",
                "index_repository": "/v1/mcp/tools/index_repository",
                "submit_feedback": "/v1/mcp/tools/submit_feedback",
            },
        },
        "endpoints": {
            "webhooks": "/v1/webhook/{platform}",
            "tasks": "/v1/tasks/{task_id}",
            "indexing": "/v1/repositories/{repo_id}/index",
            "metrics": "/metrics",
            "health": "/health",
        },
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestration."""
    return {
        "status": "healthy",
        "platform": PLATFORM,
    }


@app.post(f"{api_v1_prefix}/webhook/{{platform}}")
async def receive_webhook(
    platform: str,
    request: Request,
    config: Config = Depends(get_config),
    signature_verified: bool = Depends(verify_webhook_signature),
):
    """
    Receive platform webhook and dispatch to Celery task.

    Args:
        platform: Platform identifier (github or gitea)
        request: FastAPI request with webhook payload
        config: Application configuration
        signature_verified: Verified webhook signature

    Returns:
        JSON response with task ID for polling

    Raises:
        HTTPException: If webhook parsing fails
    """
    import json

    from adapters.gitea import GiteaAdapter
    from adapters.github import GitHubAdapter
    from worker import process_code_review

    # Parse webhook payload
    try:
        payload = await request.json()
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {e}")

    # Select platform adapter
    if platform == "github":
        adapter = GitHubAdapter(token=config.GITHUB_TOKEN or "")
    else:  # gitea
        adapter = GiteaAdapter(host=config.GITEA_HOST, token=config.GITEA_TOKEN)

    # Parse webhook to PRMetadata (T037)
    try:
        metadata = adapter.parse_webhook(payload, platform)
    except (ValueError, KeyError) as e:
        logger.error(f"Failed to parse webhook: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to parse webhook payload: {e}")

    # Generate trace_id for request correlation (T044)
    trace_id = str(uuid.uuid4())

    # Dispatch to Celery task (async processing per Constitution VII) (T037)
    task_result = process_code_review.delay(metadata.model_dump(), trace_id)

    logger.bind(
        trace_id=trace_id, platform=platform, repo_id=metadata.repo_id, pr_number=metadata.pr_number
    ).info(
        f"Webhook received: platform={platform}, "
        f"repo={metadata.repo_id}, pr={metadata.pr_number}, "
        f"trace_id={trace_id}, task_id={task_result.id}"
    )

    # Return 202 Accepted with task ID (T037)
    return JSONResponse(
        status_code=202,
        content={
            "message": "Webhook accepted, processing asynchronously",
            "task_id": task_result.id,
            "trace_id": trace_id,
            "status": "pending",
        },
    )


@app.get(f"{api_v1_prefix}/tasks/{{task_id}}")
async def get_task_status(
    task_id: str,
    config: Config = Depends(get_config),
):
    """
    Get status of async code review task (T039).

    Args:
        task_id: Celery task ID from webhook response
        config: Application configuration

    Returns:
        JSON response with task status and result if completed

    Raises:
        HTTPException: If task not found
    """
    from celery.result import AsyncResult

    from celery_app import app as celery_app

    # Query Celery result backend for task status (T039)
    result = AsyncResult(task_id, app=celery_app)

    # Map Celery states to ReviewStatus enum (T039)
    status_mapping = {
        "PENDING": "queued",
        "STARTED": "processing",
        "SUCCESS": "completed",
        "FAILURE": "failed",
        "RETRY": "processing",
        "REVOKED": "failed",
    }

    status = status_mapping.get(result.state, "queued")

    response_data = {
        "task_id": task_id,
        "status": status,
        "result": None,
        "error": None,
    }

    # Return result if completed (T039)
    if result.successful():
        response_data["result"] = result.result
    elif result.failed():
        response_data["error"] = str(result.result)
        # Include traceback if available
        if hasattr(result, "traceback") and result.traceback:
            response_data["traceback"] = result.traceback

    return response_data


@app.post(f"{api_v1_prefix}/repositories/{{repo_id:path}}/index")
async def trigger_indexing(
    repo_id: str,
    request_data: dict,
    config: Config = Depends(get_config),
):
    """
    Trigger repository indexing for RAG knowledge base (T051-T055).

    Clones repository, chunks code, generates embeddings, stores in Supabase.
    Runs as async Celery task for long-running operations.

    Args:
        repo_id: Repository identifier (e.g., "owner/repo")
        request_data: Indexing request body with git_url, access_token, branch, index_depth
        config: Application configuration

    Returns:
        JSON response with task ID for polling

    Raises:
        HTTPException: If Supabase not configured or request invalid
    """
    from models.indexing import IndexingRequest
    from worker import index_repository

    # Validate Supabase configuration (support both external and local)
    has_external_supabase = bool(config.SUPABASE_URL and config.SUPABASE_SERVICE_KEY)
    has_local_supabase = bool(config.SUPABASE_DB_URL)

    if not has_external_supabase and not has_local_supabase:
        raise HTTPException(
            status_code=503,
            detail="Supabase configuration required for indexing. "
            "Set SUPABASE_URL + SUPABASE_SERVICE_KEY for external Supabase Cloud, "
            "or SUPABASE_DB_URL for local Supabase deployment.",
        )

    # Parse request
    try:
        indexing_request = IndexingRequest(**request_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid indexing request: {e}")

    # Generate trace_id for request correlation
    trace_id = str(uuid.uuid4())

    # Dispatch to Celery task
    task_result = index_repository.delay(
        repo_id=repo_id,
        git_url=indexing_request.git_url,
        access_token=indexing_request.access_token,
        branch=indexing_request.branch,
        depth=indexing_request.index_depth.value,
        trace_id=trace_id,
    )

    logger.bind(
        trace_id=trace_id,
        repo_id=repo_id,
        branch=indexing_request.branch,
        task_id=task_result.id,
    ).info(
        f"Repository indexing triggered: repo_id={repo_id}, "
        f"branch={indexing_request.branch}, depth={indexing_request.index_depth.value}"
    )

    # Return 202 Accepted with task ID
    return JSONResponse(
        status_code=202,
        content={
            "message": "Repository indexing started",
            "task_id": task_result.id,
            "trace_id": trace_id,
            "repo_id": repo_id,
            "status": "pending",
        },
    )


@app.post(f"{api_v1_prefix}/feedback")
async def submit_feedback(
    request_data: dict,
    config: Config = Depends(get_config),
):
    """
    Submit feedback on review comment for RLHF learning loop (T047-T054).

    Accepts user feedback (accepted/rejected/modified) and triggers
    async processing to create learned constraints from rejected feedback.

    Args:
        request_data: FeedbackRequest with comment_id, action, reason, etc.
        config: Application configuration

    Returns:
        JSON response with task ID for polling

    Raises:
        HTTPException: If Supabase not configured or request invalid
    """
    from models.feedback import FeedbackRequest
    from worker import process_feedback

    # Validate Supabase configuration
    if not config.SUPABASE_URL or not config.SUPABASE_SERVICE_KEY:
        raise HTTPException(
            status_code=503,
            detail="Supabase configuration required for feedback. "
            "Set SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables.",
        )

    # Parse request
    try:
        feedback = FeedbackRequest(**request_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid feedback request: {e}")

    # Extract required parameters
    review_id = request_data.get("review_id", f"unknown:{uuid.uuid4()}")
    repo_id = request_data.get("repo_id", "unknown")

    # Generate trace_id for request correlation
    trace_id = str(uuid.uuid4())

    # Dispatch to Celery task
    task_result = process_feedback.delay(
        feedback_dict=feedback.model_dump(),
        review_id=review_id,
        repo_id=repo_id,
        trace_id=trace_id,
    )

    logger.bind(
        trace_id=trace_id,
        comment_id=feedback.comment_id,
        action=feedback.action,
        task_id=task_result.id,
    ).info(f"Feedback submitted: action={feedback.action}, comment_id={feedback.comment_id}")

    # Return 202 Accepted with task ID
    return JSONResponse(
        status_code=202,
        content={
            "message": "Feedback submitted for processing",
            "task_id": task_result.id,
            "trace_id": trace_id,
            "action": feedback.action,
            "status": "pending",
        },
    )


@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint (T079).

    Returns Prometheus-formatted metrics for observability per Constitution XI.

    Metrics exposed:
    - review_duration_seconds: Histogram with buckets (0.1, 0.5, 1, 5, 10, 30, 60, +Inf) (T080)
    - celery_queue_depth: Gauge for queue monitoring (T081)
    - celery_worker_active_tasks: Gauge for worker utilization (T082)
    - llm_tokens_total: Counter for token usage by model
    - rag_retrieval_latency_seconds: Summary for RAG performance
    - feedback_submitted_total: Counter for RLHF feedback
    - Additional error, webhook, and indexing metrics

    Returns:
        str: Prometheus text-format metrics
    """
    from prometheus_client import REGISTRY, exposition

    # Generate latest metrics in Prometheus text format
    return Response(
        content=exposition.generate_latest(REGISTRY),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@app.get("/mcp/manifest")
async def get_mcp_manifest():
    """
    MCP (Model Context Protocol) manifest for IDE integration (T092).

    Returns JSON-RPC tool schema for IDE agents (Cursor, Windsurf, etc.)
    to discover and invoke available CortexReview tools.

    Available tools:
    - analyze_diff: Analyze code diff with RAG context
    - index_repository: Trigger repository indexing for RAG knowledge base
    - submit_feedback: Submit RLHF feedback on review comments
    """
    from models.mcp import MCP_TOOLS, MCPManifest

    manifest = MCPManifest(
        name="CortexReview-Agent",
        version="1.0.0",
        description="AI-powered code review platform with RAG and RLHF",
        tools=MCP_TOOLS,
    )

    return manifest.model_dump()


@app.post(f"{api_v1_prefix}/mcp/tools/analyze_diff")
async def mcp_analyze_diff(
    request: dict,
    config: Config = Depends(get_config),
):
    """
    MCP tool: Analyze code diff and provide review comments (T093).

    IDE agents can invoke this tool to get AI-powered code review
    with optional RAG context from repository history.

    Args:
        request: Tool request with diff, optional repo_id, and config
        config: Application configuration

    Returns:
        MCPToolResponse with review results or task ID for async processing
    """
    from codereview.copilot import Copilot
    from models.mcp import MCPToolRequest, MCPToolResponse

    try:
        # Parse request
        tool_request = MCPToolRequest(
            tool_name="analyze_diff",
            arguments=request.get("arguments", {}),
            request_id=request.get("request_id") or str(uuid.uuid4()),
        )

        diff = tool_request.arguments.get("diff")
        if not diff:
            raise HTTPException(status_code=400, detail="Missing required argument: diff")

        # For synchronous MCP requests, process directly
        copilot = Copilot(config)
        review_result = copilot.code_review(diff)

        return MCPToolResponse(
            request_id=tool_request.request_id,
            tool_name="analyze_diff",
            success=True,
            result={"review": review_result},
        ).model_dump()

    except Exception as e:
        logger.error(f"MCP analyze_diff failed: {e}")
        raise HTTPException(status_code=500, detail=f"Tool execution failed: {e}")


@app.post(f"{api_v1_prefix}/mcp/tools/index_repository")
async def mcp_index_repository(
    request: dict,
    config: Config = Depends(get_config),
):
    """
    MCP tool: Trigger repository indexing for RAG knowledge base (T094).

    IDE agents can invoke this tool to trigger async repository indexing.
    Returns a Celery task ID for tracking indexing progress.

    Args:
        request: Tool request with git_url, access_token, branch, index_depth
        config: Application configuration

    Returns:
        MCPToolResponse with Celery task ID for async operation
    """
    from models.indexing import IndexingRequest
    from models.mcp import MCPToolRequest, MCPToolResponse
    from worker import index_repository

    try:
        # Parse request
        tool_request = MCPToolRequest(
            tool_name="index_repository",
            arguments=request.get("arguments", {}),
            request_id=request.get("request_id") or str(uuid.uuid4()),
        )

        # Validate indexing request
        indexing_request = IndexingRequest(**tool_request.arguments)

        # Generate trace_id for correlation
        trace_id = str(uuid.uuid4())

        # Dispatch to Celery task (async processing per Constitution VII)
        task_result = index_repository.delay(
            repo_id=indexing_request.git_url,
            git_url=indexing_request.git_url,
            access_token=indexing_request.access_token,
            branch=indexing_request.branch,
            depth=indexing_request.index_depth.value,
            trace_id=trace_id,
        )

        logger.bind(
            trace_id=trace_id, git_url=indexing_request.git_url, task_id=task_result.id
        ).info(f"Repository indexing triggered via MCP: task_id={task_result.id}")

        return MCPToolResponse(
            request_id=tool_request.request_id,
            tool_name="index_repository",
            success=True,
            result={
                "message": "Repository indexing started",
                "git_url": indexing_request.git_url,
                "branch": indexing_request.branch,
            },
            task_id=task_result.id,
        ).model_dump()

    except Exception as e:
        logger.error(f"MCP index_repository failed: {e}")
        raise HTTPException(status_code=500, detail=f"Tool execution failed: {e}")


@app.post(f"{api_v1_prefix}/mcp/tools/submit_feedback")
async def mcp_submit_feedback(
    request: dict,
    config: Config = Depends(get_config),
):
    """
    MCP tool: Submit feedback on review comments for RLHF (T094).

    IDE agents can invoke this tool to submit human feedback on review comments,
    enabling the learning loop to suppress false positives in future reviews.

    Args:
        request: Tool request with comment_id, action, reason, developer_comment, final_code_snapshot
        config: Application configuration

    Returns:
        MCPToolResponse with feedback submission result
    """
    from models.feedback import FeedbackRequest
    from models.mcp import MCPToolRequest, MCPToolResponse
    from worker import process_feedback

    try:
        # Parse request
        tool_request = MCPToolRequest(
            tool_name="submit_feedback",
            arguments=request.get("arguments", {}),
            request_id=request.get("request_id") or str(uuid.uuid4()),
        )

        # Validate feedback request
        feedback_request = FeedbackRequest(**tool_request.arguments)

        # Generate trace_id for correlation
        trace_id = str(uuid.uuid4())

        # Dispatch to Celery task (async processing per Constitution VII)
        task_result = process_feedback.delay(
            feedback_dict=feedback_request.model_dump(),
            trace_id=trace_id,
        )

        logger.bind(
            trace_id=trace_id,
            comment_id=feedback_request.comment_id,
            action=feedback_request.action,
            task_id=task_result.id,
        ).info(f"Feedback submitted via MCP: task_id={task_result.id}")

        return MCPToolResponse(
            request_id=tool_request.request_id,
            tool_name="submit_feedback",
            success=True,
            result={
                "message": "Feedback submitted for processing",
                "comment_id": feedback_request.comment_id,
                "action": feedback_request.action,
            },
            task_id=task_result.id,
        ).model_dump()

    except Exception as e:
        logger.error(f"MCP submit_feedback failed: {e}")
        raise HTTPException(status_code=500, detail=f"Tool execution failed: {e}")


@app.get(f"{api_v1_prefix}/openapi.json", include_in_schema=False)
async def openapi_spec():
    """
    OpenAPI 3.1.0 specification for v1 API (T095).

    Returns the complete OpenAPI spec for all v1 endpoints.
    This endpoint provides machine-readable API documentation
    for client SDK generation and API testing tools.
    """
    from fastapi.openapi.utils import get_openapi

    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="CortexReview Platform API",
        version="2.0.0",
        description="""
## Context-Aware AI Code Review Platform

CortexReview provides AI-powered code review with:
- **RAG**: Retrieval-Augmented Generation for context-aware reviews
- **RLHF**: Reinforcement Learning from Human Feedback for continuous improvement
- **Multi-Platform**: GitHub and Gitea webhook support
- **MCP**: Model Context Protocol for IDE agent integration

### Quick Start

1. **Webhook Integration**: POST `/v1/webhook/{platform}`
   - Configure your Git platform to send webhooks to this endpoint
   - Supported platforms: `github`, `gitea`

2. **Task Status**: GET `/v1/tasks/{task_id}`
   - Poll for async task completion after webhook submission

3. **MCP Integration**: GET `/mcp/manifest`
   - Discover available tools for IDE agents (Cursor, Windsurf, etc.)

### Authentication

All endpoints require appropriate authentication:
- Webhooks: HMAC-SHA256 signature verification
- API calls: Platform tokens (GitHub/Gitea)
- MCP: No auth (for local IDE integration)

### Response Codes

- `202 Accepted`: Async task started
- `200 OK`: Sync operation completed
- `400 Bad Request`: Invalid input
- `401 Unauthorized`: Signature verification failed
- `503 Service Unavailable`: Required services unavailable
        """,
        routes=app.routes,
    )

    # Add custom tags for better organization
    openapi_schema["tags"] = [
        {
            "name": "webhooks",
            "description": "Platform webhook endpoints for code review triggers",
        },
        {
            "name": "tasks",
            "description": "Async task status and monitoring",
        },
        {
            "name": "mcp",
            "description": "Model Context Protocol tools for IDE integration",
        },
        {
            "name": "repositories",
            "description": "Repository indexing and management",
        },
        {
            "name": "observability",
            "description": "Metrics and health monitoring",
        },
    ]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


@app.get(f"{api_v1_prefix}/spec", include_in_schema=False)
async def api_spec():
    """
    Alternative endpoint for OpenAPI spec (T095).

    Alias for /v1/openapi.json for convenience.
    """
    return await openapi_spec()


@app.get(f"{api_v1_prefix}/openapi.yaml", include_in_schema=False)
async def openapi_yaml():
    """
    OpenAPI 3.1.0 specification in YAML format (T095).

    Returns the OpenAPI spec as YAML for human-readable documentation.
    """
    import yaml
    from fastapi.openapi.utils import get_openapi

    if app.openapi_schema:
        openapi_schema = app.openapi_schema
    else:
        openapi_schema = get_openapi(
            title="CortexReview Platform API",
            version="2.0.0",
            description="Context-Aware AI Code Review Platform with RAG and RLHF",
            routes=app.routes,
        )
        app.openapi_schema = openapi_schema

    yaml_content = yaml.dump(openapi_schema, default_flow_style=False, sort_keys=False)
    return Response(
        content=yaml_content,
        media_type="text/yaml; charset=utf-8",
    )


# =============================================================================
# Legacy Endpoints (Phase 1 Compatibility)
# =============================================================================


@app.post("/codereview")
async def analyze_code_legacy(request_body: dict):
    """
    Legacy webhook endpoint for Phase 1 Gitea integration.

    DEPRECATED: Use /v1/webhook/gitea instead.
    Maintained for backward compatibility during migration.
    """
    from time import sleep

    from codereview.copilot import Copilot
    from gitea.client import GiteaClient
    from utils.utils import create_comment, extract_info_from_request

    # Initialize legacy clients
    gitea_client = GiteaClient(config.GITEA_HOST, config.GITEA_TOKEN)
    copilot = Copilot(config)

    # Extract webhook info
    owner, repo, sha, ref, pusher, full_name, title, commit_url = extract_info_from_request(
        request_body
    )

    if "[skip codereview]" in title:
        return {"message": "Skip codereview"}

    diff_blocks = gitea_client.get_diff_blocks(owner, repo, sha)
    if diff_blocks is None:
        return {"message": "Failed to get diff content"}

    current_issue_id = None
    ignored_file_suffix = config.IGNORED_FILE_SUFFIX.split(",")

    for i, diff_content in enumerate(diff_blocks, start=1):
        file_path = diff_content.split(" ")[0].split("/")
        file_name = file_path[-1]

        # Ignore the file if it's in the ignored list
        if ignored_file_suffix:
            for suffix in ignored_file_suffix:
                if file_name.endswith(suffix):
                    logger.warning(f"File {file_name} is ignored")
                    continue

        # Send the diff to AI for code analysis
        response = copilot.code_review(diff_content)

        comment = create_comment(file_name, diff_content, response)
        if i == 1:
            issue_res = gitea_client.create_issue(
                owner,
                repo,
                f"Code Review {title}",
                f"本次提交：{commit_url} \n\r 提交人：{pusher} \n\r {comment}",
                ref,
                pusher,
            )
            issue_url = issue_res["html_url"]
            current_issue_id = issue_res["number"]
            logger.success(f"The code review: {issue_url}")

            # Send a notification to the webhook
            if config.webhook and config.webhook.is_init:
                headers = {}
                if config.webhook.header_name and config.webhook.header_value:
                    headers = {config.webhook.header_name: config.webhook.header_value}

                content = f"Code Review: {title}\n{commit_url}\n\n审查结果: \n{issue_url}"
                request_body_str = config.webhook.request_body.format(
                    content=content,
                    mention=full_name,
                )
                webhook_payload = json.loads(request_body_str, strict=False)
                requests.post(
                    config.webhook.url,
                    headers=headers,
                    json=webhook_payload,
                )

        else:
            gitea_client.add_issue_comment(
                owner,
                repo,
                current_issue_id,
                comment,
            )

        logger.info("Sleep for 1.5 seconds...")
        sleep(1.5)

    # Add banner to the issue
    gitea_client.add_issue_comment(
        owner,
        repo,
        current_issue_id,
        copilot.banner,
    )

    return {"message": response}


@app.post("/test")
async def test_code_review(request: Request):
    """
    Manual testing endpoint for code review.

    Accepts raw text or JSON body containing code to review.

    DEPRECATED: Use /v1/review direct API (Phase 7).
    """
    from codereview.copilot import Copilot

    copilot = Copilot(config)

    # Try to parse as JSON first, otherwise use raw body
    try:
        json_data = await request.json()
        request_body = json_data.get("request_body", "")
        if not request_body:
            # If request_body not in JSON, use the entire JSON as string
            request_body = str(json_data)
    except Exception:
        # Not JSON, use raw body
        raw_body = await request.body()
        request_body = raw_body.decode("utf-8")

    logger.success("Test endpoint called")
    return {"message": copilot.code_review(request_body)}


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=3008,
        access_log=False,  # Disable uvicorn access log to avoid conflicts with loguru
        workers=1,
        reload=True,
    )
