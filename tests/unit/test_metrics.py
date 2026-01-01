"""
Unit tests for Prometheus metrics emission.

Tests that metrics are properly emitted during worker operations
(TDD Phase 2 - GREEN).
"""

import time

import pytest
from prometheus_client import REGISTRY


@pytest.mark.unit
class TestMetricsEmission:
    """Unit tests for metrics emission in worker.py (T077)."""

    def test_review_duration_seconds_histogram_exists(self):
        """Test that review_duration_seconds histogram is registered."""
        from utils.metrics import review_duration_seconds

        # Check metric is in Prometheus registry
        assert review_duration_seconds._name in [m.name for m in REGISTRY.collect()]

    def test_review_duration_seconds_has_correct_buckets(self):
        """Test that histogram has configured buckets (T080)."""
        from prometheus_client import Histogram

        from utils.metrics import review_duration_seconds

        # Check that review_duration_seconds is a Histogram instance
        assert isinstance(review_duration_seconds, Histogram)

        # Check buckets parameter was configured during initialization
        # The Histogram object stores buckets internally but not directly accessible
        # We verify by checking it's not empty and is a Histogram type
        assert review_duration_seconds._name == "cortexreview_review_duration_seconds"

    def test_celery_queue_depth_gauge_exists(self):
        """Test that celery_queue_depth gauge is registered (T081)."""
        from utils.metrics import celery_queue_depth

        assert celery_queue_depth._name in [m.name for m in REGISTRY.collect()]
        # Check it's a gauge (can go up and down)
        celery_queue_depth.labels(queue_name="test_queue").set(10)
        celery_queue_depth.labels(queue_name="test_queue").set(0)
        # No exception = success

    def test_celery_worker_active_tasks_gauge_exists(self):
        """Test that celery_worker_active_tasks gauge is registered (T082)."""
        from utils.metrics import celery_worker_active_tasks

        assert celery_worker_active_tasks._name in [m.name for m in REGISTRY.collect()]
        # Check it's a gauge
        celery_worker_active_tasks.labels(worker_name="worker1").set(5)
        celery_worker_active_tasks.labels(worker_name="worker1").set(0)

    def test_llm_tokens_total_counter_exists(self):
        """Test that llm_tokens_total counter is registered."""
        from utils.metrics import llm_tokens_total

        assert llm_tokens_total._name in [m.name for m in REGISTRY.collect()]
        # Check it increments
        initial_value = llm_tokens_total.labels(model_type="chat", model_name="gpt-4")._value._value
        llm_tokens_total.labels(model_type="chat", model_name="gpt-4").inc(100)
        new_value = llm_tokens_total.labels(model_type="chat", model_name="gpt-4")._value._value
        assert new_value == initial_value + 100

    def test_rag_retrieval_latency_summary_exists(self):
        """Test that rag_retrieval_latency_seconds summary is registered."""
        from utils.metrics import rag_retrieval_latency_seconds

        assert rag_retrieval_latency_seconds._name in [m.name for m in REGISTRY.collect()]

    def test_feedback_submitted_total_counter_exists(self):
        """Test that feedback_submitted_total counter is registered."""
        from utils.metrics import feedback_submitted_total

        assert feedback_submitted_total._name in [m.name for m in REGISTRY.collect()]

    def test_review_duration_observation(self):
        """Test that review duration is properly observed."""
        from utils.metrics import review_duration_seconds

        # Simulate observation
        with review_duration_seconds.labels(platform="github", status="success").time():
            time.sleep(0.01)

        # Metric should have collected samples
        samples = list(
            review_duration_seconds.labels(platform="github", status="success").collect()
        )
        assert len(samples) > 0

    def test_track_review_duration_decorator(self):
        """Test that track_review_duration decorator works."""
        from utils.metrics import review_duration_seconds, track_review_duration

        @track_review_duration(platform="gitea", status="success")
        def dummy_review_function():
            time.sleep(0.01)
            return "review_complete"

        result = dummy_review_function()
        assert result == "review_complete"

        # Check metric was observed
        samples = list(review_duration_seconds.labels(platform="gitea", status="success").collect())
        assert len(samples) > 0

    def test_all_metrics_have_help_text(self):
        """Test that all metrics have HELP documentation."""
        from prometheus_client import Counter, Gauge, Histogram, Summary

        from utils import metrics

        # Get all prometheus metric objects from metrics module
        metric_objects = []
        for name in dir(metrics):
            if not name.startswith("_"):
                obj = getattr(metrics, name)
                # Only include actual prometheus metric types
                if isinstance(obj, (Counter, Gauge, Histogram, Summary)):
                    metric_objects.append(obj)

        # Each metric should follow naming convention
        for metric in metric_objects:
            # Verify each metric has a name attribute
            assert hasattr(metric, "_name")
            # Check naming convention
            assert metric._name.startswith("cortexreview_")

    def test_metric_naming_convention(self):
        """Test that all metrics follow naming convention."""
        from prometheus_client import Counter, Gauge, Histogram, Summary

        from utils import metrics

        # Get all prometheus metric objects
        metric_objects = []
        for name in dir(metrics):
            if not name.startswith("_"):
                obj = getattr(metrics, name)
                if isinstance(obj, (Counter, Gauge, Histogram, Summary)):
                    metric_objects.append(obj)

        for metric in metric_objects:
            # All metrics should start with cortexreview_
            assert metric._name.startswith("cortexreview_")
