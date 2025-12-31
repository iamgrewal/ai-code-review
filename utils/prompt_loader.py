"""
Prompt loading utilities.

This module provides functionality for loading AI system prompts from Markdown
files with YAML front matter support and variable substitution.
"""

import os
import re
from loguru import logger


# Default fallback prompt when no prompt file is available
_FALLBACK_PROMPT = """You are a senior code reviewer. Analyze the provided code diff for:
- Security vulnerabilities
- Performance issues
- Code style and readability
- Potential bugs

Provide constructive feedback in ${locale}."""


def _strip_yaml_front_matter(content: str) -> tuple[str, dict]:
    """
    Remove YAML front matter from markdown content.

    Args:
        content: Raw file content including YAML markers

    Returns:
        Tuple of (content_without_yaml, parsed_metadata_dict)

    Algorithm:
        1. If content starts with "---":
        2. Split on "---" and find the third section (after second marker)
        3. If less than 3 sections, remove first "---" prefix
        4. Strip leading/trailing whitespace
    """
    if not content.startswith("---"):
        return content, {}

    try:
        parts = content.split("---", 2)
        if len(parts) == 3:
            # Has both opening and closing markers
            yaml_content = parts[1].strip()
            markdown_content = parts[2].strip()

            # Parse YAML metadata (imported here to avoid dependency if not needed)
            try:
                import yaml
                metadata = yaml.safe_load(yaml_content) or {}
            except Exception:
                logger.warning("Failed to parse YAML front matter, treating as plain text")
                metadata = {}

            return markdown_content, metadata
        else:
            # Malformed - fallback to naive strip
            return content.replace("---", "", 1), {}
    except Exception as e:
        logger.warning(f"Error stripping YAML front matter: {e}")
        return content, {}


def _substitute_variables(content: str, context: dict[str, str]) -> str:
    """
    Replace ${variable} placeholders with actual values.

    Args:
        content: Prompt content with potential ${variable} placeholders
        context: Dictionary mapping variable names to values

    Returns:
        Content with all known variables replaced

    Example:
        >>> _substitute_variables("Hello ${name}", {"name": "World"})
        'Hello World'
    """
    def replacer(match):
        var_name = match.group(1)
        if var_name in context:
            return str(context[var_name])
        # Missing variable - log warning, return placeholder unchanged
        logger.warning(f"Variable ${{{var_name}}} not found in context, leaving placeholder")
        return match.group(0)

    return re.sub(r'\$\{([a-zA-Z0-9_]+)\}', replacer, content)


def load_prompt(filename: str, context: dict[str, str] | None = None) -> str:
    """
    Load a prompt from a markdown file in ./prompts/ directory.

    Performs the following operations:
    1. Reads the file from ./prompts/{filename}
    2. Strips YAML front matter (content between --- markers)
    3. Replaces ${variable} placeholders with values from context dict
    4. Falls back to a safe default prompt if file is missing

    Args:
        filename: Name of the prompt file (e.g., "code-review-pr.md")
        context: Optional dictionary of variable substitutions
                 Defaults to {'locale': 'zh-cn', 'input-focus': 'general best practices'}

    Returns:
        str: The processed prompt content, or a safe default if file not found

    Side Effects:
        - Logs a WARNING if file is missing and fallback is used
        - Does not raise exceptions (graceful degradation per constitution)

    Example:
        >>> prompt = load_prompt("code-review-pr.md", {"locale": "en-us"})
        >>> assert "${locale}" not in prompt  # Variable replaced
    """
    if context is None:
        context = {}

    # Default context values
    context.setdefault('locale', 'zh-cn')
    context.setdefault('input-focus', 'general best practices')

    file_path = os.path.join(os.path.dirname(__file__), '..', 'prompts', filename)

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 1. Strip YAML Front Matter
        content, metadata = _strip_yaml_front_matter(content)

        # 2. Variable Substitution
        content = _substitute_variables(content, context)

        return content

    except FileNotFoundError:
        logger.warning(f"Prompt file {file_path} not found, using fallback prompt")
        # Apply variable substitution to fallback prompt too
        return _substitute_variables(_FALLBACK_PROMPT, context)
    except Exception as e:
        logger.warning(f"Error loading prompt file {file_path}: {e}, using fallback prompt")
        return _substitute_variables(_FALLBACK_PROMPT, context)
