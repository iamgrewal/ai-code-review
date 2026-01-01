"""
Unit Tests: FeedbackRepository

T062 - Test FeedbackRepository audit log creation

Tests for the RLHF feedback audit log repository that handles
feedback record storage for compliance and debugging.

Status: RED (implementation does not exist yet)
Task: 001-cortexreview-platform/T062
"""

import os

# Add project root to path for imports
import sys
from datetime import datetime
from enum import Enum
from typing import Any
from unittest.mock import MagicMock, Mock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


# =============================================================================
# Enum Definitions
# =============================================================================


class FeedbackAction(str, Enum):
    """Feedback action types matching the data model."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MODIFIED = "modified"


# =============================================================================
# Test Data Fixtures
# =============================================================================


@pytest.fixture
def sample_feedback_request() -> dict[str, Any]:
    """Sample FeedbackRequest data."""
    return {
        "comment_id": "comment-uuid-12345",
        "action": FeedbackAction.REJECTED,
        "reason": "false_positive",
        "developer_comment": "This pattern is safe because the variable is sanitized earlier in the function.",
        "final_code_snapshot": "username = sanitize(input)\nexecute(f'SELECT * FROM users WHERE name={username}')",
    }


@pytest.fixture
def sample_feedback_record() -> dict[str, Any]:
    """Sample FeedbackRecord for testing."""
    return {
        "id": 1,
        "review_id": "review-uuid-67890",
        "comment_id": "comment-uuid-12345",
        "user_id": "octocat",
        "action": FeedbackAction.REJECTED,
        "reason": "false_positive",
        "final_code_snapshot": "username = sanitize(input)\nexecute(f'SELECT * FROM users WHERE name={username}')",
        "trace_id": "trace-uuid-abcde",
        "created_at": datetime(2025, 12, 31, 10, 0, 0),
    }


@pytest.fixture
def mock_supabase_client() -> Mock:
    """Mock Supabase client for testing."""
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value.data = []
    client.table.return_value.select.return_value.execute.return_value.data = []
    return client


@pytest.fixture
def feedback_repo_config() -> dict[str, Any]:
    """Configuration for FeedbackRepository initialization."""
    return {
        "supabase_url": "https://test.supabase.co",
        "supabase_key": "test_service_key",
        "retention_days": 365,
    }


@pytest.fixture
def sample_trace_id() -> str:
    """Sample trace ID for distributed tracing."""
    return "trace-uuid-abcde-12345"


# =============================================================================
# FeedbackRepository.record_feedback() Tests
# =============================================================================


class TestFeedbackRepositoryRecordFeedback:
    """Test suite for FeedbackRepository.record_feedback() method."""

    def test_record_feedback_inserts_into_audit_log(
        self,
        mock_supabase_client,
        sample_feedback_request,
        sample_feedback_record,
        feedback_repo_config,
        sample_trace_id,
    ):
        """
        Test: record_feedback() inserts FeedbackRecord into Supabase audit log.

        Expected:
        - Supabase client.table('feedback_audit_log').insert() is called
        - All required fields are included in insert
        - Returns created record with generated id
        """
        # Arrange
        from models.feedback import FeedbackRequest
        from repositories.feedback import FeedbackRepository

        mock_supabase_client.table.return_value.insert.return_value.execute.return_value.data = [
            sample_feedback_record
        ]

        repo = FeedbackRepository(
            supabase_client=mock_supabase_client,
            config=feedback_repo_config,
        )

        request = FeedbackRequest(**sample_feedback_request)

        # Act
        result = repo.record_feedback(
            request=request,
            review_id="review-uuid-67890",
            user_id="octocat",
            trace_id=sample_trace_id,
        )

        # Assert
        mock_supabase_client.table.assert_called_once_with("feedback_audit_log")
        mock_supabase_client.table.return_value.insert.assert_called_once()

    def test_record_feedback_includes_all_required_fields(
        self,
        mock_supabase_client,
        sample_feedback_request,
        feedback_repo_config,
        sample_trace_id,
    ):
        """
        Test: record_feedback() includes all required fields in insert.

        Expected:
        - review_id is included
        - comment_id is included
        - user_id is included
        - action enum is stored as string
        - reason is included
        - final_code_snapshot is included
        - trace_id is included
        - created_at is set to current timestamp
        """
        # Arrange
        from models.feedback import FeedbackRequest
        from repositories.feedback import FeedbackRepository

        repo = FeedbackRepository(
            supabase_client=mock_supabase_client,
            config=feedback_repo_config,
        )

        request = FeedbackRequest(**sample_feedback_request)

        # Act
        repo.record_feedback(
            request=request,
            review_id="review-uuid-67890",
            user_id="octocat",
            trace_id=sample_trace_id,
        )

        # Assert
        call_args = mock_supabase_client.table.return_value.insert.call_args
        inserted_data = call_args[0][0]

        assert "review_id" in inserted_data
        assert "comment_id" in inserted_data
        assert "user_id" in inserted_data
        assert "action" in inserted_data
        assert "reason" in inserted_data
        assert "final_code_snapshot" in inserted_data
        assert "trace_id" in inserted_data
        assert "created_at" in inserted_data

    def test_record_feedback_sets_created_at_timestamp(
        self,
        mock_supabase_client,
        sample_feedback_request,
        feedback_repo_config,
        sample_trace_id,
    ):
        """
        Test: record_feedback() sets created_at to current timestamp.

        Expected:
        - created_at is set to datetime close to now
        - Timestamp is in UTC
        """
        # Arrange
        from models.feedback import FeedbackRequest
        from repositories.feedback import FeedbackRepository

        repo = FeedbackRepository(
            supabase_client=mock_supabase_client,
            config=feedback_repo_config,
        )

        request = FeedbackRequest(**sample_feedback_request)

        before = datetime.now()

        # Act
        repo.record_feedback(
            request=request,
            review_id="review-uuid-67890",
            user_id="octocat",
            trace_id=sample_trace_id,
        )

        after = datetime.now()

        # Assert
        call_args = mock_supabase_client.table.return_value.insert.call_args
        inserted_data = call_args[0][0]
        created_at = inserted_data["created_at"]

        assert before <= created_at <= after

    def test_record_feedback_converts_action_enum_to_string(
        self,
        mock_supabase_client,
        sample_feedback_request,
        feedback_repo_config,
        sample_trace_id,
    ):
        """
        Test: record_feedback() converts FeedbackAction enum to string.

        Expected:
        - action is stored as string value ('accepted', 'rejected', 'modified')
        - Not stored as enum object
        """
        # Arrange
        from models.feedback import FeedbackAction, FeedbackRequest
        from repositories.feedback import FeedbackRepository

        repo = FeedbackRepository(
            supabase_client=mock_supabase_client,
            config=feedback_repo_config,
        )

        request = FeedbackRequest(
            comment_id="comment-123",
            action=FeedbackAction.REJECTED,
            reason="false_positive",
            developer_comment="Test",
            final_code_snapshot="code",
        )

        # Act
        repo.record_feedback(
            request=request,
            review_id="review-123",
            user_id="user123",
            trace_id=sample_trace_id,
        )

        # Assert
        call_args = mock_supabase_client.table.return_value.insert.call_args
        inserted_data = call_args[0][0]

        assert isinstance(inserted_data["action"], str)
        assert inserted_data["action"] == "rejected"

    def test_record_feedback_returns_feedback_record_model(
        self,
        mock_supabase_client,
        sample_feedback_request,
        sample_feedback_record,
        feedback_repo_config,
        sample_trace_id,
    ):
        """
        Test: record_feedback() returns FeedbackRecord model instance.

        Expected:
        - Returns FeedbackRecord Pydantic model
        - Model includes database-generated id
        """
        # Arrange
        from models.feedback import FeedbackRecord, FeedbackRequest
        from repositories.feedback import FeedbackRepository

        mock_supabase_client.table.return_value.insert.return_value.execute.return_value.data = [
            sample_feedback_record
        ]

        repo = FeedbackRepository(
            supabase_client=mock_supabase_client,
            config=feedback_repo_config,
        )

        request = FeedbackRequest(**sample_feedback_request)

        # Act
        result = repo.record_feedback(
            request=request,
            review_id="review-uuid-67890",
            user_id="octocat",
            trace_id=sample_trace_id,
        )

        # Assert
        assert isinstance(result, FeedbackRecord)
        assert result.id == sample_feedback_record["id"]


# =============================================================================
# FeedbackRepository.get_feedback_by_comment() Tests
# =============================================================================


class TestFeedbackRepositoryGetFeedbackByComment:
    """Test suite for FeedbackRepository.get_feedback_by_comment() method."""

    def test_get_feedback_by_comment_filters_by_comment_id(
        self,
        mock_supabase_client,
        sample_feedback_record,
        feedback_repo_config,
    ):
        """
        Test: get_feedback_by_comment() queries by comment_id.

        Expected:
        - Supabase query filters by comment_id
        - Returns list of feedback for that comment
        """
        # Arrange
        from repositories.feedback import FeedbackRepository

        mock_supabase_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            sample_feedback_record
        ]

        repo = FeedbackRepository(
            supabase_client=mock_supabase_client,
            config=feedback_repo_config,
        )

        # Act
        result = repo.get_feedback_by_comment(comment_id="comment-uuid-12345")

        # Assert
        mock_supabase_client.table.return_value.select.assert_called_once()
        # Filter should be applied to comment_id field

    def test_get_feedback_by_comment_returns_feedback_records(
        self,
        mock_supabase_client,
        sample_feedback_record,
        feedback_repo_config,
    ):
        """
        Test: get_feedback_by_comment() returns list of FeedbackRecord.

        Expected:
        - Returns list of FeedbackRecord instances
        - Empty list if no feedback found
        """
        # Arrange
        from repositories.feedback import FeedbackRepository

        mock_supabase_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            sample_feedback_record
        ]

        repo = FeedbackRepository(
            supabase_client=mock_supabase_client,
            config=feedback_repo_config,
        )

        # Act
        result = repo.get_feedback_by_comment(comment_id="comment-uuid-12345")

        # Assert
        assert isinstance(result, list)
        assert len(result) == 1

    def test_get_feedback_by_comment_orders_by_created_at_desc(
        self,
        mock_supabase_client,
        feedback_repo_config,
    ):
        """
        Test: get_feedback_by_comment() orders results by created_at descending.

        Expected:
        - Most recent feedback is first
        """
        # Arrange
        from repositories.feedback import FeedbackRepository

        mock_supabase_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = []

        repo = FeedbackRepository(
            supabase_client=mock_supabase_client,
            config=feedback_repo_config,
        )

        # Act
        repo.get_feedback_by_comment(comment_id="comment-123")

        # Assert
        # Order should be applied to created_at field descending
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.order.assert_called()


# =============================================================================
# FeedbackRepository.get_feedback_by_user() Tests
# =============================================================================


class TestFeedbackRepositoryGetFeedbackByUser:
    """Test suite for FeedbackRepository.get_feedback_by_user() method."""

    def test_get_feedback_by_user_filters_by_user_id(
        self,
        mock_supabase_client,
        sample_feedback_record,
        feedback_repo_config,
    ):
        """
        Test: get_feedback_by_user() queries by user_id.

        Expected:
        - Supabase query filters by user_id
        - Returns list of feedback from that user
        """
        # Arrange
        from repositories.feedback import FeedbackRepository

        mock_supabase_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            sample_feedback_record
        ]

        repo = FeedbackRepository(
            supabase_client=mock_supabase_client,
            config=feedback_repo_config,
        )

        # Act
        result = repo.get_feedback_by_user(user_id="octocat")

        # Assert
        assert isinstance(result, list)

    def test_get_feedback_by_user_supports_date_range_filter(
        self,
        mock_supabase_client,
        feedback_repo_config,
    ):
        """
        Test: get_feedback_by_user() supports optional date range filtering.

        Expected:
        - When start_date and end_date provided, filters by date range
        - Useful for compliance audits
        """
        # Arrange
        from datetime import datetime, timedelta

        from repositories.feedback import FeedbackRepository

        repo = FeedbackRepository(
            supabase_client=mock_supabase_client,
            config=feedback_repo_config,
        )

        start_date = datetime.now() - timedelta(days=30)
        end_date = datetime.now()

        # Act
        repo.get_feedback_by_user(
            user_id="octocat",
            start_date=start_date,
            end_date=end_date,
        )

        # Assert
        # Should apply gte/lte filters on created_at


# =============================================================================
# Append-Only Behavior Tests
# =============================================================================


class TestFeedbackRepositoryAppendOnly:
    """Test suite for append-only audit log behavior."""

    def test_no_update_method_exists(
        self,
        mock_supabase_client,
        feedback_repo_config,
    ):
        """
        Test: FeedbackRepository has NO update method (append-only enforcement).

        Expected:
        - No update_feedback() method exists
        - No modify_feedback() method exists
        - Ensures audit trail integrity
        """
        # Arrange
        from repositories.feedback import FeedbackRepository

        repo = FeedbackRepository(
            supabase_client=mock_supabase_client,
            config=feedback_repo_config,
        )

        # Act & Assert
        assert not hasattr(repo, "update_feedback")
        assert not hasattr(repo, "modify_feedback")
        assert not hasattr(repo, "delete_feedback")

    def test_no_delete_method_exists(
        self,
        mock_supabase_client,
        feedback_repo_config,
    ):
        """
        Test: FeedbackRepository has NO delete method (append-only enforcement).

        Expected:
        - No delete_feedback() method exists
        - Ensures audit trail cannot be tampered with
        """
        # Arrange
        from repositories.feedback import FeedbackRepository

        repo = FeedbackRepository(
            supabase_client=mock_supabase_client,
            config=feedback_repo_config,
        )

        # Act & Assert
        assert not hasattr(repo, "delete_feedback")
        assert not hasattr(repo, "remove_feedback")

    def test_record_feedback_creates_new_record_only(
        self,
        mock_supabase_client,
        sample_feedback_request,
        feedback_repo_config,
        sample_trace_id,
    ):
        """
        Test: record_feedback() only creates new records, never updates.

        Expected:
        - Always calls insert(), never update()
        - Multiple feedback for same comment creates multiple records
        """
        # Arrange
        from models.feedback import FeedbackRequest
        from repositories.feedback import FeedbackRepository

        repo = FeedbackRepository(
            supabase_client=mock_supabase_client,
            config=feedback_repo_config,
        )

        request = FeedbackRequest(**sample_feedback_request)

        # Act - Submit same feedback twice
        repo.record_feedback(
            request=request,
            review_id="review-123",
            user_id="user1",
            trace_id=sample_trace_id,
        )

        repo.record_feedback(
            request=request,
            review_id="review-123",
            user_id="user1",
            trace_id=sample_trace_id,
        )

        # Assert
        # Should call insert() twice
        assert mock_supabase_client.table.return_value.insert.call_count == 2
        # Should never call update()
        assert mock_supabase_client.table.return_value.update.call_count == 0


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestFeedbackRepositoryErrorHandling:
    """Test suite for error handling and graceful degradation."""

    def test_handles_supabase_connection_error(
        self,
        mock_supabase_client,
        sample_feedback_request,
        feedback_repo_config,
        sample_trace_id,
        caplog,
    ):
        """
        Test: Handles Supabase connection error gracefully.

        Expected:
        - Logs error with context
        - Raises exception or returns error response
        - Does not crash application
        """
        # Arrange
        from models.feedback import FeedbackRequest
        from repositories.feedback import FeedbackRepository

        mock_supabase_client.table.return_value.insert.side_effect = Exception(
            "Supabase connection failed"
        )

        repo = FeedbackRepository(
            supabase_client=mock_supabase_client,
            config=feedback_repo_config,
        )

        request = FeedbackRequest(**sample_feedback_request)

        # Act & Assert
        with pytest.raises(Exception):
            repo.record_feedback(
                request=request,
                review_id="review-123",
                user_id="user1",
                trace_id=sample_trace_id,
            )

    def test_validates_feedback_request_before_insert(
        self,
        mock_supabase_client,
        feedback_repo_config,
        sample_trace_id,
    ):
        """
        Test: Validates FeedbackRequest before database insert.

        Expected:
        - Raises ValidationError for invalid action
        - Raises ValidationError for invalid reason
        - Validates developer_comment length (1-1000 chars)
        """
        # Arrange
        from pydantic import ValidationError

        from models.feedback import FeedbackRequest
        from repositories.feedback import FeedbackRepository

        repo = FeedbackRepository(
            supabase_client=mock_supabase_client,
            config=feedback_repo_config,
        )

        # Invalid action
        with pytest.raises(ValidationError):
            FeedbackRequest(
                comment_id="comment-123",
                action="invalid_action",  # Invalid
                reason="false_positive",
                developer_comment="Test",
                final_code_snapshot="code",
            )

    def test_handles_large_code_snapshots(
        self,
        mock_supabase_client,
        feedback_repo_config,
        sample_trace_id,
    ):
        """
        Test: Handles large final_code_snapshot strings.

        Expected:
        - Stores large code snapshots without truncation
        - No errors for code up to reasonable size (e.g., 100KB)
        """
        # Arrange
        from models.feedback import FeedbackRequest
        from repositories.feedback import FeedbackRepository

        repo = FeedbackRepository(
            supabase_client=mock_supabase_client,
            config=feedback_repo_config,
        )

        large_code = "def function():\n    return True\n" * 1000  # ~60KB

        request = FeedbackRequest(
            comment_id="comment-123",
            action="accepted",
            reason="logic_error",
            developer_comment="Large code snapshot test",
            final_code_snapshot=large_code,
        )

        # Act
        # Should not raise error
        repo.record_feedback(
            request=request,
            review_id="review-123",
            user_id="user1",
            trace_id=sample_trace_id,
        )

        # Assert
        call_args = mock_supabase_client.table.return_value.insert.call_args
        inserted_data = call_args[0][0]
        assert len(inserted_data["final_code_snapshot"]) == len(large_code)


# =============================================================================
# Compliance and Auditing Tests
# =============================================================================


class TestFeedbackRepositoryCompliance:
    """Test suite for compliance and auditing features."""

    def test_includes_trace_id_for_correlation(
        self,
        mock_supabase_client,
        sample_feedback_request,
        feedback_repo_config,
        sample_trace_id,
    ):
        """
        Test: Includes trace_id for distributed tracing correlation.

        Expected:
        - trace_id is stored in audit log
        - Enables correlation across services
        """
        # Arrange
        from models.feedback import FeedbackRequest
        from repositories.feedback import FeedbackRepository

        repo = FeedbackRepository(
            supabase_client=mock_supabase_client,
            config=feedback_repo_config,
        )

        request = FeedbackRequest(**sample_feedback_request)

        # Act
        repo.record_feedback(
            request=request,
            review_id="review-123",
            user_id="user1",
            trace_id=sample_trace_id,
        )

        # Assert
        call_args = mock_supabase_client.table.return_value.insert.call_args
        inserted_data = call_args[0][0]
        assert inserted_data["trace_id"] == sample_trace_id

    def test_logs_feedback_submission_for_audit(
        self,
        mock_supabase_client,
        sample_feedback_request,
        feedback_repo_config,
        sample_trace_id,
        caplog,
    ):
        """
        Test: Logs feedback submission for audit trail.

        Expected:
        - Logs include user_id, action, comment_id
        - Enables compliance monitoring
        """
        # Arrange
        from models.feedback import FeedbackRequest
        from repositories.feedback import FeedbackRepository

        repo = FeedbackRepository(
            supabase_client=mock_supabase_client,
            config=feedback_repo_config,
        )

        request = FeedbackRequest(**sample_feedback_request)

        # Act
        repo.record_feedback(
            request=request,
            review_id="review-123",
            user_id="octocat",
            trace_id=sample_trace_id,
        )

        # Assert
        assert any("feedback" in record.message.lower() for record in caplog.records)
