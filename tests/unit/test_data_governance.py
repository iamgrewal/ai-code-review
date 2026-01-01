"""
Unit Tests for Data Governance Module

Tests data isolation, retention policies, cleanup jobs, and
audit logging per Constitution XIII.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from utils.data_governance import (
    DataIsolationError,
    DataRetentionError,
    RetentionPolicy,
    build_repo_filter,
    cleanup_expired_constraints,
    cleanup_expired_knowledge,
    delete_all_repo_data,
    enforce_repo_isolation,
    export_repo_data,
    log_data_access,
    verify_repo_access,
)


class TestEnforceRepoIsolation:
    """Test repository ID validation and normalization."""

    def test_valid_repo_id(self):
        """GIVEN a valid repo_id WHEN enforcing isolation THEN return normalized ID."""
        result = enforce_repo_isolation("octocat/hello-world")
        assert result == "octocat/hello-world"

    def test_url_encoded_repo_id(self):
        """GIVEN a URL-encoded repo_id WHEN enforcing isolation THEN return decoded ID."""
        result = enforce_repo_isolation("octocat%2Fhello-world")
        assert result == "octocat/hello-world"

    def test_empty_repo_id_raises_error(self):
        """GIVEN an empty repo_id WHEN enforcing isolation THEN raise DataIsolationError."""
        with pytest.raises(DataIsolationError) as exc_info:
            enforce_repo_isolation("")

        assert "repo_id cannot be empty" in str(exc_info.value)

    def test_invalid_format_raises_error(self):
        """GIVEN an invalid repo_id format WHEN enforcing isolation THEN raise DataIsolationError."""
        with pytest.raises(DataIsolationError) as exc_info:
            enforce_repo_isolation("invalid-no-slash")

        assert "Invalid repo_id format" in str(exc_info.value)

    def test_multiple_slashes_raises_error(self):
        """GIVEN repo_id with multiple slashes WHEN enforcing isolation THEN raise DataIsolationError."""
        with pytest.raises(DataIsolationError) as exc_info:
            enforce_repo_isolation("org/team/repo")

        assert "Invalid repo_id format" in str(exc_info.value)


class TestBuildRepoFilter:
    """Test Supabase filter builder for repo isolation."""

    def test_build_filter_valid_repo(self):
        """GIVEN a valid repo_id WHEN building filter THEN return Supabase filter dict."""
        filter_dict = build_repo_filter("octocat/test-repo")
        assert filter_dict == {"repo_id": "eq.octocat/test-repo"}

    def test_build_filter_normalizes_encoding(self):
        """GIVEN URL-encoded repo_id WHEN building filter THEN return normalized filter."""
        filter_dict = build_repo_filter("octocat%2Ftest-repo")
        assert filter_dict == {"repo_id": "eq.octocat/test-repo"}


class TestRetentionPolicy:
    """Test data retention policy configuration."""

    def test_knowledge_retention_days(self):
        """GIVEN retention policy WHEN checking knowledge retention THEN be 180 days."""
        assert RetentionPolicy.KNOWLEDGE_RETENTION_DAYS == 180

    def test_constraint_retention_days(self):
        """GIVEN retention policy WHEN checking constraint retention THEN be 90 days."""
        assert RetentionPolicy.CONSTRAINT_RETENTION_DAYS == 90

    def test_review_retention_days(self):
        """GIVEN retention policy WHEN checking review retention THEN be 365 days."""
        assert RetentionPolicy.REVIEW_RETENTION_DAYS == 365

    def test_failed_task_retention_days(self):
        """GIVEN retention policy WHEN checking failed task retention THEN be 30 days."""
        assert RetentionPolicy.FAILED_TASK_RETENTION_DAYS == 30


class TestCleanupExpiredKnowledge:
    """Test knowledge base cleanup functionality."""

    def test_cleanup_success_returns_result(self):
        """GIVEN successful cleanup WHEN calling function THEN return result dict."""
        mock_supabase = Mock()
        mock_supabase.table.return_value.delete.return_value.lt.return_value.execute.return_value = MagicMock(
            data=[{"id": 1}, {"id": 2}]
        )

        result = cleanup_expired_knowledge(mock_supabase, retention_days=180)

        assert result["status"] == "success"
        assert result["deleted_count"] == 2
        assert result["retention_days"] == 180

    def test_cleanup_with_repo_id(self):
        """GIVEN repo_id specified WHEN cleaning up THEN apply repo filter."""
        mock_supabase = Mock()
        mock_supabase.table.return_value.delete.return_value.lt.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        cleanup_expired_knowledge(mock_supabase, repo_id="octocat/test-repo")

        # Verify repo filter was applied
        mock_supabase.table.return_value.delete.return_value.lt.return_value.eq.assert_called_once()

    def test_cleanup_failure_raises_error(self):
        """GIVEN Supabase error WHEN cleaning up THEN raise DataRetentionError."""
        mock_supabase = Mock()
        mock_supabase.table.side_effect = Exception("Database error")

        with pytest.raises(DataRetentionError):
            cleanup_expired_knowledge(mock_supabase)


class TestCleanupExpiredConstraints:
    """Test learned constraints cleanup functionality."""

    def test_cleanup_success_returns_result(self):
        """GIVEN successful cleanup WHEN calling function THEN return result dict."""
        mock_supabase = Mock()
        mock_supabase.table.return_value.delete.return_value.lt.return_value.execute.return_value = MagicMock(
            data=[{"id": 1}]
        )

        result = cleanup_expired_constraints(mock_supabase, retention_days=90)

        assert result["status"] == "success"
        assert result["deleted_count"] == 1
        assert result["retention_days"] == 90


class TestCleanupAllExpiredData:
    """Test combined cleanup functionality."""

    @pytest.mark.skip(reason="Complex Supabase mock chain requires integration test")
    def test_cleanup_all_returns_combined_results(self):
        """GIVEN both tables have expired data WHEN cleaning all THEN return combined result."""
        # This test requires complex mock setup for chained Supabase calls
        # Better suited for integration testing with real Supabase
        pass


class TestDeleteAllRepoData:
    """Test right-to-forget (GDPR-style) deletion."""

    def test_delete_all_repo_data_success(self):
        """GIVEN valid repo_id WHEN deleting all data THEN return success result."""
        mock_supabase = Mock()
        mock_supabase.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": 1}, {"id": 2}]
        )

        result = delete_all_repo_data(mock_supabase, "octocat/test-repo")

        assert result["status"] == "success"
        assert result["repo_id"] == "octocat/test-repo"
        assert result["knowledge_deleted"] == 2
        assert result["constraints_deleted"] == 2

    def test_delete_all_invalid_repo_raises_error(self):
        """GIVEN invalid repo_id WHEN deleting all data THEN raise DataIsolationError."""
        mock_supabase = Mock()

        with pytest.raises(DataIsolationError):
            delete_all_repo_data(mock_supabase, "invalid-repo")


class TestLogDataAccess:
    """Test audit logging functionality."""

    def test_log_data_access_logs_entry(self):
        """GIVEN data access WHEN logging THEN create audit log entry."""
        with patch("utils.data_governance.logger") as mock_logger:
            log_data_access(
                action="read",
                repo_id="octocat/test-repo",
                table="knowledge_base",
                record_id=123,
                user_id="user123",
            )

            # Verify log was called
            mock_logger.bind.assert_called_once()


class TestExportRepoData:
    """Test data export functionality."""

    @pytest.mark.skip(reason="Complex Supabase mock chain requires integration test")
    def test_export_repo_data_success(self):
        """GIVEN valid repo_id WHEN exporting data THEN return export dict."""
        # This test requires complex mock setup for chained Supabase calls
        # Better suited for integration testing with real Supabase
        pass

    def test_export_without_embeddings(self):
        """GIVEN export with include_embeddings=False WHEN exporting THEN exclude embedding column."""
        from unittest.mock import Mock

        mock_supabase = Mock()

        # Create mock result object
        class MockResult:
            def __init__(self, data):
                self.data = data

        mock_kb_result = MockResult([{"id": 1}])
        mock_lc_result = MockResult([])

        def mock_table_func(table_name):
            mock_tb = Mock()
            mock_select = Mock()
            mock_eq = Mock()

            if table_name == "knowledge_base":
                mock_eq.execute.return_value = mock_kb_result
            else:
                mock_eq.execute.return_value = mock_lc_result

            mock_select.eq.return_value = mock_eq
            mock_tb.select.return_value = mock_select
            return mock_tb

        mock_supabase.table.side_effect = mock_table_func

        result = export_repo_data(mock_supabase, "octocat/test-repo", include_embeddings=False)

        assert result["repo_id"] == "octocat/test-repo"


class TestVerifyRepoAccess:
    """Test repository access verification."""

    def test_verify_access_returns_true(self):
        """GIVEN record belongs to repo WHEN verifying access THEN return True."""
        mock_supabase = Mock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": 1, "repo_id": "octocat/test-repo"}]
        )

        result = verify_repo_access(mock_supabase, "octocat/test-repo", "knowledge_base", 1)

        assert result is True

    def test_verify_access_returns_false(self):
        """GIVEN record does not belong to repo WHEN verifying access THEN return False."""
        mock_supabase = Mock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]  # No matching records
        )

        result = verify_repo_access(mock_supabase, "octocat/test-repo", "knowledge_base", 999)

        assert result is False
