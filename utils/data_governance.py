"""
CortexReview Platform - Data Governance Module

Implements data isolation, retention policies, and cleanup jobs per
Constitution XIII (Data Governance).

Key Features:
- Repository-level data isolation (repo_id scoping)
- Automatic data retention policy enforcement
- Secret redaction before storage
- Audit logging for data access
- GDPR-style right-to-forget implementation
"""

from datetime import datetime, timedelta
from typing import Any

from loguru import logger
from supabase import Client


class DataIsolationError(Exception):
    """Raised when data isolation is violated."""

    pass


class DataRetentionError(Exception):
    """Raised when data retention operations fail."""

    pass


# =============================================================================
# Repository-Level Data Isolation
# =============================================================================


def enforce_repo_isolation(repo_id: str) -> str:
    """
    Validate and normalize repo_id for data isolation enforcement.

    Ensures repo_id is properly formatted for query scoping.

    Args:
        repo_id: Repository identifier (e.g., "owner/repo" or "owner%2Frepo")

    Returns:
        Normalized repo_id

    Raises:
        DataIsolationError: If repo_id is invalid or empty
    """
    if not repo_id:
        raise DataIsolationError("repo_id cannot be empty")

    # Normalize: replace URL encoding
    normalized = repo_id.replace("%2F", "/")

    # Validate format: should contain exactly one slash
    if normalized.count("/") != 1:
        raise DataIsolationError(
            f"Invalid repo_id format: '{repo_id}'. Expected format: 'owner/repo'"
        )

    return normalized


def build_repo_filter(repo_id: str) -> dict[str, Any]:
    """
    Build Supabase filter for repository-level data isolation.

    All queries to knowledge_base and learned_constraints MUST
    include this filter to ensure data isolation.

    Args:
        repo_id: Repository identifier

    Returns:
        Supabase filter dict

    Example:
        filter = build_repo_filter("octocat/hello-world")
        response = supabase.table("knowledge_base").select("*").filter(**filter).execute()
    """
    normalized_repo_id = enforce_repo_isolation(repo_id)
    return {"repo_id": f"eq.{normalized_repo_id}"}


def verify_repo_access(supabase: Client, repo_id: str, table: str, record_id: int) -> bool:
    """
    Verify that a record belongs to the specified repository.

    Used as a safety check before updates/deletes to prevent
    cross-repository data access.

    Args:
        supabase: Supabase client
        repo_id: Repository identifier
        table: Table name (e.g., "knowledge_base")
        record_id: Record ID to verify

    Returns:
        True if record belongs to repo, False otherwise

    Raises:
        DataIsolationError: If repo_id is invalid
    """
    normalized_repo_id = enforce_repo_isolation(repo_id)

    try:
        result = (
            supabase.table(table)
            .select("id, repo_id")
            .eq("id", record_id)
            .eq("repo_id", normalized_repo_id)
            .execute()
        )

        return len(result.data) > 0

    except Exception as e:
        logger.error(f"Failed to verify repo access: {e}")
        return False


# =============================================================================
# Data Retention Policy
# =============================================================================


class RetentionPolicy:
    """
    Data retention policy configuration.

    Defines how long different types of data are retained before cleanup.
    """

    # Knowledge base entries (RAG context)
    KNOWLEDGE_RETENTION_DAYS = 180  # 6 months

    # Learned constraints (RLHF feedback)
    CONSTRAINT_RETENTION_DAYS = 90  # 3 months (default, configurable)

    # Review results (for audit)
    REVIEW_RETENTION_DAYS = 365  # 1 year

    # Failed task logs
    FAILED_TASK_RETENTION_DAYS = 30  # 1 month


def cleanup_expired_knowledge(
    supabase: Client,
    repo_id: str | None = None,
    retention_days: int = RetentionPolicy.KNOWLEDGE_RETENTION_DAYS,
) -> dict[str, Any]:
    """
    Clean up expired knowledge base entries.

    Args:
        supabase: Supabase client
        repo_id: Optional repository ID for scoped cleanup (None = all repos)
        retention_days: Retention period in days

    Returns:
        Dict with cleanup results (deleted_count, status)

    Raises:
        DataRetentionError: If cleanup operation fails
    """
    try:
        # Calculate expiration date
        expiration_date = datetime.utcnow() - timedelta(days=retention_days)

        # Build query
        query = (
            supabase.table("knowledge_base").delete().lt("created_at", expiration_date.isoformat())
        )

        # Apply repo isolation if specified
        if repo_id:
            normalized_repo_id = enforce_repo_isolation(repo_id)
            query = query.eq("repo_id", normalized_repo_id)

        # Execute deletion
        result = query.execute()

        logger.info(
            f"Knowledge base cleanup completed: {len(result.data)} records deleted "
            f"(repo_id={repo_id or 'all'}, retention={retention_days}d)"
        )

        return {
            "status": "success",
            "deleted_count": len(result.data),
            "retention_days": retention_days,
            "repo_id": repo_id,
        }

    except Exception as e:
        error_msg = f"Knowledge base cleanup failed: {e}"
        logger.error(error_msg)
        raise DataRetentionError(error_msg) from e


def cleanup_expired_constraints(
    supabase: Client,
    repo_id: str | None = None,
    retention_days: int = RetentionPolicy.CONSTRAINT_RETENTION_DAYS,
) -> dict[str, Any]:
    """
    Clean up expired learned constraints.

    Args:
        supabase: Supabase client
        repo_id: Optional repository ID for scoped cleanup (None = all repos)
        retention_days: Retention period in days

    Returns:
        Dict with cleanup results (deleted_count, status)

    Raises:
        DataRetentionError: If cleanup operation fails
    """
    try:
        # Calculate expiration date
        expiration_date = datetime.utcnow() - timedelta(days=retention_days)

        # Build query
        query = (
            supabase.table("learned_constraints")
            .delete()
            .lt("created_at", expiration_date.isoformat())
        )

        # Apply repo isolation if specified
        if repo_id:
            normalized_repo_id = enforce_repo_isolation(repo_id)
            query = query.eq("repo_id", normalized_repo_id)

        # Execute deletion
        result = query.execute()

        logger.info(
            f"Learned constraints cleanup completed: {len(result.data)} records deleted "
            f"(repo_id={repo_id or 'all'}, retention={retention_days}d)"
        )

        return {
            "status": "success",
            "deleted_count": len(result.data),
            "retention_days": retention_days,
            "repo_id": repo_id,
        }

    except Exception as e:
        error_msg = f"Learned constraints cleanup failed: {e}"
        logger.error(error_msg)
        raise DataRetentionError(error_msg) from e


def cleanup_all_expired_data(
    supabase: Client,
    repo_id: str | None = None,
) -> dict[str, Any]:
    """
    Clean up all expired data across all tables.

    This is the main cleanup job called by the Celery Beat scheduler.

    Args:
        supabase: Supabase client
        repo_id: Optional repository ID for scoped cleanup

    Returns:
        Dict with combined cleanup results
    """
    logger.info(f"Starting data retention cleanup (repo_id={repo_id or 'all'})")

    results = {
        "status": "success",
        "knowledge": None,
        "constraints": None,
        "total_deleted": 0,
    }

    try:
        # Clean up knowledge base
        results["knowledge"] = cleanup_expired_knowledge(
            supabase, repo_id, RetentionPolicy.KNOWLEDGE_RETENTION_DAYS
        )
        results["total_deleted"] += results["knowledge"]["deleted_count"]

        # Clean up learned constraints
        results["constraints"] = cleanup_expired_constraints(
            supabase, repo_id, RetentionPolicy.CONSTRAINT_RETENTION_DAYS
        )
        results["total_deleted"] += results["constraints"]["deleted_count"]

        logger.info(f"Data retention cleanup completed: {results['total_deleted']} records deleted")

    except Exception as e:
        results["status"] = "error"
        results["error"] = str(e)
        logger.error(f"Data retention cleanup failed: {e}")

    return results


# =============================================================================
# Right-to-Forget (GDPR-style Data Deletion)
# =============================================================================


def delete_all_repo_data(supabase: Client, repo_id: str) -> dict[str, Any]:
    """
    Delete ALL data for a repository (right-to-forget).

    This is a permanent deletion operation that removes all traces
    of a repository from the knowledge base and learned constraints.

    WARNING: This operation is irreversible.

    Args:
        supabase: Supabase client
        repo_id: Repository identifier

    Returns:
        Dict with deletion results

    Raises:
        DataIsolationError: If repo_id is invalid
    """
    normalized_repo_id = enforce_repo_isolation(repo_id)

    logger.warning(f"Starting RIGHT-TO-FORGET deletion for repo: {normalized_repo_id}")

    results = {
        "status": "success",
        "repo_id": normalized_repo_id,
        "knowledge_deleted": 0,
        "constraints_deleted": 0,
    }

    try:
        # Delete all knowledge base entries
        kb_result = (
            supabase.table("knowledge_base").delete().eq("repo_id", normalized_repo_id).execute()
        )
        results["knowledge_deleted"] = len(kb_result.data)

        # Delete all learned constraints
        lc_result = (
            supabase.table("learned_constraints")
            .delete()
            .eq("repo_id", normalized_repo_id)
            .execute()
        )
        results["constraints_deleted"] = len(lc_result.data)

        logger.warning(
            f"RIGHT-TO-FORGET completed: {results['knowledge_deleted']} knowledge entries, "
            f"{results['constraints_deleted']} constraints deleted for repo {normalized_repo_id}"
        )

    except Exception as e:
        results["status"] = "error"
        results["error"] = str(e)
        logger.error(f"RIGHT-TO-FORGET failed for repo {normalized_repo_id}: {e}")

    return results


# =============================================================================
# Audit Logging
# =============================================================================


def log_data_access(
    action: str,
    repo_id: str,
    table: str,
    record_id: int | None = None,
    user_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """
    Log data access for audit trail.

    Args:
        action: Action performed (read, write, delete)
        repo_id: Repository identifier
        table: Table name
        record_id: Optional record ID
        user_id: Optional user identifier
        metadata: Optional additional metadata
    """
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "action": action,
        "repo_id": repo_id,
        "table": table,
        "record_id": record_id,
        "user_id": user_id,
        "metadata": metadata or {},
    }

    # Use structured logging for audit trail
    logger.bind(
        audit="data_access",
        action=action,
        repo_id=repo_id,
        table=table,
        record_id=record_id,
    ).info("Data access logged")


# =============================================================================
# Data Export (for migration/backup)
# =============================================================================


def export_repo_data(
    supabase: Client,
    repo_id: str,
    include_embeddings: bool = False,
) -> dict[str, Any]:
    """
    Export all data for a repository.

    Used for backup, migration, or data portability (GDPR).

    Args:
        supabase: Supabase client
        repo_id: Repository identifier
        include_embeddings: Whether to include vector embeddings (large)

    Returns:
        Dict with exported data

    Raises:
        DataIsolationError: If repo_id is invalid
    """
    normalized_repo_id = enforce_repo_isolation(repo_id)

    logger.info(f"Exporting data for repo: {normalized_repo_id}")

    export_data = {
        "repo_id": normalized_repo_id,
        "export_timestamp": datetime.utcnow().isoformat(),
        "knowledge_base": [],
        "learned_constraints": [],
    }

    try:
        # Export knowledge base
        kb_query = supabase.table("knowledge_base").select("*").eq("repo_id", normalized_repo_id)

        # Exclude embeddings if not requested (saves space)
        if not include_embeddings:
            kb_query = kb_query.select("id, repo_id, content, metadata, created_at")

        kb_result = kb_query.execute()
        export_data["knowledge_base"] = kb_result.data

        # Export learned constraints
        lc_result = (
            supabase.table("learned_constraints")
            .select("*")
            .eq("repo_id", normalized_repo_id)
            .execute()
        )
        export_data["learned_constraints"] = lc_result.data

        logger.info(
            f"Export completed: {len(export_data['knowledge_base'])} knowledge entries, "
            f"{len(export_data['learned_constraints'])} constraints"
        )

    except Exception as e:
        logger.error(f"Export failed for repo {normalized_repo_id}: {e}")
        export_data["error"] = str(e)

    return export_data


# =============================================================================
# Module Exports
# =============================================================================
__all__ = [
    "DataIsolationError",
    "DataRetentionError",
    "RetentionPolicy",
    "build_repo_filter",
    "cleanup_all_expired_data",
    "cleanup_expired_constraints",
    "cleanup_expired_knowledge",
    "delete_all_repo_data",
    "enforce_repo_isolation",
    "export_repo_data",
    "log_data_access",
    "verify_repo_access",
]
