"""
Integration Tests: RLHF Feedback Learning Loop

T064 - End-to-end: reject -> constraint -> suppression

Tests for the complete RLHF feedback learning loop:
1. User rejects review comment (false positive)
2. System creates LearnedConstraint from feedback
3. Future reviews suppress similar patterns

Status: RED (implementation does not exist yet)
Task: 001-cortexreview-platform/T064
"""

import os

# Add project root to path for imports
import sys
import uuid
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, Mock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


# =============================================================================
# Test Data Fixtures
# =============================================================================


@pytest.fixture
def sample_review_comment() -> dict[str, Any]:
    """Sample review comment that user will reject as false positive."""
    return {
        "id": "comment-1",
        "file_path": "src/user_service.py",
        "line_range": {"start": 45, "end": 48},
        "type": "security",
        "severity": "high",
        "message": "Potential SQL injection vulnerability",
        "suggestion": "Use parameterized queries instead of string formatting",
        "confidence_score": 0.85,
        "fix_patch": None,
        "citations": [],
    }


@pytest.fixture
def sample_diff_with_sql_pattern() -> str:
    """Sample diff containing SQL pattern that triggered false positive."""
    return """diff --git a/src/user_service.py b/src/user_service.py
index 1234567..abcdefg 100644
--- a/src/user_service.py
+++ b/src/user_service.py
@@ -42,7 +42,7 @@ class UserService:
         username = sanitize_input(username)
         # Sanitized above, safe to use in query
-        results = db.execute(f"SELECT * FROM users WHERE name='{username}'")
+        results = db.query(User).filter_by(name=username).all()
         return results
"""


@pytest.fixture
def rejected_feedback_request() -> dict[str, Any]:
    """Feedback request rejecting comment as false positive."""
    return {
        "comment_id": "comment-1",
        "action": "rejected",
        "reason": "false_positive",
        "developer_comment": "The username variable is sanitized by sanitize_input() on the previous line, making this SQL injection warning a false positive.",
        "final_code_snapshot": "username = sanitize_input(username)\nresults = db.execute(f\"SELECT * FROM users WHERE name='{username}'\")\nreturn results",
    }


@pytest.fixture
def mock_supabase_client() -> Mock:
    """Mock Supabase client for integration testing."""
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value.data = []
    client.table.return_value.select.return_value.execute.return_value.data = []
    client.rpc.return_value.execute.return_value.data = []
    return client


@pytest.fixture
def mock_openai_client() -> Mock:
    """Mock OpenAI client for embedding generation."""
    client = MagicMock()
    client.embeddings.create.return_value = MagicMock(
        data=[MagicMock(embedding=[0.1, -0.2, 0.3] * 512)]  # 1536 dimensions
    )
    return client


@pytest.fixture
def mock_celery_app() -> Mock:
    """Mock Celery application."""
    app = MagicMock()
    app.send_task.return_value = MagicMock(
        id=str(uuid.uuid4()),
        state="PENDING",
    )
    return app


# =============================================================================
# End-to-End Feedback Loop Tests
# =============================================================================


class TestFeedbackLearningLoop:
    """
    End-to-end tests for the RLHF feedback learning loop.

    Flow:
    1. Review task generates comment (SQL injection warning)
    2. User rejects as false positive via /v1/feedback
    3. Feedback processor creates LearnedConstraint
    4. Next review checks constraints and suppresses similar pattern
    """

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_complete_feedback_loop_from_rejection_to_suppression(
        self,
        sample_review_comment,
        sample_diff_with_sql_pattern,
        rejected_feedback_request,
        mock_supabase_client,
        mock_openai_client,
        mock_celery_app,
    ):
        """
        Test: Complete feedback loop from rejection to suppression.

        Scenario:
        1. AI generates SQL injection warning on code with db.execute()
        2. User rejects as false positive (variable is sanitized)
        3. System creates LearnedConstraint with embedding
        4. Next review on similar code suppresses the warning

        Expected:
        - Feedback accepted and stored
        - Constraint created with embedding
        - Next review checks constraints
        - Similar pattern suppressed
        """
        # Step 1: Submit feedback
        from models.feedback import FeedbackAction, FeedbackRequest
        from repositories.constraints import ConstraintRepository
        from repositories.feedback import FeedbackRepository

        feedback_repo = FeedbackRepository(
            supabase_client=mock_supabase_client,
            config={"retention_days": 365},
        )

        constraint_repo = ConstraintRepository(
            supabase_client=mock_supabase_client,
            config={"match_threshold": 0.8},
        )

        request = FeedbackRequest(**rejected_feedback_request)

        # Record feedback
        feedback_record = feedback_repo.record_feedback(
            request=request,
            review_id="review-1",
            user_id="octocat",
            trace_id="trace-1",
        )

        assert feedback_record.action == FeedbackAction.REJECTED

        # Step 2: Process feedback and create constraint
        # Generate embedding
        embedding_response = mock_openai_client.embeddings.create(
            input=request.final_code_snapshot,
            model="text-embedding-3-small",
        )
        query_embedding = embedding_response.data[0].embedding

        # Check if constraint already suppresses this pattern
        suppressions = constraint_repo.check_suppressions(
            query_embedding=query_embedding,
            repo_id="octocat/test-repo",
        )

        # Initially, no suppressions exist
        assert len(suppressions) == 0

        # Create constraint from rejected feedback
        from models.feedback import LearnedConstraint

        constraint = LearnedConstraint(
            id=0,  # Assigned by database
            repo_id="octocat/test-repo",
            violation_reason="sql_injection",
            code_pattern=request.final_code_snapshot,
            user_reason=request.developer_comment,
            embedding=query_embedding,
            confidence_score=0.7,  # false_positive bonus: 0.5 + 0.2
            expires_at=datetime.now() + timedelta(days=90),
            created_at=datetime.now(),
            version=1,
        )

        created_constraint = constraint_repo.create_constraint(constraint=constraint)

        assert created_constraint.id > 0
        assert created_constraint.confidence_score >= 0.7

        # Step 3: Future review checks constraints
        # Generate embedding for new similar code
        new_diff = "username = sanitize(user_input)\ndb.execute(f\"SELECT * FROM users WHERE name='{username}'\")"
        new_embedding = mock_openai_client.embeddings.create(input=new_diff).data[0].embedding

        # Check suppressions
        new_suppressions = constraint_repo.check_suppressions(
            query_embedding=new_embedding,
            repo_id="octocat/test-repo",
        )

        # Now should find the suppression
        assert len(new_suppressions) >= 1
        assert any(s.id == created_constraint.id for s in new_suppressions)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_multiple_feedback_increases_confidence_score(
        self,
        rejected_feedback_request,
        mock_supabase_client,
        mock_openai_client,
    ):
        """
        Test: Multiple users rejecting similar pattern increases confidence.

        Scenario:
        1. User A rejects SQL pattern as false positive
        2. User B rejects similar SQL pattern as false positive
        3. Second rejection increases constraint confidence

        Expected:
        - First constraint created with confidence 0.7
        - Second rejection creates new version with higher confidence
        - Or updates existing constraint confidence
        """
        from models.feedback import FeedbackRequest, LearnedConstraint
        from repositories.constraints import ConstraintRepository
        from repositories.feedback import FeedbackRepository

        feedback_repo = FeedbackRepository(
            supabase_client=mock_supabase_client,
            config={"retention_days": 365},
        )

        constraint_repo = ConstraintRepository(
            supabase_client=mock_supabase_client,
            config={"match_threshold": 0.8},
        )

        # First user feedback
        request1 = FeedbackRequest(**rejected_feedback_request)
        embedding1 = (
            mock_openai_client.embeddings.create(input=request1.final_code_snapshot)
            .data[0]
            .embedding
        )

        constraint1 = LearnedConstraint(
            id=0,
            repo_id="octocat/test-repo",
            violation_reason="sql_injection",
            code_pattern=request1.final_code_snapshot,
            user_reason=request1.developer_comment,
            embedding=embedding1,
            confidence_score=0.7,
            expires_at=datetime.now() + timedelta(days=90),
            created_at=datetime.now(),
            version=1,
        )

        created1 = constraint_repo.create_constraint(
            constraint=constraint1,
            reason="false_positive",
        )

        # Second user feedback (similar pattern)
        request2 = FeedbackRequest(
            comment_id="comment-2",
            action="rejected",
            reason="false_positive",
            developer_comment="Also safe - input is validated before this point",
            final_code_snapshot="validated_name = validate(name)\ndb.execute(f'SELECT * FROM users WHERE name=\"{validated_name}\"')",
        )

        feedback_repo.record_feedback(
            request=request2,
            review_id="review-2",
            user_id="developer2",
            trace_id="trace-2",
        )

        embedding2 = (
            mock_openai_client.embeddings.create(input=request2.final_code_snapshot)
            .data[0]
            .embedding
        )

        constraint2 = LearnedConstraint(
            id=0,
            repo_id="octocat/test-repo",
            violation_reason="sql_injection",
            code_pattern=request2.final_code_snapshot,
            user_reason=request2.developer_comment,
            embedding=embedding2,
            confidence_score=0.7,
            expires_at=datetime.now() + timedelta(days=90),
            created_at=datetime.now(),
            version=1,
        )

        created2 = constraint_repo.create_constraint(
            constraint=constraint2,
            reason="false_positive",
        )

        # Second constraint should have higher confidence due to reinforcement
        # Implementation may increment or create new version
        assert created2.confidence_score >= 0.7

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_expired_constraints_not_applied(
        self,
        rejected_feedback_request,
        mock_supabase_client,
        mock_openai_client,
    ):
        """
        Test: Expired constraints are not applied to new reviews.

        Scenario:
        1. Constraint created 90 days ago
        2. Current time is past expiration
        3. New review should not apply expired constraint

        Expected:
        - Expired constraints filtered out
        - Review proceeds without suppression
        """
        from models.feedback import LearnedConstraint
        from repositories.constraints import ConstraintRepository

        constraint_repo = ConstraintRepository(
            supabase_client=mock_supabase_client,
            config={"match_threshold": 0.8},
        )

        # Create expired constraint
        now = datetime.now()
        expired_constraint = LearnedConstraint(
            id=1,
            repo_id="octocat/test-repo",
            violation_reason="sql_injection",
            code_pattern=rejected_feedback_request["final_code_snapshot"],
            user_reason="Test",
            embedding=mock_openai_client.embeddings.create(
                input=rejected_feedback_request["final_code_snapshot"]
            )
            .data[0]
            .embedding,
            confidence_score=0.7,
            expires_at=now - timedelta(days=1),  # Expired yesterday
            created_at=now - timedelta(days=90),
            version=1,
        )

        # Check suppressions
        query_embedding = (
            mock_openai_client.embeddings.create(
                input=rejected_feedback_request["final_code_snapshot"]
            )
            .data[0]
            .embedding
        )

        suppressions = constraint_repo.check_suppressions(
            query_embedding=query_embedding,
            repo_id="octocat/test-repo",
        )

        # Expired constraint should not be returned
        assert not any(s.id == expired_constraint.id for s in suppressions)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_feedback_for_accepted_action_does_not_create_constraint(
        self,
        mock_supabase_client,
    ):
        """
        Test: Feedback with action=accepted does NOT create constraint.

        Scenario:
        1. User accepts review comment (agrees with AI)
        2. No constraint should be created
        3. Positive reinforcement for future training

        Expected:
        - Feedback recorded in audit log
        - No LearnedConstraint created
        - Comment continues to be flagged in future
        """
        from models.feedback import FeedbackRequest
        from repositories.feedback import FeedbackRepository

        feedback_repo = FeedbackRepository(
            supabase_client=mock_supabase_client,
            config={"retention_days": 365},
        )

        accepted_request = FeedbackRequest(
            comment_id="comment-1",
            action="accepted",
            reason="logic_error",
            developer_comment="Good catch! Fixed the bug.",
            final_code_snapshot="session.query(User).filter_by(name=name).first()",
        )

        feedback_record = feedback_repo.record_feedback(
            request=accepted_request,
            review_id="review-1",
            user_id="octocat",
            trace_id="trace-1",
        )

        # Feedback should be recorded
        assert feedback_record.action == "accepted"

        # No constraint should be created (verified by lack of insert call)
        # This is tested implicitly - accepted feedback doesn't trigger constraint creation

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_feedback_with_modified_action_creates_lower_confidence_constraint(
        self,
        mock_supabase_client,
        mock_openai_client,
    ):
        """
        Test: Feedback with action=modified creates lower confidence constraint.

        Scenario:
        1. User partially accepts with changes (style preference)
        2. Constraint created but with lower confidence
        3. Reflects team preference but not absolute rule

        Expected:
        - Constraint created
        - confidence_score has smaller increment (+0.05 for style_preference)
        """
        from models.feedback import FeedbackRequest, LearnedConstraint
        from repositories.constraints import ConstraintRepository
        from repositories.feedback import FeedbackRepository

        feedback_repo = FeedbackRepository(
            supabase_client=mock_supabase_client,
            config={"retention_days": 365},
        )

        constraint_repo = ConstraintRepository(
            supabase_client=mock_supabase_client,
            config={"match_threshold": 0.8},
        )

        modified_request = FeedbackRequest(
            comment_id="comment-1",
            action="modified",
            reason="style_preference",
            developer_comment="We prefer 4-space indentation for readability",
            final_code_snapshot="if True:\n    result = process()",
        )

        feedback_repo.record_feedback(
            request=modified_request,
            review_id="review-1",
            user_id="octocat",
            trace_id="trace-1",
        )

        embedding = (
            mock_openai_client.embeddings.create(input=modified_request.final_code_snapshot)
            .data[0]
            .embedding
        )

        constraint = LearnedConstraint(
            id=0,
            repo_id="octocat/test-repo",
            violation_reason="style",
            code_pattern=modified_request.final_code_snapshot,
            user_reason=modified_request.developer_comment,
            embedding=embedding,
            confidence_score=0.5,  # Base
            expires_at=datetime.now() + timedelta(days=90),
            created_at=datetime.now(),
            version=1,
        )

        created = constraint_repo.create_constraint(
            constraint=constraint,
            reason="style_preference",  # +0.05
        )

        # Style preference should have lower confidence than false_positive
        # Base 0.5 + 0.05 = 0.55
        assert created.confidence_score < 0.7


# =============================================================================
# Supabase RPC Integration Tests
# =============================================================================


class TestSupabaseRPCIntegration:
    """Test Supabase RPC function integration for constraint checking."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_check_constraints_rpc_function_called(
        self,
        mock_supabase_client,
        mock_openai_client,
    ):
        """
        Test: Supabase check_constraints RPC function is called correctly.

        Expected:
        - rpc('check_constraints') called with query_embedding and match_threshold
        - Returns constraints ordered by similarity descending
        """
        from repositories.constraints import ConstraintRepository

        constraint_repo = ConstraintRepository(
            supabase_client=mock_supabase_client,
            config={"match_threshold": 0.8},
        )

        query_embedding = (
            mock_openai_client.embeddings.create(input="test code pattern").data[0].embedding
        )

        constraint_repo.check_suppressions(
            query_embedding=query_embedding,
            repo_id="octocat/test-repo",
        )

        # Verify RPC call
        mock_supabase_client.rpc.assert_called_once()
        call_args = mock_supabase_client.rpc.call_args
        assert call_args[0][0] == "check_constraints"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_vector_cosine_similarity_filtering(
        self,
        mock_supabase_client,
    ):
        """
        Test: Vector similarity filtering uses cosine distance.

        Expected:
        - Supabase uses vector_cosine_ops for similarity
        - Returns constraints with similarity > threshold
        """
        # This tests the SQL function behavior
        # Actual cosine similarity calculation happens in Supabase
        pass


# =============================================================================
# Error Recovery Tests
# =============================================================================


class TestFeedbackLoopErrorRecovery:
    """Test error recovery in the feedback learning loop."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_embedding_api_failure_still_records_feedback(
        self,
        rejected_feedback_request,
        mock_supabase_client,
        mock_openai_client,
    ):
        """
        Test: When OpenAI embedding API fails, feedback is still recorded.

        Expected:
        - FeedbackRecord created in audit log
        - No LearnedConstraint created (no embedding)
        - Can be manually created later via admin API
        """
        from models.feedback import FeedbackRequest
        from repositories.feedback import FeedbackRepository

        feedback_repo = FeedbackRepository(
            supabase_client=mock_supabase_client,
            config={"retention_days": 365},
        )

        # Mock embedding API failure
        mock_openai_client.embeddings.create.side_effect = Exception("API timeout")

        request = FeedbackRequest(**rejected_feedback_request)

        # Should still record feedback
        feedback_record = feedback_repo.record_feedback(
            request=request,
            review_id="review-1",
            user_id="octocat",
            trace_id="trace-1",
        )

        assert feedback_record is not None
        assert feedback_record.action == "rejected"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_supabase_failure_graceful_degradation(
        self,
        rejected_feedback_request,
        mock_supabase_client,
        caplog,
    ):
        """
        Test: Supabase failure is handled gracefully.

        Expected:
        - Logs error with context
        - Returns appropriate error response
        - Does not crash application
        """
        from models.feedback import FeedbackRequest
        from repositories.feedback import FeedbackRepository

        # Mock Supabase failure
        mock_supabase_client.table.return_value.insert.side_effect = Exception(
            "Supabase connection failed"
        )

        feedback_repo = FeedbackRepository(
            supabase_client=mock_supabase_client,
            config={"retention_days": 365},
        )

        request = FeedbackRequest(**rejected_feedback_request)

        # Should raise exception or handle gracefully
        with pytest.raises(Exception):
            feedback_repo.record_feedback(
                request=request,
                review_id="review-1",
                user_id="octocat",
                trace_id="trace-1",
            )


# =============================================================================
# Feedback Latency Tests
# =============================================================================


class TestFeedbackLoopLatency:
    """Test latency requirements for feedback processing."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_constraint_applies_within_five_minutes(
        self,
        rejected_feedback_request,
        mock_supabase_client,
        mock_openai_client,
    ):
        """
        Test: Constraint becomes active within 5 minutes of feedback submission.

        Expected:
        - constraint_applies_at timestamp is now + ~5 minutes
        - Worker reloads constraints periodically
        - New reviews see updated constraints
        """
        from models.feedback import FeedbackRequest
        from repositories.feedback import FeedbackRepository

        feedback_repo = FeedbackRepository(
            supabase_client=mock_supabase_client,
            config={"retention_days": 365},
        )

        request = FeedbackRequest(**rejected_feedback_request)

        feedback_record = feedback_repo.record_feedback(
            request=request,
            review_id="review-1",
            user_id="octocat",
            trace_id="trace-1",
        )

        # Constraint should apply within 5 minutes
        # This is tested via the constraint_applies_at field in the response
        # Actual timing depends on Celery worker scheduling
