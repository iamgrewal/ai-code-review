"""
CortexReview Platform - Configuration Management

Refactored to use pydantic-settings for type-safe environment variable loading
with Phase 2 variables for Celery, Supabase, and observability.
"""

import os

from loguru import logger
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Webhook(BaseSettings):
    """Configuration for optional notification webhooks."""

    url: str | None = None
    header_name: str | None = None
    header_value: str | None = None
    request_body: str | None = None

    @property
    def is_init(self) -> bool:
        """Returns True if both url and request_body are configured."""
        return bool(self.url and self.request_body)


class Config(BaseSettings):
    """
    Centralized configuration loader using pydantic-settings.

    Loads all environment variables from .env file and provides
    typed access throughout the application. Implements graceful
    degradation with fallback values for optional settings.
    """

    # -------------------------------------------------------------------------
    # Pydantic Settings Configuration
    # -------------------------------------------------------------------------
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",  # Enables nested models with __ separator
        extra="ignore",  # Ignore extra env vars
        case_sensitive=False,  # Allow case-insensitive env var matching
    )

    # -------------------------------------------------------------------------
    # Git Platform Configuration
    # -------------------------------------------------------------------------
    # Platform selection: github, gitea
    PLATFORM: str = Field(default="gitea")

    # Gitea Configuration
    GITEA_TOKEN: str = Field(..., description="Gitea API authentication token")
    GITEA_HOST: str = Field(..., description="Gitea server host (e.g., server:3000)")

    # GitHub Configuration
    GITHUB_TOKEN: str | None = Field(default=None, description="GitHub API token")

    # -------------------------------------------------------------------------
    # LLM Configuration
    # -------------------------------------------------------------------------
    # Primary LLM API key (highest priority)
    LLM_API_KEY: str | None = Field(default=None, description="Primary LLM API key")

    # Custom LLM endpoint URL
    LLM_BASE_URL: str | None = Field(
        default=None, description="Custom LLM endpoint URL (for local LLMs or enterprise proxies)"
    )

    # Model configuration
    LLM_MODEL: str = Field(default="gpt-4", description="Model identifier for LLM requests")
    LLM_LOCALE: str = Field(default="en_us", description="Response language locale")
    LLM_PROVIDER: str = Field(default="openai", description="Provider identifier for logging")

    # Embedding model for RAG
    EMBEDDING_MODEL: str = Field(
        default="text-embedding-3-small", description="Embedding model for RAG context retrieval"
    )

    # Legacy Compatibility (fallback)
    OPENAI_KEY: str | None = Field(default=None, description="Legacy OpenAI API key (deprecated)")
    COPILOT_TOKEN: str | None = Field(default=None, description="Legacy Copilot token")

    # -------------------------------------------------------------------------
    # Celery Configuration (Phase 2)
    # -------------------------------------------------------------------------
    CELERY_BROKER_URL: str = Field(
        default="redis://redis:6379/0", description="Celery broker URL (Redis connection string)"
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="redis://redis:6379/0",
        description="Celery result backend URL (Redis connection string)",
    )
    CELERY_WORKER_CONCURRENCY: int = Field(
        default=4, description="Number of Celery worker processes"
    )
    CELERY_TASK_TIME_LIMIT: int = Field(
        default=300, description="Celery task time limit in seconds"
    )

    # -------------------------------------------------------------------------
    # Supabase Configuration (Phase 2)
    # -------------------------------------------------------------------------
    SUPABASE_URL: str | None = Field(default=None, description="Supabase project URL")
    SUPABASE_SERVICE_KEY: str | None = Field(
        default=None, description="Supabase service role key for database operations"
    )
    SUPABASE_DB_URL: str | None = Field(
        default=None, description="Direct PostgreSQL connection string (for migrations/scripting)"
    )

    # -------------------------------------------------------------------------
    # Webhook Signature Verification (Phase 2)
    # -------------------------------------------------------------------------
    PLATFORM_GITHUB_WEBHOOK_SECRET: str | None = Field(
        default=None, description="GitHub webhook secret for HMAC-SHA256 signature verification"
    )
    PLATFORM_GITEA_WEBHOOK_SECRET: str | None = Field(
        default=None, description="Gitea webhook secret for HMAC-SHA256 signature verification"
    )
    PLATFORM_GITHUB_VERIFY_SIGNATURE: bool = Field(
        default=True, description="Enable GitHub webhook signature verification"
    )
    PLATFORM_GITEA_VERIFY_SIGNATURE: bool = Field(
        default=True, description="Enable Gitea webhook signature verification"
    )

    # -------------------------------------------------------------------------
    # RAG Configuration (Phase 2)
    # -------------------------------------------------------------------------
    RAG_ENABLED: bool = Field(default=True, description="Enable RAG context-aware reviews")
    RAG_THRESHOLD: float = Field(
        default=0.75, ge=0.0, le=1.0, description="RAG similarity threshold for context matching"
    )
    RAG_MATCH_COUNT_MIN: int = Field(
        default=3, ge=1, le=10, description="Minimum RAG match count for context retrieval"
    )
    RAG_MATCH_COUNT_MAX: int = Field(
        default=10, ge=1, le=50, description="Maximum RAG match count for context retrieval"
    )

    # -------------------------------------------------------------------------
    # RLHF Configuration (Phase 2)
    # -------------------------------------------------------------------------
    RLHF_ENABLED: bool = Field(default=True, description="Enable RLHF learning loop")
    RLHF_THRESHOLD: float = Field(
        default=0.8, ge=0.0, le=1.0, description="RLHF similarity threshold for constraint matching"
    )
    FEEDBACK_ENABLED: bool = Field(default=True, description="Enable feedback processing")
    CONSTRAINT_EXPIRATION_DAYS: int = Field(
        default=90, ge=1, le=365, description="Learned constraint expiration in days"
    )

    # -------------------------------------------------------------------------
    # Observability Configuration (Phase 2)
    # -------------------------------------------------------------------------
    ENABLE_PROMETHEUS: bool = Field(default=True, description="Enable Prometheus metrics endpoint")
    ENABLE_GRAFANA: bool = Field(default=True, description="Enable Grafana dashboards")
    LOG_LEVEL: str = Field(default="INFO", description="Application log level")

    # -------------------------------------------------------------------------
    # Application Settings
    # -------------------------------------------------------------------------
    IGNORED_FILE_SUFFIX: str = Field(
        default=".json,.md,.lock",
        description="Comma-separated file extensions to skip during code review",
    )

    # -------------------------------------------------------------------------
    # Optional Webhook (nested model)
    # -------------------------------------------------------------------------
    webhook: Webhook | None = Field(default=None, description="Notification webhook configuration")

    # -------------------------------------------------------------------------
    # Post-processing and Validation
    # -------------------------------------------------------------------------
    def __init__(self, **kwargs):
        """
        Initialize configuration and apply legacy compatibility transformations.

        Raises:
            ValueError: If required variables are missing or invalid
        """
        super().__init__(**kwargs)

        # Apply strict priority for LLM authentication
        # Priority: LLM_API_KEY > OPENAI_KEY > COPILOT_TOKEN
        if not self.LLM_API_KEY:
            if self.OPENAI_KEY:
                self.LLM_API_KEY = self.OPENAI_KEY
                logger.warning("OPENAI_KEY is deprecated, use LLM_API_KEY instead")
            elif self.COPILOT_TOKEN:
                self.LLM_API_KEY = self.COPILOT_TOKEN
                logger.warning("COPILOT_TOKEN is deprecated, use LLM_API_KEY instead")
            else:
                # No LLM auth method configured
                pass

        # Initialize webhook if URL provided
        if not self.webhook:
            webhook_url = kwargs.get("webhook_url") or os.getenv("WEBHOOK_URL")
            if webhook_url:
                self.webhook = Webhook(
                    url=webhook_url,
                    header_name=kwargs.get("webhook_header_name")
                    or os.getenv("WEBHOOK_HEADER_NAME"),
                    header_value=kwargs.get("webhook_header_value")
                    or os.getenv("WEBHOOK_HEADER_VALUE"),
                    request_body=kwargs.get("webhook_request_body")
                    or os.getenv("WEBHOOK_REQUEST_BODY"),
                )

                # Warn if webhook configuration is incomplete
                if not self.webhook.is_init:
                    logger.warning(
                        "Webhook configuration is incomplete. "
                        "Both WEBHOOK_URL and WEBHOOK_REQUEST_BODY are required."
                    )

        # Validate required configuration
        self._validate()

    @field_validator("PLATFORM")
    @classmethod
    def validate_platform(cls, v: str) -> str:
        """Validate platform is either github or gitea."""
        if v.lower() not in ("github", "gitea"):
            logger.warning(f"Invalid platform: {v}. Defaulting to 'gitea'")
            return "gitea"
        return v.lower()

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is a valid value."""
        valid_levels = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        if v.upper() not in valid_levels:
            logger.warning(f"Invalid log level: {v}. Defaulting to 'INFO'")
            return "INFO"
        return v.upper()

    def _validate(self) -> None:
        """Validate required configuration is present."""
        if not self.GITEA_TOKEN:
            raise ValueError("GITEA_TOKEN is required")

        if not self.GITEA_HOST:
            raise ValueError("GITEA_HOST is required")

        if not self.LLM_API_KEY:
            raise ValueError(
                "At least one LLM authentication method required: "
                "LLM_API_KEY (recommended), OPENAI_KEY, or COPILOT_TOKEN"
            )

        # Warn if Supabase not configured (required for RAG/RLHF)
        # Support both external Supabase Cloud and local Supabase deployments
        if self.RAG_ENABLED or self.RLHF_ENABLED:
            has_external_supabase = bool(self.SUPABASE_URL and self.SUPABASE_SERVICE_KEY)
            has_local_supabase = bool(self.SUPABASE_DB_URL)

            if not has_external_supabase and not has_local_supabase:
                logger.warning(
                    "Supabase configuration is missing. RAG and RLHF features will be disabled. "
                    "Configure SUPABASE_URL + SUPABASE_SERVICE_KEY for external Supabase Cloud, "
                    "or SUPABASE_DB_URL for local Supabase deployment."
                )
                self.RAG_ENABLED = False
                self.RLHF_ENABLED = False

    # -------------------------------------------------------------------------
    # Computed Properties
    # -------------------------------------------------------------------------
    @property
    def effective_llm_base_url(self) -> str:
        """Get the effective LLM base URL with fallback."""
        return self.LLM_BASE_URL or "https://api.openai.com/v1"

    @property
    def effective_llm_api_key(self) -> str | None:
        """Get the effective LLM API key after priority resolution."""
        return self.LLM_API_KEY
