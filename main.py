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
from typing import Dict, Optional
import requests

from fastapi import FastAPI, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from loguru import logger

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
    x_platform: Optional[str] = Header(None, alias="X-Platform"),
    platform_override: Optional[str] = None,
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
            status_code=400,
            detail=f"Invalid platform: {platform}. Must be 'github' or 'gitea'"
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
    elif platform == "gitea":
        signature = request.headers.get("X-Gitea-Signature")
        secret = getattr(config, "PLATFORM_GITEA_WEBHOOK_SECRET", None)
    else:
        return True  # No verification for unknown platforms

    # Skip verification if secret not configured (development mode)
    if not secret:
        logger.warning(f"Webhook signature verification disabled for {platform}")
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
        raise HTTPException(
            status_code=401,
            detail="Invalid webhook signature"
        )

    return True


# =============================================================================
# API Endpoints (v1)
# =============================================================================

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "CortexReview Platform",
        "version": "2.0.0",
        "status": "operational",
        "platform": PLATFORM,
        "docs": "/docs",
        "metrics": "/metrics",
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
    from adapters.github import GitHubAdapter
    from adapters.gitea import GiteaAdapter

    # Parse webhook payload
    try:
        payload = await request.json()
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON payload: {e}"
        )

    # Select platform adapter
    if platform == "github":
        adapter = GitHubAdapter(token=config.GITHUB_TOKEN or "")
    else:  # gitea
        adapter = GiteaAdapter(
            host=config.GITEA_HOST,
            token=config.GITEA_TOKEN
        )

    # Parse webhook to PRMetadata
    try:
        metadata = adapter.parse_webhook(payload, platform)
    except (ValueError, KeyError) as e:
        logger.error(f"Failed to parse webhook: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to parse webhook payload: {e}"
        )

    # Generate trace_id for request correlation
    trace_id = str(uuid.uuid4())

    # Dispatch to Celery task (async processing per Constitution VII)
    # TODO: Implement in Phase 3 with Celery integration
    # task_result = process_code_review.delay(metadata.dict(), trace_id)

    logger.info(
        f"Webhook received: platform={platform}, "
        f"repo={metadata.repo_id}, pr={metadata.pr_number}, "
        f"trace_id={trace_id}"
    )

    # Return 202 Accepted with task ID (placeholder for Phase 3)
    return JSONResponse(
        status_code=202,
        content={
            "message": "Webhook accepted, processing asynchronously",
            "task_id": trace_id,  # Placeholder: will be Celery task ID in Phase 3
            "trace_id": trace_id,
            "status": "pending",
        }
    )


@app.get(f"{api_v1_prefix}/tasks/{{task_id}}")
async def get_task_status(
    task_id: str,
    config: Config = Depends(get_config),
):
    """
    Get status of async code review task.

    Args:
        task_id: Celery task ID from webhook response
        config: Application configuration

    Returns:
        JSON response with task status and result if completed

    Raises:
        HTTPException: If task not found

    TODO: Implement in Phase 3 with Celery result backend integration
    """
    # Placeholder: In Phase 3, query Celery result backend
    return {
        "task_id": task_id,
        "status": "pending",  # Placeholder
        "result": None,
        "error": None,
    }


@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint.

    Returns Prometheus-formatted metrics for observability.

    TODO: Implement in Phase 6 (Observability) with prometheus_client
    """
    # Placeholder: In Phase 6, return prometheus_client metrics
    return {
        "message": "Metrics endpoint - to be implemented in Phase 6",
    }


@app.get("/mcp/manifest")
async def get_mcp_manifest():
    """
    MCP (Model Context Protocol) manifest for IDE integration.

    Returns JSON-RPC tool schema for IDE agents to discover available tools.

    TODO: Implement in Phase 7 (IDE Integration)
    """
    # Placeholder: In Phase 7, return MCP manifest
    return {
        "name": "CortexReview-Agent",
        "version": "1.0.0",
        "description": "AI-powered code review platform with RAG and RLHF",
        "tools": [
            {
                "name": "analyze_diff",
                "description": "Analyze code diff and provide review comments",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "diff": {"type": "string", "description": "Code diff to analyze"},
                        "repo_id": {"type": "string", "description": "Repository identifier"},
                    },
                    "required": ["diff"],
                },
            }
        ],
    }


# =============================================================================
# Legacy Endpoints (Phase 1 Compatibility)
# =============================================================================

@app.post("/codereview")
async def analyze_code_legacy(request_body: Dict):
    """
    Legacy webhook endpoint for Phase 1 Gitea integration.

    DEPRECATED: Use /v1/webhook/gitea instead.
    Maintained for backward compatibility during migration.
    """
    from codereview.copilot import Copilot
    from gitea.client import GiteaClient
    from utils.utils import create_comment, extract_info_from_request
    from time import sleep

    # Initialize legacy clients
    gitea_client = GiteaClient(config.GITEA_HOST, config.GITEA_TOKEN)
    copilot = Copilot(config)

    # Extract webhook info
    owner, repo, sha, ref, pusher, full_name, title, commit_url = (
        extract_info_from_request(request_body)
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

                content = (
                    f"Code Review: {title}\n{commit_url}\n\n审查结果: \n{issue_url}"
                )
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
async def test_code_review(request_body: str):
    """
    Manual testing endpoint for code review.

    DEPRECATED: Use /v1/review direct API (Phase 7).
    """
    from codereview.copilot import Copilot

    copilot = Copilot(config)
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
        access_log=True,
        workers=1,
        reload=True,
    )

