# Data Model: Prompts and Configuration Refactoring

**Feature**: 001-prompts-config-refactor
**Date**: 2025-01-01

## Overview

This document defines the data structures and entities for the refactored Gitea AI Code Reviewer configuration system. The refactoring introduces centralized configuration management, externalized prompt files with metadata, and structured logging for LLM operations.

## Entities

### Config

**Purpose**: Centralized configuration container for all environment variables.

**Module**: `utils/config.py`

**Attributes**:

| Attribute | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `LLM_PROVIDER` | `str` | Yes | `"openai"` | Provider identifier for logging/auditing |
| `LLM_API_KEY` | `str \| None` | Conditional* | `None` | Primary LLM authentication key |
| `LLM_BASE_URL` | `str \| None` | No | `None` | Custom LLM endpoint URL (for local/proxy) |
| `LLM_MODEL` | `str` | Yes | `"gpt-4"` | Model identifier for LLM requests |
| `COPILOT_TOKEN` | `str \| None` | No | `None` | Legacy Copilot authentication token |
| `OPENAI_KEY` | `str \| None` | No | `None` | Legacy OpenAI API key (deprecated) |
| `GITEA_HOST` | `str` | Yes | - | Gitea server address |
| `GITEA_TOKEN` | `str` | Yes | - | Gitea API authentication token |
| `IGNORED_FILE_SUFFIX` | `str` | Yes | `.json,.md,.lock` | Comma-separated file extensions to skip |
| `webhook` | `Webhook \| None` | No | `None` | Optional webhook notification config |

**Validation Rules**:
1. At least one of `LLM_API_KEY`, `OPENAI_KEY`, or `COPILOT_TOKEN` must be set
2. If `LLM_API_KEY` is set, `OPENAI_KEY` and `COPILOT_TOKEN` are ignored (strict priority)
3. `GITEA_TOKEN` and `GITEA_HOST` are required—raise `ValueError` if missing

**State Transitions**: None (immutable after initialization)

### Webhook

**Purpose**: Configuration for optional notification webhooks.

**Module**: `utils/config.py`

**Attributes**:

| Attribute | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | `str` | Yes* | - | Notification webhook endpoint URL |
| `header_name` | `str` | No | `None` | Custom header name for notifications |
| `header_value` | `str` | No | `None` | Custom header value for notifications |
| `request_body` | `str` | Yes* | - | JSON template with `{content}` and `{mention}` placeholders |

**Validation Rules**:
1. Both `url` and `request_body` must be set for webhook to be enabled
2. Property `is_init` returns `True` only if both `url` and `request_body` are set

**State Transitions**: None (immutable after initialization)

### PromptFile (Virtual)

**Purpose**: Represents a loaded prompt file with parsed metadata and content.

**Module**: `utils/prompt_loader.py`

**Attributes**:

| Attribute | Type | Description |
|-----------|------|-------------|
| `filename` | `str` | Name of the prompt file (e.g., "code-review-pr.md") |
| `raw_content` | `str` | Original file content including YAML front matter |
| `metadata` | `dict[str, Any]` | Parsed YAML front matter (model, locale, temperature, etc.) |
| `content` | `str` | Prompt content with YAML stripped and variables substituted |
| `context` | `dict[str, str]` | Variable substitution context passed to `load_prompt()` |

**Validation Rules**:
1. If file not found, use fallback prompt (no exception)
2. If YAML parsing fails, strip `---` markers naively (no exception)
3. If variable not in context, leave `${variable}` placeholder intact (log warning)

**State Transitions**: None (immutable per function call)

### PromptMetadata (YAML Front Matter)

**Purpose**: Metadata embedded in prompt files between `---` markers.

**Location**: `./prompts/*.md` files

**Schema**:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `model` | `str` | No | `"gpt-4"` | LLM model to use for this prompt |
| `locale` | `str` | No | `"zh-cn"` | Language locale for review output |
| `temperature` | `float` | No | `0.1` | Sampling temperature |
| `max_tokens` | `int` | No | `4096` | Maximum tokens in response |
| `input-focus` | `str` | No | `"general best practices"` | Review focus area |

**Example**:
```yaml
---
model: gpt-4-0125-preview
locale: zh-cn
temperature: 0.1
max_tokens: 4096
---

You are an AI programming assistant...
```

### LLMRequestContext (Virtual)

**Purpose**: Context passed to `load_prompt()` for variable substitution.

**Module**: `utils/prompt_loader.py`

**Default Values**:

| Variable | Default Value | Purpose |
|----------|---------------|---------|
| `locale` | `"zh-cn"` | Language for review output |
| `input-focus` | `"general best practices"` | Review focus area |
| `model` | `Config.LLM_MODEL` | Current model name |

### StructuredLogEntry

**Purpose**: Log entry emitted for each LLM request with structured metadata.

**Module**: `utils/logger.py` (via loguru)

**Schema**:

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | `str` | ISO 8601 timestamp |
| `level` | `str` | Log level (INFO, WARNING, ERROR) |
| `message` | `str` | Log message text |
| `request_id` | `str` | UUID for request correlation |
| `latency_ms` | `int` | Request duration in milliseconds |
| `status` | `str` | Request status: "success", "timeout", "error" |
| `file` | `str` | Source file name where log was emitted |
| `line` | `int` | Source line number |

**Example**:
```json
{
  "timestamp": "2025-01-01T12:34:56.789Z",
  "level": "INFO",
  "message": "LLM request completed",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "latency_ms": 1234,
  "status": "success",
  "file": "copilot.py",
  "line": 87
}
```

## Relationships

```
┌─────────────┐
│   Config    │
├─────────────┤
│ LLM_*       │───┐
│ GITEA_*     │   │
│ IGNORED_*   │   │
│ webhook     │   │
└─────────────┘   │
                  │
                  ├─── initializes ──→ ┌──────────────────┐
                  │                     │  OpenAI Client   │
                  │                     └──────────────────┘
                  │
                  └─── provides ────→ ┌──────────────────┐
                                        │ PromptLoader     │
                                        │                  │
                  ┌────────────────────┤ load_prompt()    │
                  │                    └──────────────────┘
                  │                             │
                  │                             ▼
                  │                    ┌──────────────────┐
                  │                    │ PromptFile       │
                  │  ├──────────────────┤ (virtual entity) │
                  │                    │ - metadata       │
                  │                    │ - content        │
                  │                    └──────────────────┘
                  │                             │
                  │                             ▼
                  │                    ┌──────────────────┐
                  │                    │ LLMRequest       │
                  │                    │ - request_id     │
                  │                    │ - latency_ms     │
                  │                    │ - status         │
                  │                    └──────────────────┘
                  │                             │
                  ▼                             ▼
           ┌──────────────────────────────────────────┐
           │         StructuredLogEntry             │
           │  (emitted via loguru with bind())      │
           └──────────────────────────────────────────┘
```

## Data Flow

1. **Application Startup**:
   - `Config` instantiated from `.env` file
   - Validates required variables (`GITEA_TOKEN`, `GITEA_HOST`, at least one LLM auth)
   - Applies strict priority for LLM authentication

2. **Webhook Received**:
   - Parse Gitea payload
   - Fetch diff blocks from Gitea API

3. **Per-File Processing**:
   - Call `PromptLoader.load_prompt("code-review-pr.md", context)`
   - Read `./prompts/code-review-pr.md`
   - Parse YAML front matter → `PromptFile.metadata`
   - Strip `---` markers → `PromptFile.content`
   - Substitute `${locale}`, `${input-focus}`, `${model}` → final prompt string
   - Initialize OpenAI client with `Config.LLM_API_KEY`, `Config.LLM_BASE_URL`
   - Send request with 60-second timeout
   - Bind `request_id`, `latency_ms`, `status` to logger
   - Emit `StructuredLogEntry` via `logger.bind()`

## Validation Summary

| Entity | Validation Type | Key Constraints |
|--------|-----------------|------------------|
| **Config** | Startup validation | Required vars present, at least one LLM auth method |
| **Webhook** | Optional validation | Both url and request_body must be set |
| **PromptFile** | Graceful degradation | Fallback to default prompt on file errors |
| **PromptMetadata** | Optional metadata | All fields have sensible defaults |
| **LLMRequestContext** | Variable substitution | Missing vars left as placeholders with warning |
| **StructuredLogEntry** | Schema validation | All fields present in log output |

## References

- [Specification: Requirements](spec.md#requirements)
- [Specification: Module Specifications](spec.md#module-specifications)
- [Constitution: Configuration as Code](/.specify/memory/constitution.md#i-configuration-as-code)
