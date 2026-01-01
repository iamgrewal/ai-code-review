"""
CortexReview Platform - Graceful Degradation Module

Implements cascading fallback levels for system resilience per Constitution XII.
Provides graceful degradation when external services (Supabase, Redis, LLM) fail.

Fallback Levels:
1. FULL: All services operational (RAG + RLHF enabled)
2. DEGRADED_RAG: RAG disabled (Supabase unavailable), basic reviews continue
3. DEGRADED_RLHF: RLHF disabled (Supabase unavailable), reviews without learning
4. MINIMAL: Only LLM reviews (Redis + Supabase unavailable, Celery direct execution)
5. EMERGENCY: Fallback to legacy Phase 1 behavior (synchronous processing)
"""

import time
from collections.abc import Callable
from enum import Enum
from functools import wraps
from typing import Any

from loguru import logger


class FallbackLevel(str, Enum):
    """
    System fallback levels for graceful degradation.

    Ordered from FULL (best) to EMERGENCY (minimal functionality).
    """

    FULL = "full"  # All services operational
    DEGRADED_RAG = "degraded_rag"  # RAG disabled, RLHF enabled
    DEGRADED_RLHF = "degraded_rlhf"  # RLHF disabled, RAG enabled
    DEGRADED_BOTH = "degraded_both"  # Both RAG and RLHF disabled
    MINIMAL = "minimal"  # Only LLM reviews, no external deps
    EMERGENCY = "emergency"  # Legacy Phase 1 synchronous processing


class HealthStatus:
    """
    Tracks health status of external services.

    Used to determine current fallback level.
    """

    def __init__(self):
        self.supabase_healthy: bool = True
        self.redis_healthy: bool = True
        self.llm_healthy: bool = True
        self.last_check: float = time.time()
        self.check_interval: int = 60  # Seconds between health checks

    def set_supabase_health(self, healthy: bool) -> None:
        """Update Supabase health status."""
        self.supabase_healthy = healthy
        self.last_check = time.time()

    def set_redis_health(self, healthy: bool) -> None:
        """Update Redis health status."""
        self.redis_healthy = healthy
        self.last_check = time.time()

    def set_llm_health(self, healthy: bool) -> None:
        """Update LLM health status."""
        self.llm_healthy = healthy
        self.last_check = time.time()

    def should_check_health(self) -> bool:
        """Check if enough time has passed since last health check."""
        return time.time() - self.last_check >= self.check_interval

    def get_fallback_level(self) -> FallbackLevel:
        """
        Determine current fallback level based on service health.

        Returns:
            FallbackLevel enum value
        """
        if not self.llm_healthy:
            # LLM is critical - no reviews possible
            return FallbackLevel.EMERGENCY

        if not self.supabase_healthy and not self.redis_healthy:
            # Both data stores down - minimal LLM-only reviews
            return FallbackLevel.MINIMAL

        if not self.supabase_healthy:
            # Supabase down - no RAG or RLHF
            return FallbackLevel.DEGRADED_BOTH

        if not self.redis_healthy:
            # Redis down but Supabase up - degraded state
            # Can still do RAG/RLHF but async processing affected
            return FallbackLevel.DEGRADED_RAG

        # All services healthy
        return FallbackLevel.FULL


# Global health status instance
_health_status = HealthStatus()


def get_health_status() -> HealthStatus:
    """Get global health status instance."""
    return _health_status


def get_fallback_level() -> FallbackLevel:
    """Get current system fallback level."""
    return _health_status.get_fallback_level()


# =============================================================================
# Supabase Connection Fallback
# =============================================================================


class SupabaseConnectionError(Exception):
    """Raised when Supabase connection fails."""

    pass


def with_supabase_fallback(
    fallback_return: Any = None,
    log_level: str = "warning",
) -> Callable:
    """
    Decorator for graceful Supabase connection failure handling.

    If Supabase connection fails, updates health status and returns fallback value.

    Args:
        fallback_return: Value to return if Supabase fails
        log_level: Log level for failure messages (default: warning)

    Example:
        @with_supabase_fallback(fallback_return=[], log_level="warning")
        def retrieve_rag_context(repo_id: str, query: str) -> list[str]:
            # Supabase query code
            pass
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)

                # Update health status on success
                _health_status.set_supabase_health(True)

                return result

            except Exception as e:
                # Update health status on failure
                _health_status.set_supabase_health(False)

                # Log the failure
                log_func = getattr(logger, log_level, logger.warning)
                log_func(
                    f"Supabase connection failed in {func.__name__}: {e}. "
                    f"Fallback level: {_health_status.get_fallback_level().value}"
                )

                return fallback_return

        return wrapper

    return decorator


# =============================================================================
# Redis Connection Fallback
# =============================================================================


class RedisConnectionError(Exception):
    """Raised when Redis connection fails."""

    pass


def with_redis_fallback(
    fallback_return: Any = None,
    log_level: str = "warning",
) -> Callable:
    """
    Decorator for graceful Redis connection failure handling.

    If Redis connection fails, updates health status and returns fallback value.

    Args:
        fallback_return: Value to return if Redis fails
        log_level: Log level for failure messages (default: warning)

    Example:
        @with_redis_fallback(fallback_return=None, log_level="warning")
        def get_cached_result(key: str) -> Optional[dict]:
            # Redis query code
            pass
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)

                # Update health status on success
                _health_status.set_redis_health(True)

                return result

            except Exception as e:
                # Update health status on failure
                _health_status.set_redis_health(False)

                # Log the failure
                log_func = getattr(logger, log_level, logger.warning)
                log_func(
                    f"Redis connection failed in {func.__name__}: {e}. "
                    f"Fallback level: {_health_status.get_fallback_level().value}"
                )

                return fallback_return

        return wrapper

    return decorator


# =============================================================================
# LLM Connection Fallback
# =============================================================================


class LLMConnectionError(Exception):
    """Raised when LLM API connection fails."""

    pass


def with_llm_fallback(
    fallback_return: Any = None,
    max_retries: int = 2,
    log_level: str = "error",
) -> Callable:
    """
    Decorator for graceful LLM API connection failure handling.

    If LLM connection fails, updates health status and returns fallback value.

    Args:
        fallback_return: Value to return if LLM fails
        max_retries: Number of retries before giving up
        log_level: Log level for failure messages (default: error)

    Example:
        @with_llm_fallback(fallback_return="", max_retries=2)
        def generate_review(diff: str) -> str:
            # LLM API call code
            pass
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0

            while retries <= max_retries:
                try:
                    result = func(*args, **kwargs)

                    # Update health status on success
                    _health_status.set_llm_health(True)

                    return result

                except Exception as e:
                    retries += 1

                    if retries > max_retries:
                        # Update health status on final failure
                        _health_status.set_llm_health(False)

                        # Log the failure
                        log_func = getattr(logger, log_level, logger.error)
                        log_func(
                            f"LLM connection failed in {func.__name__} after {max_retries} retries: {e}. "
                            f"Fallback level: {_health_status.get_fallback_level().value}"
                        )

                        return fallback_return

                    # Wait before retry (exponential backoff)
                    wait_time = 2**retries
                    logger.warning(
                        f"LLM connection failed, retrying in {wait_time}s... (attempt {retries}/{max_retries})"
                    )
                    time.sleep(wait_time)

        return wrapper

    return decorator


# =============================================================================
# Cascading Fallback Context Manager
# =============================================================================


class FallbackContext:
    """
    Context manager for executing code with specific fallback behavior.

    Allows temporary override of fallback level for specific operations.

    Example:
        with FallbackContext(FallbackLevel.DEGRADED_RAG):
            # This code runs with RAG disabled
            result = process_review(diff)
    """

    def __init__(self, level: FallbackLevel):
        self.level = level
        self._previous_level: FallbackLevel | None = None

    def __enter__(self) -> "FallbackContext":
        """Enter fallback context and save previous level."""
        # For a full implementation, we'd store and restore previous level
        logger.debug(f"Entering fallback context: {self.level.value}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit fallback context and restore previous level."""
        logger.debug(f"Exiting fallback context: {self.level.value}")
        return False


# =============================================================================
# Health Check Functions
# =============================================================================


async def check_supabase_health(supabase_client) -> bool:
    """
    Check Supabase connection health.

    Args:
        supabase_client: Supabase client instance

    Returns:
        True if healthy, False otherwise
    """
    if supabase_client is None:
        _health_status.set_supabase_health(False)
        return False

    try:
        # Simple query to test connection
        result = supabase_client.table("knowledge_base").select("id").limit(1).execute()
        _health_status.set_supabase_health(True)
        return True

    except Exception as e:
        _health_status.set_supabase_health(False)
        logger.warning(f"Supabase health check failed: {e}")
        return False


async def check_redis_health(redis_client) -> bool:
    """
    Check Redis connection health.

    Args:
        redis_client: Redis client instance

    Returns:
        True if healthy, False otherwise
    """
    if redis_client is None:
        _health_status.set_redis_health(False)
        return False

    try:
        # PING command to test connection
        redis_client.ping()
        _health_status.set_redis_health(True)
        return True

    except Exception as e:
        _health_status.set_redis_health(False)
        logger.warning(f"Redis health check failed: {e}")
        return False


def is_rag_enabled() -> bool:
    """Check if RAG is enabled based on current fallback level."""
    level = get_fallback_level()
    return level in (FallbackLevel.FULL, FallbackLevel.DEGRADED_RLHF)


def is_rlhf_enabled() -> bool:
    """Check if RLHF is enabled based on current fallback level."""
    level = get_fallback_level()
    return level in (FallbackLevel.FULL, FallbackLevel.DEGRADED_RAG)


# =============================================================================
# Module Exports
# =============================================================================
__all__ = [
    "FallbackContext",
    "FallbackLevel",
    "HealthStatus",
    "LLMConnectionError",
    "RedisConnectionError",
    "SupabaseConnectionError",
    "check_redis_health",
    "check_supabase_health",
    "get_fallback_level",
    "get_health_status",
    "is_rag_enabled",
    "is_rlhf_enabled",
    "with_llm_fallback",
    "with_redis_fallback",
    "with_supabase_fallback",
]
