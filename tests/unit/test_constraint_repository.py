"""
Unit Tests: ConstraintRepository

T061 - Test ConstraintRepository.check_suppressions() method

Tests for the RLHF constraint repository that handles learned constraint
storage and retrieval for false positive suppression.

Status: RED (implementation does not exist yet)
Task: 001-cortexreview-platform/T061
"""

import os

# Add project root to path for imports
import sys
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, Mock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


# =============================================================================
# Test Data Fixtures
# =============================================================================


@pytest.fixture
def sample_query_embedding() -> list[float]:
    """Sample 1536-dimensional embedding vector from OpenAI."""
    return [0.1, -0.2, 0.3, -0.4] * 384  # 1536 dimensions


@pytest.fixture
def mock_supabase_constraint_response() -> list[dict[str, Any]]:
    """Mock Supabase RPC response for check_constraints function."""
    return [
        {
            "id": 1,
            "code_pattern": "execute(f'SELECT * FROM users WHERE name={name}')",
            "user_reason": "This is safe because username is sanitized earlier in the function",
            "similarity": 0.92,
            "confidence_score": 0.7,
            "repo_id": "octocat/test-repo",
            "expires_at": datetime(2026, 3, 31, 10, 0, 0),
        },
        {
            "id": 2,
            "code_pattern": "return {'user': user}  # Internal API",
            "user_reason": "Internal API not exposed to external clients",
            "similarity": 0.85,
            "confidence_score": 0.5,
            "repo_id": "octocat/test-repo",
            "expires_at": datetime(2026, 3, 31, 10, 0, 0),
        },
    ]


@pytest.fixture
def mock_supabase_client() -> Mock:
    """Mock Supabase client for testing."""
    client = MagicMock()
    client.rpc.return_value.execute.return_value.data = []
    return client


@pytest.fixture
def sample_constraint_record() -> dict[str, Any]:
    """Sample LearnedConstraint record."""
    return {
        "id": 1,
        "repo_id": "octocat/test-repo",
        "violation_reason": "sql_injection",
        "code_pattern": "execute(f'SELECT * FROM users WHERE name={name}')",
        "user_reason": "This is safe because username is sanitized earlier",
        "embedding": [0.1, -0.2, 0.3] * 512,  # 1536 dimensions
        "confidence_score": 0.7,
        "expires_at": datetime(2026, 3, 31, 10, 0, 0),
        "created_at": datetime(2025, 12, 31, 10, 0, 0),
        "version": 1,
    }


@pytest.fixture
def constraint_repo_config() -> dict[str, Any]:
    """Configuration for ConstraintRepository initialization."""
    return {
        "supabase_url": "https://test.supabase.co",
        "supabase_key": "test_service_key",
        "match_threshold": 0.8,
        "max_constraints": 10,
    }


# =============================================================================
# ConstraintRepository.check_suppressions() Tests
# =============================================================================


class TestConstraintRepositoryCheckSuppressions:
    """Test suite for ConstraintRepository.check_suppressions() method."""

    def test_check_suppressions_calls_supabase_rpc(
        self,
        mock_supabase_client,
        sample_query_embedding,
        mock_supabase_constraint_response,
        constraint_repo_config,
    ):
        """
        Test: check_suppressions() calls Supabase check_constraints RPC function.

        Expected:
        - Supabase client.rpc() is called with 'check_constraints' function name
        - Query embedding is passed as parameter
        - Match threshold from config is passed
        """
        # Arrange
        from repositories.constraints import ConstraintRepository

        mock_supabase_client.rpc.return_value.execute.return_value.data = (
            mock_supabase_constraint_response
        )

        repo = ConstraintRepository(
            supabase_client=mock_supabase_client,
            config=constraint_repo_config,
        )

        # Act
        result = repo.check_suppressions(
            query_embedding=sample_query_embedding,
            repo_id="octocat/test-repo",
        )

        # Assert
        mock_supabase_client.rpc.assert_called_once_with(
            "check_constraints",
            {
                "query_embedding": sample_query_embedding,
                "match_threshold": constraint_repo_config["match_threshold"],
            },
        )

    def test_check_suppressions_returns_constraint_list(
        self,
        mock_supabase_client,
        sample_query_embedding,
        mock_supabase_constraint_response,
        constraint_repo_config,
    ):
        """
        Test: check_suppressions() returns list of LearnedConstraint objects.

        Expected:
        - Returns list of LearnedConstraint instances
        - Each constraint has id, code_pattern, user_reason, similarity, confidence_score
        """
        # Arrange
        from models.feedback import LearnedConstraint
        from repositories.constraints import ConstraintRepository

        mock_supabase_client.rpc.return_value.execute.return_value.data = (
            mock_supabase_constraint_response
        )

        repo = ConstraintRepository(
            supabase_client=mock_supabase_client,
            config=constraint_repo_config,
        )

        # Act
        result = repo.check_suppressions(
            query_embedding=sample_query_embedding,
            repo_id="octocat/test-repo",
        )

        # Assert
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(c, LearnedConstraint) for c in result)

    def test_check_suppressions_filters_by_confidence_threshold(
        self,
        mock_supabase_client,
        sample_query_embedding,
        constraint_repo_config,
    ):
        """
        Test: check_suppressions() filters results by minimum confidence threshold.

        Expected:
        - Only constraints with confidence_score >= 0.5 are returned
        - Low confidence constraints are filtered out
        """
        # Arrange
        from repositories.constraints import ConstraintRepository

        # Mock response with varying confidence scores
        mock_response = [
            {
                "id": 1,
                "code_pattern": "pattern_1",
                "user_reason": "reason_1",
                "similarity": 0.95,
                "confidence_score": 0.8,  # Above threshold
            },
            {
                "id": 2,
                "code_pattern": "pattern_2",
                "user_reason": "reason_2",
                "similarity": 0.90,
                "confidence_score": 0.3,  # Below threshold
            },
            {
                "id": 3,
                "code_pattern": "pattern_3",
                "user_reason": "reason_3",
                "similarity": 0.85,
                "confidence_score": 0.5,  # At threshold
            },
        ]

        mock_supabase_client.rpc.return_value.execute.return_value.data = mock_response

        repo = ConstraintRepository(
            supabase_client=mock_supabase_client,
            config=constraint_repo_config,
        )

        # Act
        result = repo.check_suppressions(
            query_embedding=sample_query_embedding,
            repo_id="octocat/test-repo",
            min_confidence=0.5,
        )

        # Assert
        assert len(result) == 2  # Only high confidence constraints
        assert all(c.confidence_score >= 0.5 for c in result)

    def test_check_suppressions_returns_empty_list_when_no_matches(
        self,
        mock_supabase_client,
        sample_query_embedding,
        constraint_repo_config,
    ):
        """
        Test: check_suppressions() returns empty list when no constraints match.

        Expected:
        - Returns empty list when Supabase returns no matches
        - Does not raise exception
        """
        # Arrange
        from repositories.constraints import ConstraintRepository

        mock_supabase_client.rpc.return_value.execute.return_value.data = []

        repo = ConstraintRepository(
            supabase_client=mock_supabase_client,
            config=constraint_repo_config,
        )

        # Act
        result = repo.check_suppressions(
            query_embedding=sample_query_embedding,
            repo_id="octocat/test-repo",
        )

        # Assert
        assert result == []
        assert isinstance(result, list)

    def test_check_suppressions_logs_similarity_scores(
        self,
        mock_supabase_client,
        sample_query_embedding,
        mock_supabase_constraint_response,
        constraint_repo_config,
        caplog,
    ):
        """
        Test: check_suppressions() logs similarity scores for observability.

        Expected:
        - Each matched constraint logs similarity score
        - Logs include constraint_id and similarity value
        """
        # Arrange
        from repositories.constraints import ConstraintRepository

        mock_supabase_client.rpc.return_value.execute.return_value.data = (
            mock_supabase_constraint_response
        )

        repo = ConstraintRepository(
            supabase_client=mock_supabase_client,
            config=constraint_repo_config,
        )

        # Act
        repo.check_suppressions(
            query_embedding=sample_query_embedding,
            repo_id="octocat/test-repo",
        )

        # Assert
        assert any("similarity" in record.message.lower() for record in caplog.records)

    def test_check_suppressions_filters_expired_constraints(
        self,
        mock_supabase_client,
        sample_query_embedding,
        constraint_repo_config,
    ):
        """
        Test: check_suppressions() excludes expired constraints.

        Expected:
        - Constraints with expires_at < now are filtered out
        - Only active constraints are returned
        """
        # Arrange
        from datetime import timedelta

        from repositories.constraints import ConstraintRepository

        now = datetime.now()

        mock_response = [
            {
                "id": 1,
                "code_pattern": "active_pattern",
                "user_reason": "Active constraint",
                "similarity": 0.90,
                "confidence_score": 0.7,
                "expires_at": now + timedelta(days=30),  # Active
            },
            {
                "id": 2,
                "code_pattern": "expired_pattern",
                "user_reason": "Expired constraint",
                "similarity": 0.95,
                "confidence_score": 0.8,
                "expires_at": now - timedelta(days=1),  # Expired
            },
        ]

        mock_supabase_client.rpc.return_value.execute.return_value.data = mock_response

        repo = ConstraintRepository(
            supabase_client=mock_supabase_client,
            config=constraint_repo_config,
        )

        # Act
        result = repo.check_suppressions(
            query_embedding=sample_query_embedding,
            repo_id="octocat/test-repo",
        )

        # Assert
        assert len(result) == 1
        assert result[0].id == 1  # Only active constraint

    def test_check_suppressions_handles_supabase_error_gracefully(
        self,
        mock_supabase_client,
        sample_query_embedding,
        constraint_repo_config,
        caplog,
    ):
        """
        Test: check_suppressions() logs error and returns empty list on Supabase failure.

        Expected:
        - Logs error with context
        - Returns empty list (graceful degradation)
        - Does not raise exception
        """
        # Arrange
        from repositories.constraints import ConstraintRepository

        mock_supabase_client.rpc.side_effect = Exception("Supabase connection failed")

        repo = ConstraintRepository(
            supabase_client=mock_supabase_client,
            config=constraint_repo_config,
        )

        # Act
        result = repo.check_suppressions(
            query_embedding=sample_query_embedding,
            repo_id="octocat/test-repo",
        )

        # Assert
        assert result == []
        assert any("error" in record.message.lower() for record in caplog.records)


# =============================================================================
# ConstraintRepository.create_constraint() Tests
# =============================================================================


class TestConstraintRepositoryCreateConstraint:
    """Test suite for ConstraintRepository.create_constraint() method."""

    def test_create_constraint_inserts_into_supabase(
        self,
        mock_supabase_client,
        sample_constraint_record,
        constraint_repo_config,
    ):
        """
        Test: create_constraint() inserts LearnedConstraint into Supabase.

        Expected:
        - Supabase client.table().insert() is called
        - Constraint data includes embedding vector
        - Returns created constraint with id
        """
        # Arrange
        from models.feedback import LearnedConstraint
        from repositories.constraints import ConstraintRepository

        mock_supabase_client.table.return_value.insert.return_value.execute.return_value.data = [
            sample_constraint_record
        ]

        repo = ConstraintRepository(
            supabase_client=mock_supabase_client,
            config=constraint_repo_config,
        )

        constraint = LearnedConstraint(**sample_constraint_record)

        # Act
        result = repo.create_constraint(constraint=constraint)

        # Assert
        mock_supabase_client.table.assert_called_once_with("learned_constraints")
        mock_supabase_client.table.return_value.insert.assert_called_once()

    def test_create_constraint_sets_expiration_date(
        self,
        mock_supabase_client,
        constraint_repo_config,
    ):
        """
        Test: create_constraint() sets expires_at to 90 days from creation.

        Expected:
        - expires_at is calculated as created_at + 90 days
        - Default expiration is 90 days if not specified
        """
        # Arrange

        from models.feedback import LearnedConstraint
        from repositories.constraints import ConstraintRepository

        repo = ConstraintRepository(
            supabase_client=mock_supabase_client,
            config=constraint_repo_config,
        )

        constraint_data = {
            "id": 0,  # Will be assigned by database
            "repo_id": "octocat/test-repo",
            "violation_reason": "sql_injection",
            "code_pattern": "execute(f'SELECT * FROM users WHERE name={name}')",
            "user_reason": "Safe because sanitized",
            "embedding": [0.1] * 1536,
            "confidence_score": 0.5,
            "created_at": datetime.now(),
            "version": 1,
        }

        constraint = LearnedConstraint(**constraint_data)

        # Act
        repo.create_constraint(constraint=constraint)

        # Assert
        call_args = mock_supabase_client.table.return_value.insert.call_args
        inserted_data = call_args[0][0]
        assert "expires_at" in inserted_data

    def test_create_constraint_calculates_initial_confidence(
        self,
        mock_supabase_client,
        constraint_repo_config,
    ):
        """
        Test: create_constraint() calculates initial confidence based on reason.

        Expected:
        - false_positive: confidence += 0.2
        - logic_error: confidence += 0.1
        - style_preference: confidence += 0.05
        - hallucination: confidence += 0.3
        """
        # Arrange
        from models.feedback import LearnedConstraint
        from repositories.constraints import ConstraintRepository

        repo = ConstraintRepository(
            supabase_client=mock_supabase_client,
            config=constraint_repo_config,
        )

        # Test false_positive (base 0.5 + 0.2 = 0.7)
        constraint = LearnedConstraint(
            id=0,
            repo_id="octocat/test-repo",
            violation_reason="sql_injection",
            code_pattern="test pattern",
            user_reason="False positive - safe pattern",
            embedding=[0.1] * 1536,
            confidence_score=0.5,
            created_at=datetime.now(),
            version=1,
        )

        # Act
        repo.create_constraint(constraint=constraint, reason="false_positive")

        # Assert
        call_args = mock_supabase_client.table.return_value.insert.call_args
        inserted_data = call_args[0][0]
        assert inserted_data["confidence_score"] == 0.7


# =============================================================================
# ConstraintRepository.get_active_constraints() Tests
# =============================================================================


class TestConstraintRepositoryGetActiveConstraints:
    """Test suite for ConstraintRepository.get_active_constraints() method."""

    def test_get_active_constraints_queries_by_repo_id(
        self,
        mock_supabase_client,
        constraint_repo_config,
    ):
        """
        Test: get_active_constraints() filters constraints by repo_id.

        Expected:
        - Supabase query filters by repo_id
        - Returns only non-expired constraints
        """
        # Arrange
        from repositories.constraints import ConstraintRepository

        mock_supabase_client.table.return_value.select.return_value.filter.return_value.execute.return_value.data = []

        repo = ConstraintRepository(
            supabase_client=mock_supabase_client,
            config=constraint_repo_config,
        )

        # Act
        result = repo.get_active_constraints(repo_id="octocat/test-repo")

        # Assert
        mock_supabase_client.table.assert_called_once_with("learned_constraints")

    def test_get_active_constraints_filters_expired(
        self,
        mock_supabase_client,
        constraint_repo_config,
    ):
        """
        Test: get_active_constraints() excludes expired constraints.

        Expected:
        - Only constraints with expires_at > now are returned
        - Expired constraints are filtered from results
        """
        # Arrange
        from datetime import timedelta

        from repositories.constraints import ConstraintRepository

        now = datetime.now()

        mock_data = [
            {
                "id": 1,
                "code_pattern": "active",
                "confidence_score": 0.7,
                "expires_at": now + timedelta(days=30),
            },
            {
                "id": 2,
                "code_pattern": "expired",
                "confidence_score": 0.5,
                "expires_at": now - timedelta(days=1),
            },
        ]

        mock_supabase_client.table.return_value.select.return_value.filter.return_value.execute.return_value.data = mock_data

        repo = ConstraintRepository(
            supabase_client=mock_supabase_client,
            config=constraint_repo_config,
        )

        # Act
        result = repo.get_active_constraints(repo_id="octocat/test-repo")

        # Assert
        # Should filter out expired at application level if not done in SQL
        assert len(result) == 1
        assert all(c.expires_at > now for c in result)


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestConstraintRepositoryEdgeCases:
    """Test suite for edge cases and error handling."""

    def test_handles_invalid_embedding_dimension(
        self,
        mock_supabase_client,
        constraint_repo_config,
        caplog,
    ):
        """
        Test: Handles embeddings with incorrect dimension gracefully.

        Expected:
        - Logs warning about invalid embedding
        - Returns empty list or raises ValidationError
        """
        # Arrange
        from repositories.constraints import ConstraintRepository

        invalid_embedding = [0.1, 0.2, 0.3]  # Wrong dimensions

        repo = ConstraintRepository(
            supabase_client=mock_supabase_client,
            config=constraint_repo_config,
        )

        # Act & Assert
        with pytest.raises(ValueError):
            repo.check_suppressions(
                query_embedding=invalid_embedding,
                repo_id="octocat/test-repo",
            )

    def test_handles_null_embedding_in_database(
        self,
        mock_supabase_client,
        sample_query_embedding,
        constraint_repo_config,
    ):
        """
        Test: Handles constraints with null embeddings from database.

        Expected:
        - Skips constraints with null embeddings
        - Returns only valid constraints
        """
        # Arrange
        from repositories.constraints import ConstraintRepository

        mock_response = [
            {
                "id": 1,
                "code_pattern": "valid_pattern",
                "user_reason": "Valid",
                "similarity": 0.90,
                "confidence_score": 0.7,
            },
            {
                "id": 2,
                "code_pattern": "null_embedding",
                "user_reason": "Null",
                "similarity": None,  # Null similarity
                "confidence_score": 0.5,
            },
        ]

        mock_supabase_client.rpc.return_value.execute.return_value.data = mock_response

        repo = ConstraintRepository(
            supabase_client=mock_supabase_client,
            config=constraint_repo_config,
        )

        # Act
        result = repo.check_suppressions(
            query_embedding=sample_query_embedding,
            repo_id="octocat/test-repo",
        )

        # Assert
        assert len(result) == 1  # Only valid constraint
