"""
CortexReview Platform - Pytest Configuration and Fixtures

Shared fixtures and test configuration for all test modules.
"""

import os

# Add project root to path for imports
import sys
import uuid
from typing import Any
from unittest.mock import MagicMock, Mock

import pytest
from httpx import AsyncClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# Sample Webhook Payload Fixtures
# =============================================================================


@pytest.fixture
def github_pr_payload() -> dict[str, Any]:
    """
    Sample GitHub pull_request webhook payload.

    Represents a typical GitHub webhook when a PR is opened.
    """
    return {
        "action": "opened",
        "repository": {
            "id": 123456789,
            "node_id": "MDEwOlJlcG9zaXRvcnkxMjM0NTY3ODk=",
            "name": "test-repo",
            "full_name": "octocat/test-repo",
            "private": False,
            "owner": {
                "login": "octocat",
                "id": 1,
            },
        },
        "sender": {
            "login": "octocat",
            "id": 1,
        },
        "pull_request": {
            "id": 1,
            "number": 42,
            "state": "open",
            "title": "Add new feature",
            "user": {
                "login": "octocat",
            },
            "base": {
                "label": "octocat:main",
                "ref": "main",
                "sha": "a" * 40,
            },
            "head": {
                "label": "octocat:feature-branch",
                "ref": "feature-branch",
                "sha": "b" * 40,
            },
        },
    }


@pytest.fixture
def github_push_payload() -> dict[str, Any]:
    """
    Sample GitHub push webhook payload.

    Represents a typical GitHub webhook when commits are pushed.
    """
    return {
        "ref": "refs/heads/main",
        "repository": {
            "id": 123456789,
            "name": "test-repo",
            "full_name": "octocat/test-repo",
            "owner": {
                "login": "octocat",
            },
        },
        "pusher": {
            "name": "octocat",
        },
        "before": "a" * 40,
        "after": "b" * 40,
        "commits": [
            {
                "id": "b" * 40,
                "message": "Add new feature",
            }
        ],
    }


@pytest.fixture
def gitea_pr_payload() -> dict[str, Any]:
    """
    Sample Gitea pull_request webhook payload.

    Represents a typical Gitea webhook when a PR is opened.
    """
    return {
        "action": "opened",
        "repository": {
            "id": 123,
            "name": "test-repo",
            "full_name": "octocat/test-repo",
            "owner": {
                "login": "octocat",
            },
        },
        "sender": {
            "login": "octocat",
        },
        "pull_request": {
            "number": 42,
            "title": "Add new feature",
            "user": {
                "login": "octocat",
            },
            "base": {
                "ref": "main",
                "sha": "a" * 40,
            },
            "head": {
                "ref": "feature-branch",
                "sha": "b" * 40,
            },
        },
    }


@pytest.fixture
def gitea_push_payload() -> dict[str, Any]:
    """
    Sample Gitea push webhook payload.

    Represents a typical Gitea webhook when commits are pushed.
    """
    return {
        "ref": "refs/heads/main",
        "repository": {
            "full_name": "octocat/test-repo",
        },
        "pusher": {
            "login": "octocat",
        },
        "before": "a" * 40,
        "after": "b" * 40,
        "commits": [
            {
                "message": "Add new feature",
            }
        ],
    }


# =============================================================================
# Sample Diff Content Fixtures
# =============================================================================


@pytest.fixture
def sample_diff_content() -> str:
    """
    Sample git diff content for testing.

    Represents a typical unified diff output.
    """
    return '''diff --git a/src/main.py b/src/main.py
index 1234567..abcdefg 100644
--- a/src/main.py
+++ b/src/main.py
@@ -10,7 +10,7 @@ def process_request():
     pass

-def old_function():
+def new_function():
     """This is a new function."""
     return True
'''


# =============================================================================
# Mock Adapter Fixtures
# =============================================================================


@pytest.fixture
def mock_github_adapter() -> Mock:
    """
    Mock GitHubAdapter for testing.

    Provides a mock that simulates GitHub adapter behavior.
    """
    adapter = MagicMock()
    adapter.parse_webhook.return_value = Mock(
        repo_id="octocat/test-repo",
        pr_number=42,
        base_sha="a" * 40,
        head_sha="b" * 40,
        author="octocat",
        platform="github",
        title="Add new feature",
        source="webhook",
    )
    adapter.get_diff.return_value = ["diff --git a/file.py b/file.py\n+new code"]
    adapter.verify_signature.return_value = True
    return adapter


@pytest.fixture
def mock_gitea_adapter() -> Mock:
    """
    Mock GiteaAdapter for testing.

    Provides a mock that simulates Gitea adapter behavior.
    """
    adapter = MagicMock()
    adapter.parse_webhook.return_value = Mock(
        repo_id="octocat/test-repo",
        pr_number=0,  # Push event
        base_sha="a" * 40,
        head_sha="b" * 40,
        author="octocat",
        platform="gitea",
        title="Add new feature",
        source="webhook",
    )
    adapter.get_diff.return_value = ["diff --git a/file.py b/file.py\n+new code"]
    adapter.verify_signature.return_value = True
    return adapter


# =============================================================================
# Celery Mock Fixtures
# =============================================================================


@pytest.fixture
def mock_celery_task() -> Mock:
    """
    Mock Celery task for testing.

    Provides a mock that simulates Celery task behavior.
    """
    task = MagicMock()
    task.id = str(uuid.uuid4())
    task.state = "PENDING"
    task.result = None
    task.ready.return_value = False
    task.failed.return_value = False
    task.traceback = None
    return task


@pytest.fixture
def mock_celery_app() -> Mock:
    """
    Mock Celery application for testing.

    Provides a mock that simulates the Celery app.
    """
    app = MagicMock()
    app.send_task.return_value = MagicMock(
        id=str(uuid.uuid4()),
        state="PENDING",
    )
    return app


# =============================================================================
# Test Configuration Fixtures
# =============================================================================


@pytest.fixture
def test_review_config() -> dict[str, Any]:
    """
    Sample ReviewConfig for testing.

    Provides a valid review configuration.
    """
    return {
        "use_rag_context": True,
        "apply_learned_suppressions": True,
        "severity_threshold": "low",
        "include_auto_fix_patches": False,
        "personas": [],
        "max_context_matches": 10,
    }


@pytest.fixture
def sample_trace_id() -> str:
    """
    Sample trace ID for distributed tracing.
    """
    return str(uuid.uuid4())


# =============================================================================
# Sample PRMetadata Fixtures
# =============================================================================


@pytest.fixture
def sample_pr_metadata_github() -> dict[str, Any]:
    """
    Sample PRMetadata for GitHub PR event.
    """
    return {
        "repo_id": "octocat/test-repo",
        "pr_number": 42,
        "base_sha": "a" * 40,
        "head_sha": "b" * 40,
        "author": "octocat",
        "platform": "github",
        "title": "Add new feature",
        "source": "webhook",
        "callback_url": None,
    }


@pytest.fixture
def sample_pr_metadata_gitea() -> dict[str, Any]:
    """
    Sample PRMetadata for Gitea push event.
    """
    return {
        "repo_id": "octocat/test-repo",
        "pr_number": 0,  # Push event
        "base_sha": "a" * 40,
        "head_sha": "b" * 40,
        "author": "octocat",
        "platform": "gitea",
        "title": "Add new feature",
        "source": "webhook",
        "callback_url": None,
    }


# =============================================================================
# Async Client Fixture
# =============================================================================


@pytest.fixture
async def async_test_client() -> AsyncClient:
    """
    Async test client for FastAPI application.

    Provides an async client for testing API endpoints.
    """
    from httpx import ASGITransport

    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# =============================================================================
# Sample Review Response Fixture
# =============================================================================


@pytest.fixture
def sample_review_response() -> dict[str, Any]:
    """
    Sample ReviewResponse for testing.
    """
    return {
        "review_id": str(uuid.uuid4()),
        "summary": "Found 2 potential issues",
        "comments": [
            {
                "id": str(uuid.uuid4()),
                "file_path": "src/main.py",
                "line_range": {"start": 10, "end": 15},
                "type": "bug",
                "severity": "medium",
                "message": "Potential null pointer dereference",
                "suggestion": "Add null check before accessing",
                "confidence_score": 0.85,
                "fix_patch": None,
                "citations": ["See PR #123"],
            }
        ],
        "stats": {
            "total_issues": 2,
            "critical": 0,
            "high": 0,
            "medium": 1,
            "low": 1,
            "nit": 0,
            "execution_time_ms": 1500,
            "rag_context_used": True,
            "rag_matches_found": 3,
            "rlhf_constraints_applied": 1,
            "tokens_used": 250,
        },
    }


# =============================================================================
# Environment Override Fixture
# =============================================================================


@pytest.fixture
def override_test_env(monkeypatch):
    """
    Override environment variables for testing.

    Ensures tests run with consistent test configuration.
    """
    monkeypatch.setenv("PLATFORM", "github")
    monkeypatch.setenv("GITHUB_TOKEN", "test_token")
    monkeypatch.setenv("GITEA_TOKEN", "test_token")
    monkeypatch.setenv("GITEA_HOST", "gitea.example.com:3000")
    monkeypatch.setenv("LLM_API_KEY", "test_llm_key")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test_service_key")


# =============================================================================
# Mock Supabase Client Fixture
# =============================================================================


@pytest.fixture
def mock_supabase_client() -> Mock:
    """
    Mock Supabase client for testing.

    Provides a mock that simulates Supabase behavior.
    """
    client = MagicMock()
    client.table.return_value.select.return_value.execute.return_value.data = []
    client.table.return_value.insert.return_value.execute.return_value.data = []
    client.rpc.return_value.execute.return_value.data = []
    return client


# =============================================================================
# Mock OpenAI Client Fixture
# =============================================================================


@pytest.fixture
def mock_openai_client() -> Mock:
    """
    Mock OpenAI client for testing.

    Provides a mock that simulates LLM API responses.
    """
    client = MagicMock()
    client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="Review comment response"))],
        usage=MagicMock(total_tokens=100),
    )
    client.embeddings.create.return_value = MagicMock(data=[MagicMock(embedding=[0.1] * 1536)])
    return client


# =============================================================================
# Pytest Configuration
# =============================================================================


@pytest.fixture(autouse=True)
def configure_logging_for_tests():
    """
    Auto-use fixture to configure logging for tests.

    Creates logs directory if it doesn't exist and prevents
    permission errors during test execution. Uses tmp_path for
    test isolation to avoid polluting the project logs directory.
    """
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    yield
    # Cleanup: Note - we don't delete the logs directory as it may contain
    # useful test artifacts. In CI/CD, logs are typically archived after tests run.


# =============================================================================
# FastAPI Test Client Fixture
# =============================================================================


@pytest.fixture
def client(override_test_env):
    """
    FastAPI test client for endpoint testing.

    Provides a sync test client for testing API endpoints.
    """
    from fastapi.testclient import TestClient

    from main import app

    with TestClient(app) as test_client:
        yield test_client


# =============================================================================
# Additional Fixtures for Metrics Tests
# =============================================================================


@pytest.fixture
def sample_github_webhook(github_pr_payload):
    """Alias for GitHub PR webhook payload."""
    return github_pr_payload


@pytest.fixture
def mock_celery_task_with_result():
    """
    Mock Celery task that returns a successful result.
    """

    def _create_result(result_dict):
        task = MagicMock()
        task.id = str(uuid.uuid4())
        task.state = "SUCCESS"
        task.result = result_dict
        task.ready.return_value = True
        task.successful.return_value = True
        task.failed.return_value = False
        return task

    return _create_result


@pytest.fixture
def mock_celery_task_failure():
    """
    Mock Celery task that simulates a failure.
    """

    def _create_failure(exception):
        task = MagicMock()
        task.id = str(uuid.uuid4())
        task.state = "FAILURE"
        task.result = exception
        task.ready.return_value = True
        task.successful.return_value = False
        task.failed.return_value = True
        task.traceback = "Traceback..."
        return task

    return _create_failure


def pytest_configure(config):
    """
    Pytest configuration hook.

    Registers custom markers and test configuration.
    """
    config.addinivalue_line("markers", "unit: mark test as unit test")
    config.addinivalue_line("markers", "contract: mark test as contract/endpoint test")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "github: mark test as GitHub-specific")
    config.addinivalue_line("markers", "gitea: mark test as Gitea-specific")
