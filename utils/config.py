import os
from dotenv import load_dotenv
from loguru import logger


class Webhook:
    """Configuration for optional notification webhooks."""

    def __init__(self) -> None:
        self.url: str | None = None
        self.header_name: str | None = None
        self.header_value: str | None = None
        self.request_body: str | None = None

    @property
    def is_init(self) -> bool:
        """Returns True if both url and request_body are configured."""
        return bool(self.url and self.request_body)


class Config:
    """
    Centralized configuration loader using python-dotenv.

    Loads all environment variables from .env file and provides
    typed access throughout the application. Implements graceful
    degradation with fallback values for optional settings.
    """

    # LLM Configuration
    LLM_PROVIDER: str
    LLM_API_KEY: str | None
    LLM_BASE_URL: str | None
    LLM_MODEL: str

    # Legacy Compatibility
    COPILOT_TOKEN: str | None
    OPENAI_KEY: str | None

    # Gitea Configuration
    GITEA_HOST: str
    GITEA_TOKEN: str

    # Application Settings
    IGNORED_FILE_SUFFIX: str

    # Optional Webhook
    webhook: Webhook | None

    def __init__(self, config_file: str | None = None) -> None:
        """
        Load configuration from .env file.

        Args:
            config_file: Optional path to custom .env file

        Raises:
            ValueError: If required variables (GITEA_TOKEN, GITEA_HOST) are missing
                        or if no LLM authentication method is configured.
        """
        load_dotenv(config_file)

        # Gitea Configuration (Required)
        self.GITEA_TOKEN = os.getenv("GITEA_TOKEN")
        self.GITEA_HOST = os.getenv("GITEA_HOST")

        # LLM Configuration with strict priority
        # Priority: LLM_API_KEY > OPENAI_KEY > COPILOT_TOKEN
        self.LLM_API_KEY = os.getenv("LLM_API_KEY")
        self.OPENAI_KEY = os.getenv("OPENAI_KEY")
        self.COPILOT_TOKEN = os.getenv("COPILOT_TOKEN")

        # Apply strict priority for LLM authentication
        if self.LLM_API_KEY:
            # Use LLM_API_KEY, ignore legacy keys
            pass
        elif self.OPENAI_KEY:
            # Use OPENAI_KEY as fallback
            self.LLM_API_KEY = self.OPENAI_KEY
            logger.warning("OPENAI_KEY is deprecated, use LLM_API_KEY instead")
        elif self.COPILOT_TOKEN:
            # Use COPILOT_TOKEN as fallback
            self.LLM_API_KEY = self.COPILOT_TOKEN
        else:
            # No LLM auth method configured
            self.LLM_API_KEY = None

        self.LLM_BASE_URL = os.getenv("LLM_BASE_URL")
        self.LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4")
        self.LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")

        # Application Settings
        self.IGNORED_FILE_SUFFIX = os.getenv("IGNORED_FILE_SUFFIX", ".json,.md,.lock")

        # Optional Webhook
        webhook_url = os.getenv("WEBHOOK_URL")
        if webhook_url:
            self.webhook = Webhook()
            self.webhook.url = webhook_url
            self.webhook.header_name = os.getenv("WEBHOOK_HEADER_NAME")
            self.webhook.header_value = os.getenv("WEBHOOK_HEADER_VALUE")
            self.webhook.request_body = os.getenv("WEBHOOK_REQUEST_BODY")
        else:
            self.webhook = None

        self._validate()

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
