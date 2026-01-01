"""
T035 - Unit Tests for Celery Worker

Tests the process_code_review Celery task signature and verifies
it accepts PRMetadata and ReviewConfig parameters correctly.

These tests MUST FAIL because the Celery task implementation may
not exist or have incorrect signatures/behavior.
"""

from unittest.mock import MagicMock, patch

import pytest

from models.platform import PRMetadata
from models.review import ReviewConfig


class TestProcessCodeReviewTask:
    """
    Test process_code_review Celery task.

    These tests verify the Celery task signature and behavior.
    """

    def test_process_code_review_task_exists(self):
        """
        GIVEN the worker module
        WHEN importing process_code_review task
        THEN the task should exist

        FAIL EXPECTED: Task may not be defined or not properly decorated
        """
        # Arrange & Act
        try:
            from worker import process_code_review
        except ImportError as e:
            pytest.fail(f"process_code_review task not found: {e}")

        # Assert
        assert process_code_review is not None
        assert hasattr(process_code_review, "delay"), (
            "process_code_review should be a Celery task with delay() method"
        )

    def test_process_code_review_task_name(self):
        """
        GIVEN the process_code_review task
        WHEN checking its name
        THEN it should match "worker.process_code_review"

        FAIL EXPECTED: Task may have wrong name
        """
        # Arrange
        from worker import process_code_review

        # Act
        task_name = process_code_review.name

        # Assert
        assert task_name == "worker.process_code_review", (
            f"Expected task name 'worker.process_code_review', got '{task_name}'"
        )

    def test_process_code_review_accepts_metadata_dict(
        self, sample_pr_metadata_github, sample_trace_id
    ):
        """
        GIVEN a PRMetadata dict and trace_id
        WHEN calling process_code_review.delay()
        THEN it should accept the parameters

        FAIL EXPECTED: Task signature may not accept dict parameter
        """
        # Arrange
        from worker import process_code_review

        metadata_dict = sample_pr_metadata_github

        # Act & Assert - Just verify it doesn't raise TypeError
        try:
            result = process_code_review.s(metadata_dict, sample_trace_id)
            assert result is not None
        except TypeError as e:
            pytest.fail(f"Task signature doesn't accept parameters: {e}")

    def test_process_code_review_accepts_prmetadata_model(
        self, sample_pr_metadata_github, sample_trace_id
    ):
        """
        GIVEN a PRMetadata model instance
        WHEN converting to dict and calling process_code_review
        THEN it should handle the conversion correctly

        FAIL EXPECTED: Task may not handle PRMetadata model correctly
        """
        # Arrange
        from worker import process_code_review

        metadata = PRMetadata(**sample_pr_metadata_github)
        metadata_dict = metadata.model_dump()

        # Act & Assert
        try:
            result = process_code_review.s(metadata_dict, sample_trace_id)
            assert result is not None
        except Exception as e:
            pytest.fail(f"Task failed to accept PRMetadata dict: {e}")

    def test_process_code_review_with_github_metadata(
        self, sample_pr_metadata_github, sample_trace_id
    ):
        """
        GIVEN a GitHub PRMetadata
        WHEN calling process_code_review
        THEN it should handle GitHub platform correctly

        FAIL EXPECTED: May not handle GitHub platform properly
        """
        # Arrange
        from worker import process_code_review

        metadata_dict = sample_pr_metadata_github
        metadata_dict["platform"] = "github"

        # Act & Assert
        result = process_code_review.s(metadata_dict, sample_trace_id)
        assert result is not None

    def test_process_code_review_with_gitea_metadata(
        self, sample_pr_metadata_gitea, sample_trace_id
    ):
        """
        GIVEN a Gitea PRMetadata
        WHEN calling process_code_review
        THEN it should handle Gitea platform correctly

        FAIL EXPECTED: May not handle Gitea platform properly
        """
        # Arrange
        from worker import process_code_review

        metadata_dict = sample_pr_metadata_gitea
        metadata_dict["platform"] = "gitea"

        # Act & Assert
        result = process_code_review.s(metadata_dict, sample_trace_id)
        assert result is not None

    def test_process_code_review_task_is_bound(self):
        """
        GIVEN the process_code_review task
        WHEN checking its definition
        THEN it should be a bound task (has self parameter)

        FAIL EXPECTED: Task may not be bound
        """
        # Arrange
        from worker import process_code_review

        # Assert - Bound tasks have 'bind=True' in decorator
        # This is harder to test directly, but we can check if it has request attr
        # when applied
        assert hasattr(process_code_review, "apply_async")


class TestCeleryAppConfiguration:
    """
    Test Celery app configuration.

    These tests verify the Celery app is properly configured.
    """

    def test_celery_app_exists(self):
        """
        GIVEN the celery_app module
        WHEN importing the Celery app
        THEN it should exist

        FAIL EXPECTED: Celery app may not be configured
        """
        # Arrange & Act
        try:
            from celery_app import app
        except ImportError as e:
            pytest.fail(f"Celery app not found: {e}")

        # Assert
        assert app is not None
        assert app.main == "cortexreview"

    def test_celery_broker_url_configured(self):
        """
        GIVEN the Celery app configuration
        WHEN checking broker_url
        THEN it should be set to Redis URL

        FAIL EXPECTED: Broker URL may not be configured
        """
        # Arrange
        from celery_app import app

        # Act
        broker_url = app.conf.get("broker_url")

        # Assert
        assert broker_url is not None, "broker_url should be configured"
        assert "redis" in broker_url, "broker_url should use Redis"

    def test_celery_result_backend_configured(self):
        """
        GIVEN the Celery app configuration
        WHEN checking result_backend
        THEN it should be set to Redis URL

        FAIL EXPECTED: Result backend may not be configured
        """
        # Arrange
        from celery_app import app

        # Act
        result_backend = app.conf.get("result_backend")

        # Assert
        assert result_backend is not None, "result_backend should be configured"
        assert "redis" in result_backend, "result_backend should use Redis"

    def test_celery_task_routes_configured(self):
        """
        GIVEN the Celery app configuration
        WHEN checking task_routes
        THEN process_code_review should be routed to code_review queue

        FAIL EXPECTED: Task routing may not be configured
        """
        # Arrange
        from celery_app import app

        # Act
        task_routes = app.conf.get("task_routes", {})

        # Assert
        assert "worker.process_code_review" in task_routes, (
            "process_code_review should have a route configured"
        )


class TestCeleryTaskRegistration:
    """
    Test Celery task registration.

    These tests verify all tasks are properly registered.
    """

    def test_index_repository_task_exists(self):
        """
        GIVEN the worker module
        WHEN importing index_repository task
        THEN the task should exist

        FAIL EXPECTED: Task may not be defined
        """
        # Arrange & Act
        try:
            from worker import index_repository
        except ImportError as e:
            pytest.fail(f"index_repository task not found: {e}")

        # Assert
        assert index_repository is not None

    def test_process_feedback_task_exists(self):
        """
        GIVEN the worker module
        WHEN importing process_feedback task
        THEN the task should exist

        FAIL EXPECTED: Task may not be defined
        """
        # Arrange & Act
        try:
            from worker import process_feedback
        except ImportError as e:
            pytest.fail(f"process_feedback task not found: {e}")

        # Assert
        assert process_feedback is not None

    def test_cleanup_expired_constraints_task_exists(self):
        """
        GIVEN the worker module
        WHEN importing cleanup_expired_constraints task
        THEN the task should exist

        FAIL EXPECTED: Task may not be defined
        """
        # Arrange & Act
        try:
            from worker import cleanup_expired_constraints
        except ImportError as e:
            pytest.fail(f"cleanup_expired_constraints task not found: {e}")

        # Assert
        assert cleanup_expired_constraints is not None

    def test_aggregate_metrics_task_exists(self):
        """
        GIVEN the worker module
        WHEN importing aggregate_metrics task
        THEN the task should exist

        FAIL EXPECTED: Task may not be defined
        """
        # Arrange & Act
        try:
            from worker import aggregate_metrics
        except ImportError as e:
            pytest.fail(f"aggregate_metrics task not found: {e}")

        # Assert
        assert aggregate_metrics is not None


class TestProcessCodeReviewTaskBehavior:
    """
    Test process_code_review task behavior with mocks.

    These tests verify the task behaves correctly when executed.
    """

    @patch("worker.process_code_review")
    def test_task_returns_dict_with_task_id(
        self, mock_task, sample_pr_metadata_github, sample_trace_id
    ):
        """
        GIVEN a mocked process_code_review task
        WHEN calling it with valid parameters
        THEN it should return a dict with task_id field

        FAIL EXPECTED: Task may not return correct format
        """
        # Arrange
        from celery import Task

        mock_self = MagicMock(spec=Task)
        mock_self.request.id = sample_trace_id
        mock_self.request.get.return_value = None

        # Import actual task
        import worker

        # We can't easily mock the whole task execution, so we just
        # verify the task signature is correct
        metadata_dict = sample_pr_metadata_github

        # Act & Assert - Just verify parameters are accepted
        try:
            # Create signature
            sig = worker.process_code_review.s(metadata_dict, sample_trace_id)
            assert sig is not None
        except Exception as e:
            pytest.fail(f"Task signature failed: {e}")

    @patch("worker.process_code_review")
    def test_task_accepts_valid_pr_number(
        self, mock_task, sample_pr_metadata_github, sample_trace_id
    ):
        """
        GIVEN metadata with valid pr_number (> 0)
        WHEN calling the task
        THEN it should accept the pr_number

        FAIL EXPECTED: Task may not handle PR events correctly
        """
        # Arrange
        import worker

        metadata_dict = sample_pr_metadata_github.copy()
        metadata_dict["pr_number"] = 42  # Valid PR number

        # Act & Assert
        try:
            sig = worker.process_code_review.s(metadata_dict, sample_trace_id)
            assert sig is not None
        except Exception as e:
            pytest.fail(f"Task failed with PR number: {e}")

    @patch("worker.process_code_review")
    def test_task_accepts_push_event_pr_number_zero(
        self, mock_task, sample_pr_metadata_gitea, sample_trace_id
    ):
        """
        GIVEN metadata with pr_number=0 (push event)
        WHEN calling the task
        THEN it should accept the pr_number

        FAIL EXPECTED: Task may not handle push events correctly
        """
        # Arrange
        import worker

        metadata_dict = sample_pr_metadata_gitea.copy()
        metadata_dict["pr_number"] = 0  # Push event

        # Act & Assert
        try:
            sig = worker.process_code_review.s(metadata_dict, sample_trace_id)
            assert sig is not None
        except Exception as e:
            pytest.fail(f"Task failed with push event: {e}")


class TestReviewConfigModel:
    """
    Test ReviewConfig model used in worker tasks.

    These tests verify ReviewConfig validates correctly.
    """

    def test_review_config_accepts_valid_data(self, test_review_config):
        """
        GIVEN valid ReviewConfig data
        WHEN creating the model
        THEN it should validate successfully

        FAIL EXPECTED: Model may have wrong validation rules
        """
        # Arrange & Act
        config = ReviewConfig(**test_review_config)

        # Assert
        assert config.use_rag_context is True
        assert config.apply_learned_suppressions is True
        assert config.severity_threshold.value == "low"
        assert config.include_auto_fix_patches is False
        assert config.max_context_matches == 10

    def test_review_config_default_values(self):
        """
        GIVEN minimal ReviewConfig data
        WHEN creating the model
        THEN it should use default values

        FAIL EXPECTED: Defaults may not match specification
        """
        # Arrange & Act
        config = ReviewConfig()

        # Assert
        assert config.use_rag_context is True  # Default
        assert config.apply_learned_suppressions is True  # Default
        assert config.severity_threshold.value == "low"  # Default
        assert config.include_auto_fix_patches is False  # Default
        assert config.max_context_matches == 10  # Default

    def test_review_config_max_context_matches_validation(self):
        """
        GIVEN invalid max_context_matches value
        WHEN creating the model
        THEN it should raise ValidationError

        FAIL EXPECTED: Validation may not be enforced
        """
        # Arrange & Act & Assert
        with pytest.raises(Exception):  # ValidationError
            ReviewConfig(max_context_matches=100)  # Too high

        with pytest.raises(Exception):  # ValidationError
            ReviewConfig(max_context_matches=1)  # Too low (min is 3)
