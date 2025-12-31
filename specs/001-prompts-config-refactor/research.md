# Research: Prompts and Configuration Refactoring

**Feature**: 001-prompts-config-refactor
**Date**: 2025-01-01
**Status**: Complete

## Overview

This document captures technology decisions, best practices research, and architectural patterns for refactoring the Gitea AI Code Reviewer from a monolithic script to a modular, containerized service with externalized prompts and flexible LLM provider configuration.

## Technology Decisions

### 1. OpenAI Python SDK for LLM Integration

**Decision**: Use `openai>=1.0.0` SDK for LLM provider communication.

**Rationale**:
- Official library with robust `base_url` configuration support
- Built-in timeout handling via `timeout` parameter
- Automatic error response parsing with descriptive exceptions
- Compatible with OpenAI, Azure OpenAI, and local LLMs (Ollama, LocalAI) through base_url
- Type hints included for better IDE support

**Alternatives Considered**:
- **requests** (current approach): Requires manual error handling, timeout implementation, and response parsing. More code to maintain.
- **httpx**: Async-first, but adds complexity for synchronous use case. OpenAI SDK wraps httpx internally.
- **LangChain**: Over-engineered for this use case. Adds dependency chain for simple prompt/response pattern.

**Implementation Pattern**:
```python
from openai import OpenAI
from utils.config import Config

config = Config()

client = OpenAI(
    api_key=config.LLM_API_KEY,
    base_url=config.LLM_BASE_URL,  # None for default OpenAI endpoint
    timeout=60.0,  # 60-second timeout per clarification
)

response = client.chat.completions.create(
    model=config.LLM_MODEL,
    messages=[
        {"role": "system", "content": prompt},
        {"role": "user", "content": diff_content}
    ]
)
```

### 2. PyYAML for Front Matter Parsing

**Decision**: Use `PyYAML>=6.0.1` for parsing YAML front matter in prompt files.

**Rationale**:
- Already in requirements.txt
- Mature, battle-tested library
- Handles YAML edge cases (multiline strings, lists, nested structures)
- Simple `safe_load()` API prevents code execution vulnerabilities
- Widely adopted in static site generators (Jekyll, Hugo) for front matter parsing

**Alternatives Considered**:
- **Custom string splitting**: Faster dependency-free approach using `split("---")`. Chosen as fallback in PromptLoader for simplicity, but PyYAML provides validation.
- **ruamel.yaml**: More features but heavier dependency. Overkill for simple key-value metadata.
- **toml**: Not suitable—front matter convention uses YAML, not TOML.

**Implementation Pattern**:
```python
import yaml

def _strip_yaml_front_matter(content: str) -> tuple[str, dict]:
    """
    Returns (content_without_yaml, parsed_metadata)
    """
    if not content.startswith("---"):
        return content, {}

    try:
        # Split on --- delimiter
        parts = content.split("---", 2)
        if len(parts) == 3:
            metadata = yaml.safe_load(parts[1]) or {}
            return parts[2].strip(), metadata
        # Malformed—fallback to naive strip
        return content.replace("---", "", 1), {}
    except yaml.YAMLError:
        # Parse error—return content without YAML markers
        return content.replace("---", "", 1), {}
```

### 3. Variable Substitution Strategy

**Decision**: Custom string replacement using `${variable}` syntax with regex.

**Rationale**:
- No additional template dependencies (Jinja2, Mako, string.Template)
- Simple, fast, and predictable
- Regex pattern: `\$\{([a-zA-Z0-9_]+)\}` matches variable names
- Graceful handling of missing variables (leave placeholder intact with warning)

**Alternatives Considered**:
- **string.Template**: Uses `$var` syntax (no braces), less explicit, conflicts with shell variable syntax
- **Jinja2**: Overkill for simple substitution, adds heavy dependency, security concerns if prompts are user-editable
- **str.format()**: Requires `{var}` syntax, conflicts with YAML/JSON content in prompts

**Implementation Pattern**:
```python
import re
from typing import Dict

def _substitute_variables(content: str, context: Dict[str, str]) -> str:
    """
    Replace ${variable} placeholders with values from context.
    Missing variables are left intact (with warning logged).
    """
    def replacer(match):
        var_name = match.group(1)
        if var_name in context:
            return str(context[var_name])
        # Missing variable—log warning, return placeholder unchanged
        logger.warning(f"Variable ${{{var_name}}} not found in context")
        return match.group(0)  # Return original ${var}

    return re.sub(r'\$\{([a-zA-Z0-9_]+)\}', replacer, content)
```

### 4. Structured Logging with Loguru

**Decision**: Use `loguru>=0.7.2` with custom JSON formatter for structured logs.

**Rationale**:
- Already in requirements.txt
- Simpler API than standard logging module
- Built-in rotation, compression, and filtering
- Supports custom formatters via `lambda` functions
- JSON logs consumable by monitoring systems (Loki, Elasticsearch, CloudWatch)

**Alternatives Considered**:
- **standard logging**: Verbose API, requires custom handler for JSON
- **structlog**: More powerful but adds dependency
- **python-json-logger**: Library-specific formatter, loguru can do this natively

**Implementation Pattern**:
```python
from loguru import logger
import json
from typing import Dict, Any

def structured_formatter(record: Dict[str, Any]) -> str:
    """
    Convert log record to JSON string with request_id, latency_ms, status fields.
    """
    log_data = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "message": record["message"],
        "request_id": record.get("extra", {}).get("request_id"),
        "latency_ms": record.get("extra", {}).get("latency_ms"),
        "status": record.get("extra", {}).get("status"),
        "file": record["file"].name,
        "line": record["line"],
    }
    return json.dumps(log_data)

# Configure logger
logger.remove()  # Remove default handler
logger.add(
    sys.stdout,
    format=structured_formatter,
    level="INFO",
    serialize=True,  # Use built-in JSON serialization
)

# Usage in code:
logger.bind(request_id=uuid.uuid4(), latency_ms=1234, status="success").info("LLM request completed")
```

### 5. Docker Volume Mount Hot-Reload

**Decision**: Mount `./prompts:/app/prompts` as read-write volume in docker-compose.yml.

**Rationale**:
- File changes on host immediately visible in container (no rebuild required)
- Enables rapid prompt iteration during development
- Production can use baked-in prompts (omit volume mount in production compose file)
- `uvicorn reload=True` handles main.py hot-reloading separately

**Performance Considerations**:
- Volume mounts have minimal overhead on Linux (bind mounts)
- On macOS/Windows, performance may degrade—use cached volumes or mutagen for development
- Prompt files are small (<10KB each), I/O overhead negligible

**Alternatives Considered**:
- **ConfigMap/Secret (Kubernetes)**: More complex for single-container setup
- **S3/curl on startup**: Adds network dependency, slows startup, not truly hot-reload
- **ENV variables**: Not suitable for multi-line prompts, difficult to edit

**Implementation Pattern**:
```yaml
# docker-compose.yml
services:
  ai-codereview:
    volumes:
      - ./prompts:/app/prompts:rw  # Hot-reload for development
      # In production: omit this volume, prompts baked into image
```

### 6. Configuration Loading Priority

**Decision**: Strict priority order for LLM authentication: `LLM_API_KEY` > `OPENAI_KEY` > `COPILOT_TOKEN`.

**Rationale**:
- Single source of truth prevents ambiguity
- Operators have explicit control via which variables they set
- Backward compatibility maintained without fallback chains
- Deprecation warnings guide migration to new variables

**Alternatives Considered**:
- **First non-empty found**: Unpredictable, depends on env var ordering
- **Error on multiple configured**: Forces single source but breaks existing deployments
- **Combine all keys**: Complex, no clear precedence, potential security issues

**Implementation Pattern**:
```python
class Config:
    def __init__(self):
        # Load variables
        llm_api_key = os.getenv("LLM_API_KEY")
        openai_key = os.getenv("OPENAI_KEY")
        copilot_token = os.getenv("COPILOT_TOKEN")

        # Apply strict priority
        if llm_api_key:
            self.LLM_API_KEY = llm_api_key
        elif openai_key:
            self.LLM_API_KEY = openai_key
            logger.warning("OPENAI_KEY is deprecated, use LLM_API_KEY instead")
        elif copilot_token:
            self.LLM_API_KEY = copilot_token
        else:
            raise ValueError("At least one LLM authentication method required: LLM_API_KEY, OPENAI_KEY, or COPILOT_TOKEN")
```

## Best Practices Summary

| Area | Best Practice | Source |
|------|---------------|--------|
| **Type Hints** | Use `str | None` for optional values, `dict[str, str]` for string mappings | PEP 585 (Python 3.9+) |
| **Config Class** | Use `@dataclass` or plain class with class-level attributes loaded in `__init__` | python-dotenv documentation |
| **Error Handling** | Log WARNING for fallbacks, raise ValueError for startup failures | Constitution Graceful Degradation |
| **File I/O** | Always use `encoding='utf-8'` parameter for `open()` | Python best practices |
| **Docker** | Multi-stage builds not needed for Python 3.10-slim (already minimal) | Docker best practices |
| **Testing** | Manual testing via `/test` endpoint acceptable for this refactor | Project scope |
| **Logging** | Use `logger.bind()` for contextual data (request_id, latency_ms) | Loguru documentation |

## References

- [OpenAI Python SDK Documentation](https://github.com/openai/openai-python)
- [PyYAML Documentation](https://pyyaml.org/wiki/)
- [Loguru Documentation](https://github.com/Delgan/loguru)
- [Python Type Hints PEP 484](https://peps.python.org/pep-0484/)
- [Python Type Hints PEP 585](https://peps.python.org/pep-0585/)
- [Docker Volume Mounts](https://docs.docker.com/storage/volumes/)
- [Project Constitution](/.specify/memory/constitution.md)
