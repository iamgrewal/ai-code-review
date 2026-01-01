"""
Integration tests for metrics collection across request lifecycle.

Tests that metrics are properly emitted end-to-end from webhook
through task completion (TDD Phase 2 - GREEN).
"""

import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
class TestMetricsFlow:
    """Integration tests for metrics collection (T078)."""

    @pytest.mark.asyncio
    async def test_webhook_to_metrics_emission(
        self, client: TestClient, mock_celery_task, sample_github_webhook
    ):
        """Test that webhook triggers metrics emission (T078)."""
        # Send webhook
        response = client.post(
            "/v1/webhook/github",
            json=sample_github_webhook,
            headers={"X-Hub-Signature-256": "mock_signature"},
        )

        # Verify webhook accepted
        assert response.status_code == 202
        task_id = response.json()["task_id"]

        # Wait for task to complete
        time.sleep(0.1)

        # Query metrics endpoint
        metrics_response = client.get("/metrics")
        assert metrics_response.status_code == 200
        metrics_content = metrics_response.text

        # Verify webhook_received_total metric was emitted
        assert "cortexreview_webhook_received_total" in metrics_content
        assert 'platform="github"' in metrics_content

    @pytest.mark.asyncio
    async def test_review_duration_metric_emitted(
        self,
        client: TestClient,
        mock_celery_task_with_result,
        sample_github_webhook,
    ):
        """Test that review_duration_seconds histogram is emitted."""
        # Mock successful review
        mock_result = {
            "task_id": "test-task-123",
            "status": "success",
            "review_id": "review-123",
            "comment_count": 3,
            "duration_seconds": 2.5,
        }

        with patch(
            "worker.process_code_review.delay",
            return_value=mock_celery_task_with_result(mock_result),
        ):
            response = client.post(
                "/v1/webhook/github",
                json=sample_github_webhook,
                headers={"X-Hub-Signature-256": "mock_signature"},
            )

            assert response.status_code == 202

            # Wait for processing
            time.sleep(0.1)

            # Check metrics
            metrics_response = client.get("/metrics")
            metrics_content = metrics_response.text

            # Verify review duration metric exists
            assert "cortexreview_review_duration_seconds" in metrics_content

    def test_llm_tokens_metric_emitted(self):
        """Test that LLM token usage is tracked."""
        from utils.metrics import llm_tokens_total

        # Simulate token usage
        model_type = "chat"
        model_name = "gpt-4"
        tokens = 150

        llm_tokens_total.labels(model_type=model_type, model_name=model_name).inc(tokens)

        # Get metrics output
        from prometheus_client import exposition

        metrics_output = exposition.generate_latest(REGISTRY).decode("utf-8")

        # Verify token metric
        assert "cortexreview_llm_tokens_total" in metrics_output
        assert f'model_name="{model_name}"' in metrics_output
        assert "150" in metrics_output

    def test_celery_queue_depth_metric_updates(self):
        """Test that Celery queue depth gauge updates (T081)."""
        from prometheus_client import REGISTRY, exposition

        from utils.metrics import celery_queue_depth

        # Simulate queue depth changes
        queue_name = "celery"

        # Queue empty
        celery_queue_depth.labels(queue_name=queue_name).set(0)

        # Queue has tasks
        celery_queue_depth.labels(queue_name=queue_name).set(25)

        # Queue backed up
        celery_queue_depth.labels(queue_name=queue_name).set(150)

        # Get metrics
        metrics_output = exposition.generate_latest(REGISTRY).decode("utf-8")

        # Verify gauge value
        assert "cortexreview_celery_queue_depth" in metrics_output
        assert 'queue_name="celery"' in metrics_output

    def test_celery_worker_active_tasks_metric_updates(self):
        """Test that Celery worker active tasks gauge updates (T082)."""
        from utils.metrics import celery_worker_active_tasks

        # Simulate worker activity
        worker_name = "worker1@hostname"

        # Worker idle
        celery_worker_active_tasks.labels(worker_name=worker_name).set(0)

        # Worker busy
        celery_worker_active_tasks.labels(worker_name=worker_name).set(5)

        # Worker at capacity
        celery_worker_active_tasks.labels(worker_name=worker_name).set(10)

        # Get metrics
        from prometheus_client import exposition

        metrics_output = exposition.generate_latest(REGISTRY).decode("utf-8")

        # Verify gauge
        assert "cortexreview_celery_worker_active_tasks" in metrics_output
        assert f'worker_name="{worker_name}"' in metrics_output

    def test_rag_metrics_emitted_on_context_retrieval(self):
        """Test that RAG metrics are emitted during context retrieval."""
        from utils.metrics import rag_retrieval_latency_seconds, rag_retrieval_success_total

        repo_id = "test/repo"

        # Simulate RAG retrieval
        with rag_retrieval_latency_seconds.labels(repo_id=repo_id).time():
            time.sleep(0.05)  # Simulate retrieval latency
            rag_retrieval_success_total.labels(repo_id=repo_id).inc()

        # Get metrics
        from prometheus_client import exposition

        metrics_output = exposition.generate_latest(REGISTRY).decode("utf-8")

        # Verify RAG metrics
        assert "cortexreview_rag_retrieval_latency_seconds" in metrics_output
        assert "cortexreview_rag_retrieval_success_total" in metrics_output
        assert f'repo_id="{repo_id}"' in metrics_output

    def test_feedback_metrics_emitted_on_submission(self):
        """Test that feedback metrics are emitted."""
        from utils.metrics import feedback_submitted_total

        # Simulate different feedback actions
        for action in ["accepted", "rejected", "modified"]:
            feedback_submitted_total.labels(action=action).inc()

        # Get metrics
        from prometheus_client import exposition

        metrics_output = exposition.generate_latest(REGISTRY).decode("utf-8")

        # Verify feedback metrics
        assert "cortexreview_feedback_submitted_total" in metrics_output
        assert 'action="accepted"' in metrics_output
        assert 'action="rejected"' in metrics_output
        assert 'action="modified"' in metrics_output

    @pytest.mark.asyncio
    async def test_error_metrics_on_failure(
        self, client: TestClient, mock_celery_task_failure, sample_github_webhook
    ):
        """Test that error metrics are emitted on task failure."""
        with patch(
            "worker.process_code_review.delay",
            return_value=mock_celery_task_failure(Exception("Review failed")),
        ):
            response = client.post(
                "/v1/webhook/github",
                json=sample_github_webhook,
                headers={"X-Hub-Signature-256": "mock_signature"},
            )

            assert response.status_code == 202

            # Wait for error
            time.sleep(0.1)

            # Check metrics
            metrics_response = client.get("/metrics")
            metrics_content = metrics_response.text

            # Verify error metrics
            assert "cortexreview_error_total" in metrics_content

    def test_metrics_persist_across_requests(self):
        """Test that metrics persist and accumulate across multiple requests."""
        from utils.metrics import webhook_received_total

        # Simulate multiple webhooks
        for _ in range(5):
            webhook_received_total.labels(platform="github").inc()

        # Get metrics
        from prometheus_client import exposition

        metrics_output = exposition.generate_latest(REGISTRY).decode("utf-8")

        # Verify counter accumulated
        assert "cortexreview_webhook_received_total" in metrics_output
        assert 'platform="github"' in metrics_output
        # Should have value 5
        assert " 5" in metrics_output or "5.0" in metrics_output
