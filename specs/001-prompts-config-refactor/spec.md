# Feature Specification: Prompts and Configuration Refactoring

**Feature Branch**: `001-prompts-config-refactor`
**Created**: 2025-01-01
**Status**: Draft
**Input**: User description: "Refactor Gitea AI Code Reviewer: Externalize prompts, modularize configuration, support flexible LLM providers"

## System Architecture Overview

### Current State (Monolithic)

The current system has AI system prompts hardcoded directly in the source code at `codereview/copilot.py:43-44`. Configuration is scattered throughout the codebase with direct `os.getenv()` calls. The system only supports a single LLM provider (Copilot API at cocopilot.org) with hardcoded endpoints and model settings.

### Target State (Modular)

The refactored system will:

1. **Externalize Prompts**: Store AI system instructions as Markdown files in a `./prompts/` directory, separate from application code
2. **Centralize Configuration**: Use a single `Config` class with python-dotenv to manage all environment variables
3. **Support Multiple LLM Providers**: Enable switching between OpenAI, Azure OpenAI, local LLMs (Ollama, LocalAI), and enterprise proxies through configuration
4. **Graceful Degradation**: Fall back to safe defaults when optional assets are missing

### Architecture Shift

```
BEFORE:
┌─────────────────────────────────────────────────────────────┐
│ main.py                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   FastAPI    │───>│ Copilot AI  │    │  Gitea API   │  │
│  │              │    │ [Hardcoded  │    │              │  │
│  │              │    │  Prompt]    │    │              │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
└─────────────────────────────────────────────────────────────┘

AFTER:
┌─────────────────────────────────────────────────────────────┐
│ main.py                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   FastAPI    │───>│ LLM Client  │    │  Gitea API   │  │
│  │              │    │ [Config     │    │              │  │
│  │              │    │  Base URL]  │    │              │  │
│  └──────────────┘    └──────┬───────┘    └──────────────┘  │
│                            │                                   │
│  ┌──────────────┐    ┌──────▼───────┐                        │
│  │  Config      │───>│PromptLoader │                        │
│  │  [.env vars] │    │[./prompts/] │                        │
│  └──────────────┘    └──────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

## Clarifications

### Session 2025-01-01

- **Q**: LLM request timeout behavior when request hangs or takes too long? → **A**: Timeout after 60 seconds, log warning, skip to next file (continue processing)
- **Q**: Which authentication method takes precedence when multiple are configured? → **A**: Strict priority: LLM_API_KEY first, then OPENAI_KEY, then COPILOT_TOKEN (lower-priority ignored if higher is set)
- **Q**: Should system expose metrics for monitoring LLM requests? → **A**: Logs only - emit structured JSON logs with request_id, latency_ms, status for each LLM call

## Configuration Schema

### Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `GITEA_TOKEN` | Yes | - | Authentication token for Gitea API access |
| `GITEA_HOST` | Yes | - | Gitea server address (e.g., `server:3000`) |
| `LLM_API_KEY` | Conditional* | - | Primary LLM provider API key (required if no other LLM auth method) |
| `LLM_BASE_URL` | No | - | Custom LLM endpoint URL (for local LLMs or proxies) |
| `LLM_MODEL` | No | `gpt-4` | Model identifier for LLM requests |
| `LLM_PROVIDER` | No | `openai` | Provider name identifier (for logging/auditing) |
| `COPILOT_TOKEN` | Conditional* | - | Legacy Copilot authentication token (required if no other LLM auth method) |
| `OPENAI_KEY` | Conditional* | - | Legacy OpenAI API key (required if no other LLM auth method) |
| `IGNORED_FILE_SUFFIX` | No | `.json,.md,.lock` | Comma-separated file extensions to skip during review |
| `WEBHOOK_URL` | No | - | Optional notification webhook endpoint |
| `WEBHOOK_HEADER_NAME` | No | - | Custom header name for webhook notifications |
| `WEBHOOK_HEADER_VALUE` | No | - | Custom header value for webhook notifications |
| `WEBHOOK_REQUEST_BODY` | No | - | JSON template for webhook payload (supports `{content}` and `{mention}` placeholders) |

**\*Conditional requirement**: At least one LLM authentication method must be configured: `LLM_API_KEY` (recommended), `OPENAI_KEY`, or `COPILOT_TOKEN`. If multiple are set, strict priority applies: `LLM_API_KEY` > `OPENAI_KEY` > `COPILOT_TOKEN`.

### Backward Compatibility

The system must check for legacy environment variables in this order:
1. If `LLM_API_KEY` is set, use it (highest priority, ignore legacy keys)
2. Else if `OPENAI_KEY` is set, use it and log a deprecation warning
3. Else if `COPILOT_TOKEN` is set, use it for Copilot-specific authentication
4. If none are available, log an error and prevent startup

**Priority Rule**: When multiple authentication methods are configured, strict priority applies—`LLM_API_KEY` takes precedence over `OPENAI_KEY`, which takes precedence over `COPILOT_TOKEN`. Lower-priority keys are ignored if a higher-priority key is set.

### Prompt File Context Variables

When loading prompt files, the system supports variable substitution using the following context:

| Variable | Purpose | Example Value |
|----------|---------|---------------|
| `${locale}` | Language locale for review output | `zh-cn`, `en-us` |
| `${input-focus}` | Review focus area (security, performance, etc.) | `security vulnerabilities` |
| `${model}` | Current LLM model name | `gpt-4-turbo` |

## Module Specifications

### Config Class

**Purpose**: Centralized configuration management for all application settings.

**Location**: `utils/config.py`

**Class Structure**:

```python
class Config:
    """
    Centralized configuration loader using python-dotenv.

    Loads all environment variables from .env file and provides
    typed access throughout the application. Implements graceful
    degradation with fallback values for optional settings.
    """

    # LLM Configuration
    LLM_PROVIDER: str          # Provider identifier (e.g., "openai", "copilot")
    LLM_API_KEY: str | None    # Primary API key (may be None for local LLMs)
    LLM_BASE_URL: str | None   # Custom endpoint URL (None for default OpenAI)
    LLM_MODEL: str             # Model identifier

    # Legacy Compatibility
    COPILOT_TOKEN: str | None  # Copilot-specific token
    OPENAI_KEY: str | None     # Legacy OpenAI key (fallback)

    # Gitea Configuration
    GITEA_HOST: str            # Gitea server address
    GITEA_TOKEN: str           # Gitea API token

    # Application Settings
    IGNORED_FILE_SUFFIX: str   # File extensions to skip

    # Optional Webhook
    webhook: Webhook | None    # Webhook notification config (if enabled)

    def __init__(self, config_file: str | None = None):
        """
        Load configuration from .env file.

        Args:
            config_file: Optional path to custom .env file

        Raises:
            ValueError: If required variables (GITEA_TOKEN, GITEA_HOST) are missing
        """
```

**Loading Logic**:
1. Call `load_dotenv(config_file or ".env")`
2. Load `GITEA_TOKEN` and `GITEA_HOST` - raise `ValueError` if missing
3. Load `LLM_API_KEY`, falling back to `OPENAI_KEY` if missing (log deprecation warning)
4. Load `LLM_BASE_URL` with `None` as default
5. Load `LLM_MODEL` with `"gpt-4"` as default
6. Load `LLM_PROVIDER` with `"openai"` as default
7. Load optional variables with sensible defaults
8. Validate that at least one LLM authentication method is available
9. If multiple auth methods are set, apply strict priority (LLM_API_KEY > OPENAI_KEY > COPILOT_TOKEN)

### PromptLoader Module

**Purpose**: Load and parse AI system prompts from Markdown files with YAML front matter support.

**Location**: `utils/prompt_loader.py`

**Function Signatures**:

```python
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
```

**YAML Parsing Logic**:

```python
def _strip_yaml_front_matter(content: str) -> str:
    """
    Remove YAML front matter from markdown content.

    YAML front matter is delimited by --- markers at the start of the file:

    ---
    model: gpt-4-0125-preview
    locale: zh-cn
    ---

    Actual prompt content here...

    Args:
        content: Raw file content including YAML markers

    Returns:
        str: Content with YAML section removed

    Algorithm:
        1. If content starts with "---":
        2. Split on "---" and find the third section (after second marker)
        3. If less than 3 sections, remove first "---" prefix
        4. Strip leading/trailing whitespace
    """
```

**Variable Replacement Strategy**:

```python
def _substitute_variables(content: str, context: dict[str, str]) -> str:
    """
    Replace ${variable} placeholders with actual values.

    Supports:
    - Simple variables: ${locale} → "zh-cn"
    - Missing variables: Leave placeholder unchanged (with warning log)

    Args:
        content: Prompt content with potential ${variable} placeholders
        context: Dictionary mapping variable names to values

    Returns:
        str: Content with all known variables replaced

    Example:
        >>> _substitute_variables("Hello ${name}", {"name": "World"})
        'Hello World'
    """
```

**Graceful Degradation**:

The loader MUST implement the following fallback behavior:
1. If prompt file is missing: Log WARNING and return default prompt
2. If YAML parsing fails: Log WARNING and return content without parsing
3. If variable is missing from context: Log WARNING and leave placeholder in content
4. The system MUST NEVER crash due to prompt file issues

**Default Fallback Prompt**:

```
You are a senior code reviewer. Analyze the provided code diff for:
- Security vulnerabilities
- Performance issues
- Code style and readability
- Potential bugs

Provide constructive feedback in ${locale}.
```

## Infrastructure & Deployment

### Dockerfile Strategy

**Base Image**: `python:3.10-slim`

**Build Process**:
1. Set working directory to `/app`
2. Copy `requirements.txt` and install dependencies
3. Copy remaining application code
4. Expose port 3008
5. Set default command to `python main.py`

**Key Requirements**:
- Use `--no-cache-dir` for pip to keep image size minimal
- Do NOT copy `.env` file (secrets mounted as volume or passed via docker-compose)
- Include `.specify/` directory for project templates (development convenience)

### Docker Compose Volume Mappings

**Required Volumes**:

| Volume Mapping | Purpose | Hot-Reload |
|----------------|---------|------------|
| `./main.py:/app/main.py` | Application entry point | Yes |
| `./prompts:/app/prompts` | AI prompt files | Yes |

**Optional Volumes**:

| Volume Mapping | Purpose |
|----------------|---------|
| `./codereview:/app/codereview` | AI provider modules |
| `./gitea:/app/gitea` | Gitea API client |
| `./utils:/app/utils` | Utility modules |

**Network Configuration**:
- External network: `gitea_gitea` (connects to Gitea server)
- Port mapping: `3008:3008`
- Extra hosts: `host.docker.internal:host-gateway` (for local development)

**Environment Variable Passing**:
- Use `env_file: .env` to load secrets from host
- Override specific variables in `environment:` section (e.g., `GITEA_HOST` for container networking)

### Hot-Reloading Behavior

When running in Docker Compose with volume mounts:
1. **Prompts**: Changes to `./prompts/*.md` files on host are immediately available in container without restart
2. **Main Script**: Changes to `main.py` trigger auto-reload (uvicorn reload=True in development)
3. **Environment Variables**: Require container restart (env_file only read at startup)

## Data Flow

### Complete Webhook Processing Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. WEBHOOK RECEIVED                                                         │
│    Gitea sends POST /codereview with push event payload                      │
└───────────────────────────────────────────┬─────────────────────────────────┘
                                            │
                                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. CONFIG LOAD                                                              │
│    - Config() instantiated                                                  │
│    - .env file loaded via python-dotenv                                     │
│    - LLM_BASE_URL, LLM_API_KEY, LLM_MODEL extracted                          │
│    - Backward compatibility: checks OPENAI_KEY if LLM_API_KEY missing       │
└───────────────────────────────────────────┬─────────────────────────────────┘
                                            │
                                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. EXTRACT REQUEST INFO                                                      │
│    - Parse webhook payload for owner, repo, sha, ref, pusher, title         │
│    - Check for [skip codereview] in commit title                             │
└───────────────────────────────────────────┬─────────────────────────────────┘
                                            │
                       ┌────────────────────┴────────────────────┐
                       │                                         │
                       ▼                                         ▼
┌─────────────────────────────┐           ┌─────────────────────────────────┐
│ 4a. PROMPT LOAD             │           │ 4b. FETCH DIFF FROM GITEA       │
│    - PromptLoader invoked   │           │    - GiteaClient.get_diff_blocks│
│    - Read ./prompts/*.md    │           │    - Parse diff into file blocks │
│    - Strip YAML front matter│           │    - Return list of diffs        │
│    - Substitute variables   │           │                                   │
│    - Fallback if missing    │           │                                   │
└──────────────┬──────────────┘           └───────────────┬─────────────────┘
               │                                         │
               └─────────────────┬───────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 5. LLM REQUEST PER FILE                                                     │
│    For each diff block:                                                     │
│    a. Check file suffix against ignored list                                │
│    b. Load prompt from PromptLoader                                         │
│    c. Construct messages array:                                             │
│       - role: "system", content: <prompt from file>                         │
│       - role: "user", content: <diff>                                       │
│    d. Initialize LLM client with Config values:                             │
│       - api_key=Config.LLM_API_KEY                                          │
│       - base_url=Config.LLM_BASE_URL (or None for default)                  │
│    e. Send request to LLM endpoint with 60-second timeout                    │
│    f. Parse response and format comment                                     │
│    g. Emit structured log: {request_id, latency_ms, status}                  │
│    h. Create issue or add comment via GiteaClient                           │
│    i. Sleep 1.5 seconds (rate limiting)                                     │
└───────────────────────────────────────────┬─────────────────────────────────┘
                                            │
                                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 6. NOTIFICATION (OPTIONAL)                                                  │
│    - If webhook configured, send notification with review URL               │
└───────────────────────────────────────────┬─────────────────────────────────┘
                                            │
                                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 7. RESPONSE                                                                 │
│    - Return {"message": "review_result"} to webhook caller                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Error Handling Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ ERROR: Prompt File Missing                                                  │
│ → Log WARNING: "Prompt file {filename} not found, using fallback"           │
│ → Use default prompt                                                        │
│ → Continue processing                                                       │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ ERROR: YAML Parse Fails                                                    │
│ → Log WARNING: "Failed to parse YAML in {filename}, using raw content"      │
│ → Use file content without YAML stripping                                  │
│ → Continue processing                                                       │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ ERROR: Config Variable Missing (Required)                                   │
│ → Raise ValueError with clear message                                       │
│ → Prevent application startup                                               │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ ERROR: Config Variable Missing (Optional)                                   │
│ → Log INFO: "Using default value for {variable}"                           │
│ → Use documented default                                                    │
│ → Continue processing                                                       │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ ERROR: LLM Request Fails                                                   │
│ → Log ERROR with response details                                           │
│ → Return error message in Gitea issue comment                               │
│ → Continue with next file (if processing multiple files)                    │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ ERROR: LLM Request Timeout (>60 seconds)                                   │
│ → Log WARNING with request_id and latency                                  │
│ → Skip to next file (continue processing)                                   │
│ → Structured log: {"request_id": "uuid", "latency_ms": 60000, "status": "timeout"}│
└─────────────────────────────────────────────────────────────────────────────┘
```

## User Scenarios & Testing

### User Story 1 - Externalized Prompt Management (Priority: P1)

A repository maintainer wants to customize the AI code review instructions to focus on security vulnerabilities without modifying any code or restarting the service.

**Why this priority**: This is the core value proposition of the refactoring—enabling non-technical users to modify AI behavior through configuration rather than code changes. It directly addresses the most critical limitation in the current system.

**Independent Test**: Can be tested by modifying `./prompts/code-review-pr.md` and observing that the AI uses the new instructions on the next webhook trigger, without any code changes or container restart.

**Acceptance Scenarios**:

1. **Given** the system is running, **When** a user edits `./prompts/code-review-pr.md` on the host machine, **Then** the next code review uses the updated prompt (no restart required)
2. **Given** a prompt file contains `${locale}` placeholder, **When** the prompt is loaded with context `{"locale": "en-us"}`, **Then** the placeholder is replaced with "en-us" in the loaded prompt
3. **Given** a prompt file has YAML front matter, **When** the prompt is loaded, **Then** the YAML content is stripped and not sent to the LLM API
4. **Given** the `./prompts/code-review-pr.md` file is missing, **When** the system attempts to load it, **Then** a WARNING is logged and a safe default prompt is used instead

---

### User Story 2 - Flexible LLM Provider Configuration (Priority: P2)

A DevOps engineer wants to switch from the Copilot API to a local Ollama instance running on the same server to reduce API costs and latency.

**Why this priority**: Enables cost savings and data privacy by supporting local LLMs. Important for enterprises with strict data governance policies. Secondary to prompt management because the system must work with prompts first.

**Independent Test**: Can be tested by setting `LLM_BASE_URL` to point to a local LLM endpoint and `LLM_API_KEY` to empty/omitted, then verifying the system sends requests to the local endpoint.

**Acceptance Scenarios**:

1. **Given** `LLM_BASE_URL` is set to `http://localhost:11434/v1`, **When** the LLM client makes a request, **Then** the request is sent to localhost:11434 instead of the default OpenAI endpoint
2. **Given** `LLM_API_KEY` is not set, **When** the system starts, **Then** it checks for `OPENAI_KEY` as a fallback and logs a deprecation warning if found
3. **Given** `LLM_MODEL` is set to `llama3`, **When** a code review is performed, **Then** the LLM request specifies model "llama3"
4. **Given** all LLM authentication variables are missing, **When** the system starts, **Then** it raises a clear ValueError indicating which variables are required

---

### User Story 3 - Container Deployment with Hot-Reload (Priority: P3)

A developer wants to iterate on prompt templates by editing files on their host machine and seeing changes take effect immediately in the running container.

**Why this priority**: Improves developer experience and enables rapid experimentation. Lowest priority because the system can function without hot-reloading (users can restart the container), but it's a significant quality-of-life improvement.

**Independent Test**: Can be tested by running `docker-compose up`, editing `./prompts/code-review-pr.md` on the host, and triggering a webhook to verify the new prompt is used without restarting the container.

**Acceptance Scenarios**:

1. **Given** a container is running with `./prompts:/app/prompts` volume mounted, **When** a file is edited in the host's `./prompts/` directory, **Then** the change is visible inside the container at `/app/prompts/`
2. **Given** the volume mount is configured, **When** the prompt loader reads a file, **Then** it reads the latest content from the mounted volume (not the baked-in image content)
3. **Given** the volume mount is missing, **When** the container starts, **Then** the system uses the prompts baked into the image at build time

---

### Edge Cases

- What happens when a prompt file contains invalid YAML syntax? → Log WARNING, strip YAML markers naively, continue with raw content
- What happens when the `.env` file is missing entirely? → Raise ValueError, prevent startup with clear message about required variables
- What happens when `LLM_BASE_URL` is set but unreachable? → Log ERROR, return error message in Gitea comment, don't crash the service
- What happens when a variable placeholder `${custom_var}` is in the prompt but not in context? → Log WARNING, leave placeholder in content, send to LLM as-is
- What happens when the `./prompts/` directory doesn't exist? → Log WARNING, use default prompt for all requests
- What happens when `GITEA_TOKEN` expires during operation? → **OUT OF SCOPE** - Gitea token renewal is outside this refactoring's scope. Current behavior: API calls fail, log ERROR, notify user via webhook if configured. Token renewal is handled by Gitea administrators or via external automation.
- What happens when LLM request exceeds 60 seconds? → Timeout, log WARNING, skip to next file (continue processing)
- What happens when multiple LLM authentication variables are set? → Apply strict priority: LLM_API_KEY > OPENAI_KEY > COPILOT_TOKEN (highest wins, ignore others)

## Requirements

### Functional Requirements

- **FR-001**: System MUST load AI system prompts from Markdown files in `./prompts/` directory
- **FR-002**: System MUST strip YAML front matter from prompt files before sending to LLM API
- **FR-003**: System MUST replace `${variable}` placeholders in prompts with values from context dictionary
- **FR-004**: System MUST use a centralized `Config` class to load all environment variables via python-dotenv
- **FR-005**: System MUST support `LLM_BASE_URL` environment variable for custom LLM endpoints
- **FR-006**: System MUST support `LLM_API_KEY` environment variable for LLM authentication
- **FR-007**: System MUST fall back to `OPENAI_KEY` if `LLM_API_KEY` is missing, with deprecation warning logged
- **FR-008**: System MUST support `LLM_MODEL` environment variable for configurable model selection
- **FR-009**: System MUST provide a default fallback prompt when `./prompts/code-review-pr.md` is missing
- **FR-010**: System MUST log a WARNING when using fallback prompts due to missing files
- **FR-011**: System MUST mount `./prompts` directory as a Docker volume for hot-reloading
- **FR-012**: System MUST raise `ValueError` on startup if required variables (`GITEA_TOKEN`, `GITEA_HOST`) are missing
- **FR-013**: System MUST NOT crash due to missing or invalid prompt files (graceful degradation)
- **FR-014**: System MUST construct LLM messages array with prompt content as `role: system`
- **FR-015**: System MUST initialize LLM client using `base_url` from Config (if set)
- **FR-016**: System MUST timeout LLM requests after 60 seconds and continue processing next file
- **FR-017**: System MUST apply strict priority when multiple LLM authentication methods are configured (LLM_API_KEY > OPENAI_KEY > COPILOT_TOKEN)
- **FR-018**: System MUST emit structured JSON logs for each LLM request including request_id, latency_ms, and status

### Key Entities

**Prompt File**: A Markdown file stored in `./prompts/` directory containing AI system instructions. May include YAML front matter (metadata delimited by `---`) and variable placeholders (`${variable}`).

**Configuration Context**: A dictionary mapping variable names to values used for prompt substitution. Includes `locale`, `input-focus`, and `model` by default.

**Fallback Prompt**: A safe default system prompt used when the specified prompt file is missing or unreadable. See "Default Fallback Prompt" in Module Specifications for the full text.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Repository maintainers can modify AI review instructions by editing files in `./prompts/` directory without code changes
- **SC-002**: System continues operating when prompt files are missing (uses fallback, logs WARNING)
- **SC-003**: Users can switch LLM providers by changing environment variables in `.env` file
- **SC-004**: System supports local LLMs (Ollama, LocalAI) when `LLM_BASE_URL` is configured
- **SC-005**: Changes to `./prompts/*.md` files on host are reflected in container without restart (volume mount verified)
- **SC-006**: Prompt YAML front matter is never sent to LLM API (validated by checking API request logs)
- **SC-007**: Variable placeholders like `${locale}` are replaced with actual values in loaded prompts
- **SC-008**: System provides clear error messages when required configuration is missing on startup
- **SC-009**: Backward compatibility maintained—existing deployments with `OPENAI_KEY` continue working with deprecation warning

### Assumptions

1. The `.env` file exists in the project root or is provided via Docker Compose `env_file`
2. The `./prompts/` directory will be created during implementation (does not currently exist)
3. YAML front matter in prompt files will follow standard format (content between first and second `---` markers)
4. Local LLMs (Ollama, LocalAI) provide OpenAI-compatible API endpoints
5. Docker Compose is used for container orchestration in production
6. The application runs with `reload=True` in development mode for main.py hot-reloading
7. Variable placeholders in prompts use `${variable}` syntax (not other formats like `{{variable}}` or `%variable%`)

### Dependencies

- **Existing Codebase**: Current `main.py`, `codereview/copilot.py`, `utils/config.py`, `gitea/client.py`
- **Constitution**: Project constitution at `.specify/memory/constitution.md` (Must-Haves and Prohibited Actions)
- **Documentation**: Existing documentation at `docs/OLD_Documentation.md` for current architecture reference
- **Python Packages**: `python-dotenv`, `pyyaml` already in `requirements.txt`
