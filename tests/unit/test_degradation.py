"""
Unit Tests for Graceful Degradation Module

Tests the fallback level system, health status tracking, and
graceful degradation decorators for Supabase, Redis, and LLM failures.
"""

from unittest.mock import patch

from utils.degradation import (
    FallbackContext,
    FallbackLevel,
    HealthStatus,
    get_health_status,
    is_rag_enabled,
    is_rlhf_enabled,
    with_llm_fallback,
    with_redis_fallback,
    with_supabase_fallback,
)


class TestFallbackLevel:
    """Test FallbackLevel enum values."""

    def test_fallback_level_values(self):
        """GIVEN the FallbackLevel enum WHEN accessing values THEN they match specification."""
        assert FallbackLevel.FULL.value == "full"
        assert FallbackLevel.DEGRADED_RAG.value == "degraded_rag"
        assert FallbackLevel.DEGRADED_RLHF.value == "degraded_rlhf"
        assert FallbackLevel.DEGRADED_BOTH.value == "degraded_both"
        assert FallbackLevel.MINIMAL.value == "minimal"
        assert FallbackLevel.EMERGENCY.value == "emergency"


class TestHealthStatus:
    """Test HealthStatus tracking."""

    def test_initial_state_all_healthy(self):
        """GIVEN a new HealthStatus WHEN created THEN all services are healthy."""
        status = HealthStatus()
        assert status.supabase_healthy is True
        assert status.redis_healthy is True
        assert status.llm_healthy is True

    def test_set_supabase_health(self):
        """GIVEN a HealthStatus WHEN setting Supabase health THEN value is updated."""
        status = HealthStatus()
        status.set_supabase_health(False)
        assert status.supabase_healthy is False
        status.set_supabase_health(True)
        assert status.supabase_healthy is True

    def test_set_redis_health(self):
        """GIVEN a HealthStatus WHEN setting Redis health THEN value is updated."""
        status = HealthStatus()
        status.set_redis_health(False)
        assert status.redis_healthy is False
        status.set_redis_health(True)
        assert status.redis_healthy is True

    def test_set_llm_health(self):
        """GIVEN a HealthStatus WHEN setting LLM health THEN value is updated."""
        status = HealthStatus()
        status.set_llm_health(False)
        assert status.llm_healthy is False
        status.set_llm_health(True)
        assert status.llm_healthy is True

    def test_get_fallback_level_full(self):
        """GIVEN all services healthy WHEN getting fallback level THEN return FULL."""
        status = HealthStatus()
        assert status.get_fallback_level() == FallbackLevel.FULL

    def test_get_fallback_level_emergency(self):
        """GIVEN LLM down WHEN getting fallback level THEN return EMERGENCY."""
        status = HealthStatus()
        status.set_llm_health(False)
        assert status.get_fallback_level() == FallbackLevel.EMERGENCY

    def test_get_fallback_level_minimal(self):
        """GIVEN Supabase and Redis down WHEN getting fallback level THEN return MINIMAL."""
        status = HealthStatus()
        status.set_supabase_health(False)
        status.set_redis_health(False)
        assert status.get_fallback_level() == FallbackLevel.MINIMAL

    def test_get_fallback_level_degraded_both(self):
        """GIVEN Supabase down WHEN getting fallback level THEN return DEGRADED_BOTH."""
        status = HealthStatus()
        status.set_supabase_health(False)
        assert status.get_fallback_level() == FallbackLevel.DEGRADED_BOTH


class TestSupabaseFallback:
    """Test Supabase connection fallback decorator."""

    def test_supabase_fallback_on_success(self):
        """GIVEN Supabase connection succeeds WHEN calling decorated function THEN return result."""

        @with_supabase_fallback(fallback_return=[])
        def query_data():
            return ["result"]

        result = query_data()
        assert result == ["result"]
        assert get_health_status().supabase_healthy is True

    def test_supabase_fallback_on_failure(self):
        """GIVEN Supabase connection fails WHEN calling decorated function THEN return fallback."""

        @with_supabase_fallback(fallback_return=[], log_level="warning")
        def query_data():
            raise Exception("Connection failed")

        result = query_data()
        assert result == []
        assert get_health_status().supabase_healthy is False

    def test_supabase_fallback_custom_return(self):
        """GIVEN Supabase connection fails WHEN calling with custom fallback THEN return custom value."""

        @with_supabase_fallback(fallback_return={"error": "degraded"})
        def query_data():
            raise Exception("Connection failed")

        result = query_data()
        assert result == {"error": "degraded"}


class TestRedisFallback:
    """Test Redis connection fallback decorator."""

    def test_redis_fallback_on_success(self):
        """GIVEN Redis connection succeeds WHEN calling decorated function THEN return result."""

        @with_redis_fallback(fallback_return=None)
        def get_cached():
            return {"cached": "value"}

        result = get_cached()
        assert result == {"cached": "value"}
        assert get_health_status().redis_healthy is True

    def test_redis_fallback_on_failure(self):
        """GIVEN Redis connection fails WHEN calling decorated function THEN return fallback."""

        @with_redis_fallback(fallback_return=None, log_level="warning")
        def get_cached():
            raise Exception("Connection failed")

        result = get_cached()
        assert result is None
        assert get_health_status().redis_healthy is False


class TestLLMFallback:
    """Test LLM connection fallback decorator."""

    def test_llm_fallback_on_success(self):
        """GIVEN LLM connection succeeds WHEN calling decorated function THEN return result."""

        @with_llm_fallback(fallback_return="", max_retries=2)
        def generate_review():
            return "Review comment"

        result = generate_review()
        assert result == "Review comment"
        assert get_health_status().llm_healthy is True

    def test_llm_fallback_on_failure_with_retries(self):
        """GIVEN LLM connection fails WHEN calling with retries THEN retry before fallback."""

        @with_llm_fallback(fallback_return="", max_retries=2)
        def generate_review():
            raise Exception("API error")

        result = generate_review()
        assert result == ""
        assert get_health_status().llm_healthy is False


class TestFallbackContext:
    """Test FallbackContext manager."""

    def test_fallback_context_enter_exit(self):
        """GIVEN a FallbackContext WHEN entering and exiting THEN log appropriately."""
        with patch("utils.degradation.logger"), FallbackContext(FallbackLevel.DEGRADED_RAG):
            pass


class TestUtilityFunctions:
    """Test utility functions."""

    def test_is_rag_enabled_full(self):
        """GIVEN fallback level is FULL WHEN checking RAG THEN return True."""
        from utils.degradation import _health_status

        # Reset to healthy state
        _health_status.supabase_healthy = True
        _health_status.redis_healthy = True
        _health_status.llm_healthy = True
        assert is_rag_enabled() is True

    def test_is_rag_enabled_degraded(self):
        """GIVEN fallback level is DEGRADED_RAG WHEN checking RAG THEN return False."""
        from utils.degradation import _health_status

        # Set Supabase as unhealthy
        _health_status.supabase_healthy = False
        _health_status.redis_healthy = True
        _health_status.llm_healthy = True
        assert is_rag_enabled() is False

    def test_is_rlhf_enabled_full(self):
        """GIVEN fallback level is FULL WHEN checking RLHF THEN return True."""
        from utils.degradation import _health_status

        # Reset to healthy state
        _health_status.supabase_healthy = True
        _health_status.redis_healthy = True
        _health_status.llm_healthy = True
        assert is_rlhf_enabled() is True

    def test_is_rlhf_enabled_degraded(self):
        """GIVEN fallback level is DEGRADED_BOTH WHEN checking RLHF THEN return False."""
        from utils.degradation import _health_status

        # Set Supabase as unhealthy (RLHF needs Supabase)
        _health_status.supabase_healthy = False
        _health_status.redis_healthy = True
        _health_status.llm_healthy = True
        assert is_rlhf_enabled() is False
