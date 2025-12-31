"""
Copilot AI implementation for code review.

This module provides integration with GitHub Copilot's API for AI-powered
code review functionality.
"""

import os
import time
import uuid
from dotenv import load_dotenv, set_key
import requests
from codereview.ai import AI
from loguru import logger
from utils.prompt_loader import load_prompt
from utils.config import Config


class Copilot(AI):
    """
    GitHub Copilot AI provider for code review.

    This class handles authentication with Copilot API and performs
    code review using AI models.
    """

    def __init__(self, config: Config):
        """
        Initialize Copilot with configuration.

        Args:
            config: Config instance with LLM settings

        Raises:
            ValueError: If no LLM authentication method is available
        """
        if not config.LLM_API_KEY:
            raise ValueError("LLM_API_KEY is required")

        self.config = config
        self.api_key = config.LLM_API_KEY
        self.base_url = config.LLM_BASE_URL or "https://api.cocopilot.org"
        self.model = config.LLM_MODEL
        self.access_token = None

        # Try to get access token if using Copilot
        if config.COPILOT_TOKEN:
            self.access_token = self.get_access_token()

    def code_review(self, diff_content: str, model: str | None = None) -> str:
        """
        Perform code review using AI.

        Args:
            diff_content: The content of the code diff
            model: Optional model override (uses Config.LLM_MODEL if not provided)

        Returns:
            str: The AI code review response
        """
        model = model or self.model
        request_id = str(uuid.uuid4())
        start_time = time.time()

        try:
            # Load system prompt from file
            context = {
                "locale": self.config.LLM_LOCALE,
                "input-focus": "general best practices",
                "model": model,
            }
            system_prompt = load_prompt("code-review-pr.md", context)

            # Construct API request
            # Handle various base_url formats:
            # - https://api.openai.com -> add /v1/chat/completions
            # - https://api.openai.com/v1 -> add /chat/completions
            # - https://api.openai.com/v1/chat/completions -> use as is
            base = self.base_url.rstrip("/")

            if base.endswith("/chat/completions"):
                # Full endpoint already specified
                url = base
            elif base.endswith("/v1"):
                # Version specified, append chat/completions
                url = f"{base}/chat/completions"
            elif "/v1/" in base:
                # Base already has /v1/ in it, append chat/completions
                url = f"{base}/chat/completions"
            else:
                # Default to OpenAI-compatible endpoint
                url = f"{base}/v1/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "editor-version": "vscode/1.91.0",
                "editor-plugin-version": "copilot-chat/0.16.1",
            }

            data = {
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": f"{diff_content} Code review",
                    },
                ],
                "model": model,
                "max_tokens": 4096,
                "temperature": 0.1,
                "top_p": 1,
                "n": 1,
                "stream": False,
            }

            # Send request with 60-second timeout
            response = requests.post(url, headers=headers, json=data, timeout=60)

            latency_ms = int((time.time() - start_time) * 1000)

            if response.status_code == 401:
                # Token expired, try to renew
                if self.config.COPILOT_TOKEN:
                    new_token = self.get_access_token(renew=True)
                    self.api_key = new_token
                    return self.code_review(diff_content, model)
                else:
                    logger.bind(request_id=request_id, latency_ms=latency_ms, status="auth_error").error(
                        "Authentication failed"
                    )
                    return "Error: Authentication failed"

            if response.status_code == 200:
                result = response.json()["choices"][0]["message"]["content"]
                logger.bind(request_id=request_id, latency_ms=latency_ms, status="success").info(
                    "LLM request completed"
                )
                return result
            else:
                logger.bind(request_id=request_id, latency_ms=latency_ms, status="error").error(
                    f"LLM request failed: {response.text}"
                )
                return f"Error: {response.text}"

        except requests.Timeout:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.bind(request_id=request_id, latency_ms=latency_ms, status="timeout").warning(
                "LLM request timed out after 60 seconds"
            )
            return "Error: Request timed out after 60 seconds"
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.bind(request_id=request_id, latency_ms=latency_ms, status="error").error(
                f"LLM request error: {e}"
            )
            return f"Error: {str(e)}"

    def get_access_token(self, renew: bool = False) -> str:
        """
        Get or renew Copilot access token.

        Args:
            renew: If True, force token renewal

        Returns:
            str: The access token

        Raises:
            Exception: If token retrieval fails
        """
        if not renew:
            load_dotenv()
            existing_key = os.getenv("OPENAI_KEY")
            if existing_key:
                logger.info(f"Using existing OpenAI key")
                return existing_key

        endpoint = f"{self.base_url}/copilot_internal/v2/token"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"token {self.config.COPILOT_TOKEN}",
            "editor-version": "vscode/1.91.0",
            "editor-plugin-version": "copilot-chat/0.16.1",
        }
        response = requests.get(endpoint, headers=headers)
        if response.status_code == 200:
            token = response.json()["token"]
            set_key(".env", "OPENAI_KEY", token)
            logger.success(f"Updated OpenAI key")
            return token
        else:
            logger.error(f"Failed to get OpenAI key: {response.text}")
            raise Exception("Failed to get OpenAI key")

    @property
    def banner(self) -> str:
        """Returns the attribution banner for Copilot."""
        return "## Power by \n ![GitHub_Copilot_logo](/attachments/c99d46b9-d26f-4859-ad4f-d77650b27f8e)"
