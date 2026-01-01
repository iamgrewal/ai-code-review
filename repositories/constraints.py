"""
Constraint Repository for RLHF (Reinforcement Learning from Human Feedback).

Manages learned constraints stored in Supabase, including:
- Creating constraints from rejected feedback
- Checking for matching constraints to suppress false positives
- Auto-expiring old constraints (90-day policy)
- Calculating confidence scores based on feedback frequency
"""

import uuid
from datetime import datetime, timedelta

from loguru import logger
from supabase import Client

from models.feedback import LearnedConstraint
from utils.metrics import constraint_count


class ConstraintRepository:
    """
    Repository for managing learned constraints in Supabase.

    Learned constraints are negative examples from user feedback that
    suppress similar false positive patterns in future reviews.
    """

    def __init__(self, supabase_client: Client):
        """
        Initialize constraint repository.

        Args:
            supabase_client: Supabase client instance
        """
        self.client = supabase_client

    def create_constraint(
        self,
        repo_id: str,
        violation_reason: str,
        code_pattern: str,
        user_reason: str,
        embedding: list[float],
        expires_in_days: int = 90,
    ) -> LearnedConstraint:
        """
        Create a new learned constraint from rejected feedback.

        Args:
            repo_id: Repository identifier (owner/repo)
            violation_reason: Original violation reason from review
            code_pattern: Code pattern that was flagged
            user_reason: User's explanation for rejection
            embedding: Vector embedding of the code pattern
            expires_in_days: Days until auto-expiration (default 90)

        Returns:
            LearnedConstraint: Created constraint record

        Raises:
            Exception: If database operation fails
        """
        constraint_id = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        # Calculate initial confidence score (T071)
        # Start at 0.5, increases with repeated similar feedback
        confidence_score = self._calculate_initial_confidence(repo_id, code_pattern, embedding)

        constraint_data = {
            "id": constraint_id,
            "repo_id": repo_id,
            "violation_reason": violation_reason,
            "code_pattern": code_pattern,
            "user_reason": user_reason,
            "embedding": embedding,
            "confidence_score": confidence_score,
            "expires_at": expires_at.isoformat(),
            "created_at": datetime.utcnow().isoformat(),
            "version": 1,
        }

        try:
            result = self.client.table("learned_constraints").insert(constraint_data).execute()

            logger.bind(
                constraint_id=constraint_id,
                repo_id=repo_id,
                confidence=confidence_score,
                expires_at=expires_at.isoformat(),
            ).info("Created learned constraint")

            # Update constraint count gauge (T075)
            constraint_count.labels(repo_id=repo_id).inc()

            return LearnedConstraint(**constraint_data)

        except Exception as e:
            logger.error(f"Failed to create constraint: {e}")
            raise

    def check_suppressions(
        self,
        repo_id: str,
        embedding: list[float],
        threshold: float = 0.8,
    ) -> list[LearnedConstraint]:
        """
        Check for matching constraints that should suppress this pattern.

        Uses vector similarity search to find learned constraints that match
        the current code pattern. Matches above threshold are suppressed.

        Args:
            repo_id: Repository identifier
            embedding: Query embedding for current code pattern
            threshold: Similarity threshold for matching (default 0.8)

        Returns:
            List of matching LearnedConstraint objects

        Raises:
            Exception: If database query fails
        """
        try:
            # Call Supabase RPC function for vector similarity search
            response = self.client.rpc(
                "check_constraints",
                {
                    "p_repo_id": repo_id,
                    "query_embedding": embedding,
                    "match_threshold": threshold,
                },
            ).execute()

            constraints = [LearnedConstraint(**row) for row in response.data]

            if constraints:
                logger.bind(
                    repo_id=repo_id,
                    match_count=len(constraints),
                    threshold=threshold,
                ).info(f"Found {len(constraints)} matching constraints")

                # Track suppression metrics (T075)
                for constraint in constraints:
                    confidence_level = self._get_confidence_level(constraint.confidence_score)
                    from utils.metrics import constraint_suppressions_total

                    constraint_suppressions_total.labels(
                        repo_id=repo_id,
                        confidence_level=confidence_level,
                    ).inc()

            return constraints

        except Exception as e:
            logger.warning(f"Failed to check constraints (graceful fallback): {e}")
            # Return empty list on failure (graceful degradation)
            return []

    def get_by_id(self, constraint_id: str) -> LearnedConstraint | None:
        """
        Retrieve a constraint by ID.

        Args:
            constraint_id: Constraint identifier

        Returns:
            LearnedConstraint if found, None otherwise
        """
        try:
            result = (
                self.client.table("learned_constraints")
                .select("*")
                .eq("id", constraint_id)
                .execute()
            )

            if result.data:
                return LearnedConstraint(**result.data[0])
            return None

        except Exception as e:
            logger.error(f"Failed to get constraint {constraint_id}: {e}")
            return None

    def update_confidence(
        self,
        constraint_id: str,
        new_confidence: float,
    ) -> LearnedConstraint | None:
        """
        Update constraint confidence score.

        Called when similar feedback is received, increasing confidence
        that this pattern should be suppressed.

        Args:
            constraint_id: Constraint identifier
            new_confidence: New confidence score (0.0-1.0)

        Returns:
            Updated LearnedConstraint if found, None otherwise
        """
        try:
            result = (
                self.client.table("learned_constraints")
                .update({"confidence_score": new_confidence})
                .eq("id", constraint_id)
                .execute()
            )

            if result.data:
                logger.bind(
                    constraint_id=constraint_id,
                    new_confidence=new_confidence,
                ).info("Updated constraint confidence")
                return LearnedConstraint(**result.data[0])
            return None

        except Exception as e:
            logger.error(f"Failed to update constraint confidence: {e}")
            return None

    def delete_expired(self, days_old: int = 90) -> int:
        """
        Delete expired constraints older than specified days.

        Args:
            days_old: Age in days for expiration (default 90)

        Returns:
            Number of constraints deleted

        Raises:
            Exception: If database operation fails
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)

        try:
            result = (
                self.client.table("learned_constraints")
                .delete()
                .lt("created_at", cutoff_date.isoformat())
                .execute()
            )

            deleted_count = len(result.data) if result.data else 0

            if deleted_count > 0:
                logger.info(f"Deleted {deleted_count} expired constraints")

                # Track expiration metrics
                from utils.metrics import constraint_expirations_total

                # Get repo_ids from deleted constraints
                repo_ids = set(row.get("repo_id", "unknown") for row in result.data)
                for repo_id in repo_ids:
                    constraint_expirations_total.labels(repo_id=repo_id).inc(deleted_count)
                    constraint_count.labels(repo_id=repo_id).dec(deleted_count)

            return deleted_count

        except Exception as e:
            logger.error(f"Failed to delete expired constraints: {e}")
            return 0

    def get_active_count(self, repo_id: str) -> int:
        """
        Get count of active (non-expired) constraints for repository.

        Args:
            repo_id: Repository identifier

        Returns:
            Number of active constraints
        """
        try:
            now = datetime.utcnow().isoformat()
            result = (
                self.client.table("learned_constraints")
                .select("*", count="exact")
                .eq("repo_id", repo_id)
                .gte("expires_at", now)
                .execute()
            )

            return result.count if hasattr(result, "count") else 0

        except Exception as e:
            logger.error(f"Failed to get constraint count: {e}")
            return 0

    # -------------------------------------------------------------------------
    # Private Helper Methods
    # -------------------------------------------------------------------------

    def _calculate_initial_confidence(
        self,
        repo_id: str,
        code_pattern: str,
        embedding: list[float],
    ) -> float:
        """
        Calculate initial confidence score for new constraint.

        Checks for similar existing constraints. If similar patterns exist,
        starts with higher confidence (0.6-0.7). Otherwise starts at 0.5.

        Args:
            repo_id: Repository identifier
            code_pattern: Code pattern being constrained
            embedding: Vector embedding

        Returns:
            Initial confidence score (0.5-0.7)
        """
        try:
            # Check for similar existing constraints (lower threshold)
            similar = self.check_suppressions(
                repo_id=repo_id,
                embedding=embedding,
                threshold=0.7,  # Lower threshold for similarity check
            )

            if similar:
                # Similar patterns exist, start with higher confidence
                max_confidence = max(c.confidence_score for c in similar)
                return min(0.7, max_confidence + 0.1)

            # No similar patterns, start at base confidence
            return 0.5

        except Exception:
            # On error, return base confidence
            return 0.5

    def _get_confidence_level(self, confidence_score: float) -> str:
        """
        Convert confidence score to categorical level for metrics.

        Args:
            confidence_score: Confidence score (0.0-1.0)

        Returns:
            Confidence level string
        """
        if confidence_score >= 0.8:
            return "high"
        elif confidence_score >= 0.6:
            return "medium"
        else:
            return "low"


# =============================================================================
# Module Exports
# =============================================================================
__all__ = ["ConstraintRepository"]
