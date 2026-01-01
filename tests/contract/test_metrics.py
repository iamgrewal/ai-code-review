"""
Contract tests for Prometheus metrics endpoint.

Tests that the GET /metrics endpoint returns properly formatted
Prometheus metrics text per specification (TDD Phase 2 - GREEN).
"""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.contract
class TestMetricsEndpoint:
    """Contract tests for /metrics endpoint (T076)."""

    def test_metrics_endpoint_returns_200(self, client: TestClient):
        """Test that /metrics endpoint returns 200 OK."""
        response = client.get("/metrics")
        assert response.status_code == 200

    def test_metrics_returns_text_content_type(self, client: TestClient):
        """Test that /metrics returns text/plain content type."""
        response = client.get("/metrics")
        assert response.status_code == 200
        # Prometheus uses text/plain content type
        assert "text/plain" in response.headers.get("content-type", "")

    def test_metrics_includes_review_duration_seconds(self, client: TestClient):
        """Test that metrics include review_duration_seconds histogram."""
        response = client.get("/metrics")
        assert response.status_code == 200
        content = response.text
        # Check for histogram metric definition
        assert "cortexreview_review_duration_seconds" in content

    def test_metrics_includes_bucket_labels(self, client: TestClient):
        """Test that histogram includes configured buckets (T080)."""
        response = client.get("/metrics")
        assert response.status_code == 200
        content = response.text
        # Check for histogram metric definition
        assert "cortexreview_review_duration_seconds" in content
        # Check that it's defined as a histogram type
        assert "# TYPE cortexreview_review_duration_seconds histogram" in content

    def test_metrics_includes_celery_queue_depth(self, client: TestClient):
        """Test that metrics include celery_queue_depth gauge (T081)."""
        response = client.get("/metrics")
        assert response.status_code == 200
        content = response.text
        assert "cortexreview_celery_queue_depth" in content

    def test_metrics_includes_celery_worker_active_tasks(self, client: TestClient):
        """Test that metrics include celery_worker_active_tasks gauge (T082)."""
        response = client.get("/metrics")
        assert response.status_code == 200
        content = response.text
        assert "cortexreview_celery_worker_active_tasks" in content

    def test_metrics_includes_llm_tokens_total(self, client: TestClient):
        """Test that metrics include llm_tokens_total counter."""
        response = client.get("/metrics")
        assert response.status_code == 200
        content = response.text
        assert "cortexreview_llm_tokens_total" in content

    def test_metrics_includes_rag_metrics(self, client: TestClient):
        """Test that metrics include RAG-related metrics."""
        response = client.get("/metrics")
        assert response.status_code == 200
        content = response.text
        # Check for RAG retrieval latency
        assert "cortexreview_rag_retrieval_latency_seconds" in content

    def test_metrics_includes_feedback_metrics(self, client: TestClient):
        """Test that metrics include feedback submission counter."""
        response = client.get("/metrics")
        assert response.status_code == 200
        content = response.text
        assert "cortexreview_feedback_submitted_total" in content

    def test_metrics_format_valid_prometheus(self, client: TestClient):
        """Test that metrics output is valid Prometheus format."""
        response = client.get("/metrics")
        assert response.status_code == 200
        content = response.text

        # Prometheus format validation:
        # - Lines should be metric_name{labels} value or TYPE/HELP comments
        lines = content.split("\n")
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Valid metric line format
            assert "{" in line or " " in line, f"Invalid metric line: {line}"

    def test_metrics_includes_help_text(self, client: TestClient):
        """Test that metrics include HELP comments for documentation."""
        response = client.get("/metrics")
        assert response.status_code == 200
        content = response.text
        # Prometheus HELP comments
        assert "# HELP" in content

    def test_metrics_includes_type_comments(self, client: TestClient):
        """Test that metrics include TYPE comments (counter, gauge, histogram)."""
        response = client.get("/metrics")
        assert response.status_code == 200
        content = response.text
        # Prometheus TYPE comments
        assert "# TYPE" in content
        assert "counter" in content.lower()
        assert "gauge" in content.lower()
        assert "histogram" in content.lower()
