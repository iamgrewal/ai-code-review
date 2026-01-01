"""
Feedback Service for RLHF (Reinforcement Learning from Human Feedback).

Orchestrates feedback processing workflow:
1. Validate feedback request
2. Create audit log entry (FeedbackRecord)
3. Generate embedding for code pattern
4. Create learned constraint (if rejected)
5. Update confidence scores (if similar constraint exists)
6. Track metrics

Constitution VI: Learning Loop - User feedback drives continuous improvement.
"""

from loguru import logger
from openai import OpenAI
from supabase import Client

from models.feedback import FeedbackRequest, LearnedConstraint
from repositories.constraints import ConstraintRepository
from repositories.feedback import FeedbackRepository
from utils.config import Config
from utils.metrics import (
    feedback_submitted_total,
)


class FeedbackService:
    """
    Service for processing user feedback and managing RLHF learning loop.

    Coordinates between repositories to:
    - Log all feedback for compliance
    - Create learned constraints from rejected feedback
    - Update constraint confidence scores
    - Calculate false positive reduction metrics
    """

    def __init__(
        self,
        supabase_client: Client,
        llm_client: OpenAI,
        config: Config,
    ):
        """
        Initialize feedback service.

        Args:
            supabase_client: Supabase client for database operations
            llm_client: OpenAI client for embedding generation
            config: Application configuration
        """
        self.supabase = supabase_client
        self.llm_client = llm_client
        self.config = config

        # Initialize repositories
        self.feedback_repo = FeedbackRepository(supabase_client)
        self.constraint_repo = ConstraintRepository(supabase_client)

    def process_feedback(
        self,
        feedback: FeedbackRequest,
        review_id: str,
        repo_id: str,
        trace_id: str,
    ) -> dict:
        """
        Process user feedback through RLHF learning loop.

        Workflow (T047-T054):
        1. Validate feedback request
        2. Create FeedbackRecord audit log entry
        3. If action=rejected:
           a. Generate embedding for code_pattern
           b. Check for similar existing constraints
           c. Create new constraint or update existing
        4. Track metrics

        Args:
            feedback: Validated feedback request
            review_id: Associated review ID
            repo_id: Repository identifier
            trace_id: Correlation ID for distributed tracing

        Returns:
            dict with processing result

        Raises:
            ValueError: If feedback validation fails
            Exception: If processing fails
        """
        logger.bind(
            trace_id=trace_id,
            comment_id=feedback.comment_id,
            action=feedback.action,
        ).info("Processing feedback")

        # Step 1: Validate feedback request (T047)
        self._validate_feedback(feedback)

        # Step 2: Create FeedbackRecord audit log entry (T048)
        feedback_record = self.feedback_repo.create_record(
            review_id=review_id,
            comment_id=feedback.comment_id,
            user_id=feedback.user_id or "anonymous",
            action=feedback.action,
            reason=feedback.reason,
            developer_comment=feedback.developer_comment,
            final_code_snapshot=feedback.final_code_snapshot,
            trace_id=trace_id,
        )

        # Step 3: Track feedback metric (T049)
        feedback_submitted_total.labels(action=feedback.action).inc()

        # Step 4: Process rejected feedback to create learned constraint (T050)
        constraint = None
        if feedback.action == "rejected":
            constraint = self._process_rejected_feedback(
                feedback=feedback,
                repo_id=repo_id,
                trace_id=trace_id,
            )

        # Step 5: Calculate and update false positive reduction ratio (T075)
        self._update_fp_reduction_metrics(repo_id)

        return {
            "status": "success",
            "feedback_id": feedback_record.id,
            "constraint_id": constraint.id if constraint else None,
            "action": feedback.action,
        }

    def _validate_feedback(self, feedback: FeedbackRequest) -> None:
        """
        Validate feedback request meets requirements.

        Args:
            feedback: Feedback request to validate

        Raises:
            ValueError: If validation fails
        """
        if not feedback.comment_id:
            raise ValueError("comment_id is required")

        if feedback.action not in ("accepted", "rejected", "modified"):
            raise ValueError(f"Invalid action: {feedback.action}")

        if feedback.action == "rejected" and not feedback.reason:
            raise ValueError("reason is required for rejected feedback")

        if len(feedback.developer_comment) < 1:
            raise ValueError("developer_comment must not be empty")

        if len(feedback.developer_comment) > 1000:
            raise ValueError("developer_comment must not exceed 1000 characters")

        if not feedback.final_code_snapshot:
            raise ValueError("final_code_snapshot is required")

    def _process_rejected_feedback(
        self,
        feedback: FeedbackRequest,
        repo_id: str,
        trace_id: str,
    ) -> LearnedConstraint:
        """
        Process rejected feedback to create/update learned constraint.

        Args:
            feedback: Rejected feedback request
            repo_id: Repository identifier
            trace_id: Correlation ID

        Returns:
            LearnedConstraint: Created or updated constraint

        Raises:
            Exception: If constraint creation fails
        """
        logger.bind(
            trace_id=trace_id,
            comment_id=feedback.comment_id,
            reason=feedback.reason,
        ).info("Processing rejected feedback")

        # Step 1: Generate embedding for code pattern (T051)
        code_pattern = self._extract_code_pattern(feedback)
        embedding = self._generate_embedding(code_pattern)

        # Step 2: Check for similar existing constraints (T052)
        similar_constraints = self.constraint_repo.check_suppressions(
            repo_id=repo_id,
            embedding=embedding,
            threshold=self.config.RLHF_THRESHOLD,
        )

        # Step 3: Create new constraint or update existing (T053)
        if similar_constraints:
            # Similar constraint exists, update confidence score
            existing = similar_constraints[0]
            new_confidence = min(1.0, existing.confidence_score + 0.1)

            updated = self.constraint_repo.update_confidence(
                constraint_id=existing.id,
                new_confidence=new_confidence,
            )

            logger.bind(
                constraint_id=existing.id,
                old_confidence=existing.confidence_score,
                new_confidence=new_confidence,
            ).info("Updated existing constraint confidence")

            return updated or existing
        else:
            # No similar constraint, create new one
            constraint = self.constraint_repo.create_constraint(
                repo_id=repo_id,
                violation_reason=feedback.reason,
                code_pattern=code_pattern,
                user_reason=feedback.developer_comment,
                embedding=embedding,
                expires_in_days=self.config.CONSTRAINT_EXPIRATION_DAYS,
            )

            logger.bind(
                constraint_id=constraint.id,
                confidence=constraint.confidence_score,
                expires_at=constraint.expires_at.isoformat() if constraint.expires_at else None,
            ).info("Created new learned constraint")

            return constraint

    def _extract_code_pattern(self, feedback: FeedbackRequest) -> str:
        """
        Extract code pattern from feedback for embedding.

        Uses final_code_snapshot as the pattern to match against.

        Args:
            feedback: Feedback request

        Returns:
            Code pattern string
        """
        # Use final code snapshot as the pattern
        # This is what the user actually committed
        return feedback.final_code_snapshot

    def _generate_embedding(self, text: str) -> list[float]:
        """
        Generate embedding for code pattern using OpenAI API.

        Args:
            text: Text to embed

        Returns:
            List of embedding values (1536-dimensional)

        Raises:
            Exception: If embedding generation fails
        """
        try:
            response = self.llm_client.embeddings.create(
                model=self.config.EMBEDDING_MODEL,
                input=text[:8000],  # OpenAI limit
            )

            embedding = response.data[0].embedding

            # Track token usage (T051)
            from utils.metrics import llm_tokens_total

            llm_tokens_total.labels(
                model_type="embedding",
                model_name=self.config.EMBEDDING_MODEL,
            ).inc(response.usage.total_tokens)

            return embedding

        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise

    def _update_fp_reduction_metrics(self, repo_id: str) -> None:
        """
        Update false positive reduction ratio gauge.

        Args:
            repo_id: Repository identifier
        """
        try:
            ratio = self.feedback_repo.calculate_false_positive_reduction(
                repo_id=repo_id,
                days_back=30,
            )

            # Update gauge metric (T075)
            from utils.metrics import false_positive_reduction_ratio

            false_positive_reduction_ratio.labels(repo_id=repo_id).set(ratio)

        except Exception as e:
            logger.warning(f"Failed to update FP reduction metrics: {e}")


# =============================================================================
# Module Exports
# =============================================================================
__all__ = ["FeedbackService"]
