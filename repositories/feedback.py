"""
Feedback Repository for RLHF (Reinforcement Learning from Human Feedback).

Manages feedback records stored in Supabase, including:
- Creating feedback audit log entries
- Retrieving feedback history for analysis
- Computing false positive reduction metrics
- Tracking feedback patterns per repository
"""

import uuid
from datetime import datetime, timedelta

from loguru import logger
from supabase import Client

from models.feedback import FeedbackRecord
from models.platform import FeedbackAction


class FeedbackRepository:
    """
    Repository for managing feedback records in Supabase.

    Feedback records are audit log entries that track all user feedback
    for compliance, debugging, and learning loop analysis.
    """

    def __init__(self, supabase_client: Client):
        """
        Initialize feedback repository.

        Args:
            supabase_client: Supabase client instance
        """
        self.client = supabase_client

    def create_record(
        self,
        review_id: str,
        comment_id: str,
        user_id: str,
        action: FeedbackAction,
        reason: str,
        developer_comment: str,
        final_code_snapshot: str,
        trace_id: str,
    ) -> FeedbackRecord:
        """
        Create a new feedback record audit log entry.

        Args:
            review_id: Associated review ID
            comment_id: Review comment ID being feedback upon
            user_id: User identifier for audit trail
            action: Action taken (accepted/rejected/modified)
            reason: User-provided reason category
            developer_comment: Full developer explanation
            final_code_snapshot: Final code after user changes
            trace_id: Correlation ID for distributed tracing

        Returns:
            FeedbackRecord: Created feedback record

        Raises:
            Exception: If database operation fails
        """
        feedback_id = str(uuid.uuid4())

        record_data = {
            "id": feedback_id,
            "review_id": review_id,
            "comment_id": comment_id,
            "user_id": user_id,
            "action": action,
            "reason": reason,
            "developer_comment": developer_comment,
            "final_code_snapshot": final_code_snapshot,
            "trace_id": trace_id,
            "created_at": datetime.utcnow().isoformat(),
        }

        try:
            result = self.client.table("feedback_records").insert(record_data).execute()

            logger.bind(
                feedback_id=feedback_id,
                review_id=review_id,
                action=action,
                reason=reason,
            ).info("Created feedback record")

            return FeedbackRecord(**record_data)

        except Exception as e:
            logger.error(f"Failed to create feedback record: {e}")
            raise

    def get_by_review(self, review_id: str) -> list[FeedbackRecord]:
        """
        Retrieve all feedback records for a review.

        Args:
            review_id: Review identifier

        Returns:
            List of FeedbackRecord objects
        """
        try:
            result = (
                self.client.table("feedback_records")
                .select("*")
                .eq("review_id", review_id)
                .order("created_at", desc=False)
                .execute()
            )

            return [FeedbackRecord(**row) for row in result.data]

        except Exception as e:
            logger.error(f"Failed to get feedback for review {review_id}: {e}")
            return []

    def get_by_comment(self, comment_id: str) -> list[FeedbackRecord]:
        """
        Retrieve all feedback records for a specific comment.

        Args:
            comment_id: Comment identifier

        Returns:
            List of FeedbackRecord objects
        """
        try:
            result = (
                self.client.table("feedback_records")
                .select("*")
                .eq("comment_id", comment_id)
                .order("created_at", desc=False)
                .execute()
            )

            return [FeedbackRecord(**row) for row in result.data]

        except Exception as e:
            logger.error(f"Failed to get feedback for comment {comment_id}: {e}")
            return []

    def get_by_repository(
        self,
        repo_id: str,
        days_back: int = 30,
    ) -> list[FeedbackRecord]:
        """
        Retrieve feedback records for a repository within time window.

        Args:
            repo_id: Repository identifier (owner/repo)
            days_back: Number of days to look back (default 30)

        Returns:
            List of FeedbackRecord objects
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)

            # Parse review_id to extract repo_id if stored in metadata
            # Assuming review_id format includes repo_id or we have a join table
            result = (
                self.client.table("feedback_records")
                .select("*")
                .gte("created_at", cutoff_date.isoformat())
                .order("created_at", desc=False)
                .execute()
            )

            # Filter by repo_id from review_id (assuming format: "repo_id:timestamp")
            records = []
            for row in result.data:
                record = FeedbackRecord(**row)
                # Extract repo_id from review_id if formatted as "repo_id:uuid"
                record_repo_id = record.review_id.split(":")[0] if ":" in record.review_id else ""
                if record_repo_id == repo_id:
                    records.append(record)

            return records

        except Exception as e:
            logger.error(f"Failed to get feedback for repo {repo_id}: {e}")
            return []

    def get_feedback_stats(
        self,
        repo_id: str | None = None,
        days_back: int = 30,
    ) -> dict[str, int]:
        """
        Get feedback statistics for metrics and analysis.

        Args:
            repo_id: Repository identifier (optional, aggregates all if None)
            days_back: Number of days to look back (default 30)

        Returns:
            Dictionary with feedback counts by action type
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)

            query = (
                self.client.table("feedback_records")
                .select("action", count="exact")
                .gte("created_at", cutoff_date.isoformat())
            )

            if repo_id:
                # Filter by repo_id (assuming review_id contains repo_id)
                # This is a simplified approach; production might need proper join
                result = query.execute()
                # Filter in post-processing
                records = [
                    r for r in result.data if r.get("review_id", "").startswith(f"{repo_id}:")
                ]
            else:
                result = query.execute()
                records = result.data

            # Count by action type
            stats = {
                "accepted": 0,
                "rejected": 0,
                "modified": 0,
                "total": len(records),
            }

            for record in records:
                action = record.get("action", "")
                if action in stats:
                    stats[action] += 1

            return stats

        except Exception as e:
            logger.error(f"Failed to get feedback stats: {e}")
            return {"accepted": 0, "rejected": 0, "modified": 0, "total": 0}

    def calculate_false_positive_reduction(
        self,
        repo_id: str,
        days_back: int = 30,
    ) -> float:
        """
        Calculate false positive reduction ratio for metrics.

        Ratio = rejected_feedback / total_feedback
        Higher ratio indicates more false positives being suppressed.

        Args:
            repo_id: Repository identifier
            days_back: Number of days to look back (default 30)

        Returns:
            False positive reduction ratio (0.0-1.0)
        """
        stats = self.get_feedback_stats(repo_id=repo_id, days_back=days_back)

        total = stats["total"]
        if total == 0:
            return 0.0

        rejected = stats["rejected"]
        return round(rejected / total, 4)

    def get_recent_feedback(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[FeedbackRecord]:
        """
        Get recent feedback records across all repositories.

        Args:
            limit: Maximum number of records to return
            offset: Number of records to skip (pagination)

        Returns:
            List of FeedbackRecord objects
        """
        try:
            result = (
                self.client.table("feedback_records")
                .select("*")
                .order("created_at", desc=True)
                .range(offset, offset + limit - 1)
                .execute()
            )

            return [FeedbackRecord(**row) for row in result.data]

        except Exception as e:
            logger.error(f"Failed to get recent feedback: {e}")
            return []

    def get_feedback_by_action(
        self,
        action: FeedbackAction,
        days_back: int = 30,
    ) -> list[FeedbackRecord]:
        """
        Retrieve feedback records filtered by action type.

        Args:
            action: Action type to filter by (accepted/rejected/modified)
            days_back: Number of days to look back (default 30)

        Returns:
            List of FeedbackRecord objects
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)

            result = (
                self.client.table("feedback_records")
                .select("*")
                .eq("action", action)
                .gte("created_at", cutoff_date.isoformat())
                .order("created_at", desc=False)
                .execute()
            )

            return [FeedbackRecord(**row) for row in result.data]

        except Exception as e:
            logger.error(f"Failed to get feedback by action {action}: {e}")
            return []


# =============================================================================
# Module Exports
# =============================================================================
__all__ = ["FeedbackRepository"]
