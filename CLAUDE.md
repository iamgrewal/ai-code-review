# CLAUDE.md - Project Context & Architecture Documentation

## Project Overview
**Project Name:** Gitea AI Code Reviewer
**Repository:** `bestK/gitea-ai-codereview` (local fork)
**Purpose:** A lightweight, self-hosted Python bot that integrates with Gitea. It listens for Webhook events (Push commits), fetches code diffs, sends them to an LLM (Large Language Model) for analysis, and posts the review comments back to Gitea Issues.

**Tech Stack:**
- **Framework:** FastAPI (Uvicorn server)
- **Python:** 3.10+ (pyproject.toml specifies ^3.11)
- **AI Provider:** Configurable LLM providers via OpenAI-compatible API (OpenAI, Azure, Ollama, LocalAI, Copilot)
- **Configuration:** python-dotenv with centralized Config class
- **Logging:** loguru with structured JSON logging
- **Containerization:** Docker + docker-compose
- **Prompt Management:** Externalized Markdown files with YAML front matter

---

## Current Architecture & Codebase Documentation

### Directory Structure
```
gitea-ai-codereview/
├── codereview/              # AI review layer
│   ├── __init__.py
│   ├── ai.py                # Abstract base class for AI providers
│   └── copilot.py           # Copilot AI implementation (uses load_prompt)
├── gitea/                   # Gitea integration layer
│   ├── __init__.py
│   └── client.py            # Gitea API client
├── utils/                   # Utilities
│   ├── __init__.py
│   ├── config.py            # Configuration management (LLM_API_KEY, LLM_BASE_URL, etc.)
│   ├── logger.py            # Logging setup (loguru with structured JSON formatter)
│   ├── prompt_loader.py     # Prompt loading with YAML parsing and variable substitution
│   └── utils.py             # Helper functions
├── prompts/                 # AI prompt files (externalized, gitignored for user customization)
│   ├── README.md            # Prompt file documentation
│   └── code-review-pr.md    # Default system prompt with YAML front matter
├── logs/                    # Application logs (gitignored)
├── docs/                    # Documentation
├── .env                     # Environment variables (secrets, gitignored)
├── .env.example            # Example environment file
├── main.py                  # FastAPI application entry point
├── Dockerfile               # Container configuration
├── docker-compose.yml       # Docker orchestration with prompts volume mount
├── pyproject.toml          # Poetry project configuration
├── requirements.txt        # Python dependencies
└── CLAUDE.md               # This file
```

### File-by-File Documentation

#### `main.py` - FastAPI Application Entry Point
**Location:** [main.py](main.py)

**Key Components:**
```python
# Global instances (lines 14-20)
app = FastAPI()
config = Config()
gitea_client = GiteaClient(config.GITEA_HOST, config.GITEA_TOKEN)
copilot = Copilot(config)  # Now takes Config object instead of individual token
```

**API Endpoints:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/codereview` | POST | Webhook receiver for Gitea push events |
| `/test` | POST | Manual testing endpoint for code review |

**Webhook Flow (`/codereview`):**
1. Extract info from request: `owner, repo, sha, ref, pusher, full_name, title, commit_url`
2. Skip if title contains `[skip codereview]`
3. Fetch diff blocks from Gitea
4. For each diff block:
   - Check if file suffix is in `config.IGNORED_FILE_SUFFIX`
   - Send to AI for code review (with 60-second timeout)
   - First file: Create new Gitea Issue
   - Subsequent files: Add comments to issue
   - Sleep 1.5s between requests
5. Add AI banner to final issue comment
6. Optional: Send notification webhook (if configured)

**Uvicorn Configuration:**
- Host: `0.0.0.0`
- Port: `3008`
- Workers: `1`
- Reload: `True` (development mode)

---

#### `codereview/ai.py` - Abstract Base Class
**Location:** [codereview/ai.py](codereview/ai.py)

**Abstract Methods:**
```python
class AI(ABC):
    @abstractmethod
    def code_review(self, diff_content: str, model: str) -> str:
        """Generate code review for diff content"""
        pass

    @abstractmethod
    def get_access_token(self) -> str:
        """Get/renew API access token"""
        pass

    @abstractmethod
    def banner(self) -> str:
        """Return attribution banner text"""
        pass
```

---

#### `codereview/copilot.py` - Copilot AI Implementation
**Location:** [codereview/copilot.py](codereview/copilot.py)

**Key Changes (Post-Refactoring):**
- Constructor now accepts `Config` object instead of individual token
- Uses `load_prompt()` from `utils/prompt_loader.py` instead of hardcoded prompt
- Supports configurable LLM providers via `config.LLM_BASE_URL`
- Structured logging with `request_id`, `latency_ms`, `status`
- 60-second timeout on all requests
- Graceful error handling (skip to next file on timeout)

**Key Methods:**

| Method | Purpose |
|--------|---------|
| `__init__(config: Config)` | Initialize with Config object, validate LLM_API_KEY |
| `code_review(diff_content, model)` | Send diff to LLM API for review with structured logging |
| `get_access_token(renew=False)` | Get token from config or renew from API (Copilot-specific) |
| `banner` (property) | Returns "Power by GitHub Copilot" banner |

**API Configuration:**
- Base URL: From `config.LLM_BASE_URL` (default: `https://api.cocopilot.org`)
- Model: From `config.LLM_MODEL` (default: `gpt-4-0125-preview`)
- Max tokens: `4096`
- Temperature: `0.1`
- Timeout: `60 seconds`

**Structured Logging Example:**
```python
request_id = str(uuid.uuid4())
start_time = time.time()
# ... make request ...
latency_ms = int((time.time() - start_time) * 1000)
logger.bind(request_id=request_id, latency_ms=latency_ms, status="success").info("LLM request completed")
```

**Timeout Handling:**
```python
try:
    response = requests.post(url, headers=headers, json=data, timeout=60)
    # ...
except requests.Timeout:
    logger.bind(request_id=request_id, latency_ms=latency_ms, status="timeout").warning("LLM request timed out after 60 seconds")
    # Skip to next file
```

**Headers Required:**
```
Content-Type: application/json
Authorization: Bearer {access_token}
editor-version: vscode/1.91.0
editor-plugin-version: copilot-chat/0.16.1
```

---

#### `gitea/client.py` - Gitea API Client
**Location:** [gitea/client.py](gitea/client.py)

**Key Methods:**

| Method | Purpose |
|--------|---------|
| `get_diff_blocks(owner, repo, sha)` | Fetch and parse commit diff |
| `create_issue(owner, repo, title, body, ref, pusher)` | Create new issue |
| `add_issue_comment(owner, repo, issue_id, comment)` | Add comment to issue |

**Gitea API Endpoints Used:**
```
GET  /api/v1/repos/{owner}/{repo}/git/commits/{sha}.diff
POST /api/v1/repos/{owner}/{repo}/issues
POST /api/v1/repos/{owner}/{repo}/issues/{id}/comments
```

**Issue Creation Parameters:**
- `assignee`: `"jenkins"` (hardcoded)
- `assignees`: `[pusher]`
- `labels`: `[0]`
- `ref`: branch ref
- `title`: `"Code Review {commit_title}"`

**Diff Parsing:**
- Splits diff by `diff --git ` delimiter
- Filters out empty blocks
- Returns list of file-specific diff strings

---

#### `utils/config.py` - Configuration Management
**Location:** [utils/config.py](utils/config.py)

**Refactored Architecture:**
- All attributes use uppercase naming (Python convention)
- Strict priority for LLM authentication: `LLM_API_KEY > OPENAI_KEY > COPILOT_TOKEN`
- Deprecation warning when using legacy `OPENAI_KEY`
- Optional webhook configuration

**Environment Variables:**

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `GITEA_TOKEN` | Yes | - | Gitea API authentication token |
| `GITEA_HOST` | Yes | - | Gitea server host (e.g., `server:3000`) |
| `LLM_API_KEY` | Conditional* | - | Primary LLM API key (at least one auth method required) |
| `LLM_BASE_URL` | No | `https://api.cocopilot.org` | LLM API endpoint (enables provider switching) |
| `LLM_MODEL` | No | `gpt-4` | Model name for LLM requests |
| `LLM_PROVIDER` | No | `openai` | Provider identifier (for documentation) |
| `OPENAI_KEY` | No | - | Legacy OpenAI key (fallback, deprecated) |
| `COPILOT_TOKEN` | No | - | Legacy Copilot token (fallback) |
| `IGNORED_FILE_SUFFIX` | No | - | Comma-separated file suffixes to ignore |

**Webhook Configuration (Optional):**
| Variable | Purpose |
|----------|---------|
| `WEBHOOK_URL` | Notification webhook URL |
| `WEBHOOK_HEADER_NAME` | Custom header name |
| `WEBHOOK_HEADER_VALUE` | Custom header value |
| `WEBHOOK_REQUEST_BODY` | JSON template with `{content}` and `{mention}` placeholders |

**Validation:**
- Raises `ValueError` if `GITEA_TOKEN`, `GITEA_HOST` is missing
- Raises `ValueError` if no LLM authentication available (LLM_API_KEY, OPENAI_KEY, or COPILOT_TOKEN)

**Usage:**
```python
config = Config()
# Access via uppercase attributes
api_key = config.LLM_API_KEY
base_url = config.LLM_BASE_URL
model = config.LLM_MODEL
```

---

#### `utils/prompt_loader.py` - Prompt Loading Module
**Location:** [utils/prompt_loader.py](utils/prompt_loader.py)

**Purpose:** Load and parse prompt files from `./prompts/` directory with YAML front matter support and variable substitution.

**Key Functions:**

| Function | Purpose |
|----------|---------|
| `load_prompt(filename, context)` | Main function to load prompt content |
| `_strip_yaml_front_matter(content)` | Remove YAML metadata between `---` markers |
| `_substitute_variables(content, context)` | Replace `${variable}` placeholders |

**YAML Front Matter Example:**
```markdown
---
model: gpt-4-0125-preview
locale: zh-cn
temperature: 0.1
max_tokens: 4096
---

You are an AI programming assistant...
```

**Variable Substitution:**
- Placeholders use `${variable}` syntax
- Context dict provides values for substitution
- Default context values: `locale=zh-cn`, `input-focus=general best practices`

**Graceful Degradation:**
- On missing file: Logs WARNING, uses fallback prompt
- Fallback prompt: "You are a senior code reviewer. Please analyze the provided code diff."

**Usage Example:**
```python
from utils.prompt_loader import load_prompt

context = {
    "locale": "zh-cn",
    "input-focus": "security and performance",
    "model": "gpt-4"
}
system_prompt = load_prompt("code-review-pr.md", context)
```

---

#### `utils/logger.py` - Logging Configuration
**Location:** [utils/logger.py](utils/logger.py)

**Log Configuration:**
- **Console Output:**
  ```
  {time:YYYY-MM-DD HH:mm:ss} | {level} | {line} - {message}
  ```
- **File Output:** `./logs/app.log`
  - Rotation: `10 MB`
  - Retention: `10 days`
  - Compression: `zip`
- **Structured JSON Logging:** New formatter for LLM request tracking
  - Supports binding `request_id`, `latency_ms`, `status` via `logger.bind()`
  - Outputs JSON format for log aggregation

**Disabled Modules:** `httpcore`, `httpx`, `apscheduler`, `elastic_transport`, `sqlalchemy`

**Structured Logging Example:**
```python
from loguru import logger
import uuid

request_id = str(uuid.uuid4())
logger.bind(request_id=request_id, latency_ms=1250, status="success").info("LLM request completed")
# Output: {"timestamp": "...", "level": "INFO", "request_id": "...", "latency_ms": 1250, "status": "success", "message": "LLM request completed"}
```

---

#### `utils/utils.py` - Helper Functions
**Location:** [utils/utils.py](utils/utils.py)

```python
def extract_info_from_request(request_body):
    """Extract owner, repo, sha, ref, pusher, full_name, title, commit_url from webhook"""

def create_comment(file_name: str, diff_content: str, response: str) -> str:
    """Format comment as: 文件名：{file_name} 文件变更: {diff} 审查结果: {response}"""
```

---

### Current Dependencies
**From [requirements.txt](requirements.txt):**
```
fastapi>=0.111.0
requests>=2.32.3
loguru>=0.7.2
python-dotenv==1.0.1
openai>=1.0.0
uvicorn[standard]
pyyaml==6.0.1
```

---

### Docker Configuration

#### [Dockerfile](Dockerfile)
- Base: `python:3.10-slim`
- Workdir: `/app`
- Port: `3008`
- Cmd: `python main.py`

#### [docker-compose.yml](docker-compose.yml)
- Container: `gitea-ai-codereview`
- Network: `gitea_gitea` (external)
- Volumes:
  - `./main.py:/app/main.py` (hot-reload for development)
  - `./prompts:/app/prompts` (hot-reload for prompt changes)
- Port mapping: `3008:3008`
- Restart: `always`
- Environment: Passes `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, `LLM_PROVIDER` from `.env`

---

### Prompt Management

#### Prompt Directory Structure
```
prompts/
├── README.md                    # Documentation for prompt files
└── code-review-pr.md            # Default code review prompt
```

#### Prompt File Format
**YAML Front Matter (Metadata):**
```yaml
---
model: gpt-4-0125-preview
locale: zh-cn
temperature: 0.1
max_tokens: 4096
---
```

**Prompt Content:**
- Markdown-formatted instructions for the LLM
- Variable placeholders: `${locale}`, `${input-focus}`, `${model}`
- Loaded via `load_prompt(filename, context)` function

#### Hot-Reload Behavior
- Volume mount `./prompts:/app/prompts` enables instant updates
- Edit prompt file on host → container sees changes immediately
- No container restart required
- Next webhook trigger uses updated prompt

---

## Architecture Principles

### I. Configuration as Code
All environment-specific settings externalized to `.env` files. Single `Config` class using `python-dotenv` centralizes variable access. No hardcoded API keys, URLs, or model names in source code.

### II. Prompts as Data
AI system prompts stored in `./prompts/` directory as Markdown files. Loaded at runtime with YAML front matter support and variable substitution. Enables non-technical users to modify AI behavior without deployments.

### III. Container-First
Application runs inside Docker container. Development and production environments are identical. Volume mounts for prompt hot-reloading enable rapid iteration without rebuilds.

### IV. Graceful Degradation
Missing prompts trigger fallback with WARNING logs. Missing required configuration prevents startup with clear error messages. System continues operating on non-critical failures (timeouts skip to next file).

### V. OpenAI-Compatible API
LLM integration uses OpenAI client interface with `base_url` and `api_key` configuration. Enables compatibility with OpenAI, Azure OpenAI, local LLMs (Ollama, LocalAI), and enterprise proxies.

### VI. Modular Service Architecture
Clear module separation: configuration utilities, prompt loading, Gitea API client, and AI provider abstraction. Each module has independent testability.

---

## Spec-Driven Development (Spec Kit)

### References

- Constitution: [`.specify/memory/constitution.md`](.specify/memory/constitution.md)
- Spec Kit Framework: [`docs/Spec-Kit-Doc-Framework.md`](docs/Spec-Kit-Doc-Framework.md)
- Quick Reference: [`docs/Spec-Kit-Quick-Reference.md`](docs/Spec-Kit-Quick-Reference.md)
- Templates: [`.specify/templates/`](.specify/templates/)

### Claude Code Commands

- `/speckit.constitution [prompt]`
- `/speckit.specify [prompt]`
- `/speckit.clarify`
- `/speckit.plan [prompt]`
- `/speckit.tasks`
- `/speckit.implement`

### Document Separation (Constitution §VII)

|Document|Perspective|Content|Audience|
|---|---|---|---|
|**spec.md**|Product|User stories, requirements, success criteria|Product Owner, Stakeholders|
|**plan.md**|Engineering|Tech stack, architecture, implementation details|Developers, Tech Leads|

**VIOLATION:** Technical details in spec.md are a **merge blocker**. Spec.md reviews MUST verify technology-agnosticism.

---
## Claude Agents, Subagents & Skills

### Agent Discovery

Claude has access to pre-installed agents from the Claude Marketplace and project-specific agents/skills installed in the `.claude/` directory.

|Level|Location|Purpose|
|---||---|---|
|**User-level**|Claude Marketplace (pre-installed)|General-purpose capabilities|
|**Project-level**|`.claude/agents/`|Project-specific agents and skills|
|**Registry**|`.claude/agents/registry/REGISTRY.md`|Index of available project agents|

### Before Starting a Task

1. **Check the Registry** — Review `.claude/agents/registry/REGISTRY.md` for available agents
2. **Assess Parallelizability** — Determine if subtasks can run concurrently
3. **Select Appropriate Agent** — Match agent capabilities to task requirements

### Execution Model

|Task Type|Execution|Example|
|---|---|---|
|**Parallelizable**|Spawn multiple subagents concurrently|Running tests across modules, linting multiple files, independent API calls|
|**Sequential/Dependent**|Single agent or chained execution|Database migrations, stateful workflows, ordered transformations|
|**Specialized**|Delegate to domain-specific skill|LLM routing → specialized skill|

### Usage Guidelines

```
# Before complex tasks, consult the registry
→ Read .claude/agents/registry/REGISTRY.md

# For parallel-safe operations
→ Use subagents for concurrent execution

# For stateful or ordered operations
→ Use sequential execution with appropriate skill

# When uncertain about agent availability
→ Check registry before assuming capability exists
```

### Agent Selection Priority

1. **Project-level agents** (`.claude/agents/`) — Preferred for project-specific tasks
2. **User-level skills** — For general development tasks
3. **Built-in capabilities** — Fallback for standard operations

> **Note:** The `.claude/` directory is excluded from linting and formatting per Constitution §248-254.

---
## Feature Implementation System Guidelines

### Feature Implementation Priority Rules
- IMMEDIATE EXECUTION: Launch parallel Tasks immediately upon feature requests.
- NO CLARIFICATION: Skip asking what type of implementation unless absolutely critical.
- PARALLEL BY DEFAULT: Always use parallel methods for efficiency.

### Context Optimization Rules
- Strip out all comments when reading code files for analysis.
- Each task handles ONLY specified files or file types.

---

## Quick Reference Commands

```bash
# Development
python main.py                    # Run locally with uvicorn auto-reload
docker-compose up --build        # Build and run with Docker

# Testing
curl -X POST http://localhost:3008/test -d "your code here"

# Logs
tail -f ./logs/app.log           # View application logs
docker logs -f gitea-ai-codereview  # View container logs

# Environment
cp .env.example .env             # Create environment file
# Edit .env with your values
```

---

## Key Constants & Magic Numbers

| Location | Value | Purpose |
|----------|-------|---------|
| `main.py` | `1.5` | Sleep delay between API calls (seconds) |
| `copilot.py` | `4096` | max_tokens for API request |
| `copilot.py` | `0.1` | temperature for API request |
| `main.py` | `"[skip codereview]"` | Skip trigger string in commit title |
| `gitea/client.py` | `"jenkins"` | Default assignee for issues |
| `logger.py` | `"./logs/app.log"` | Log file path |
| `logger.py` | `"10 MB"` | Log rotation size |
| `logger.py` | `"10 days"` | Log retention period |
| `copilot.py` | `60` | LLM request timeout (seconds) |
| `prompt_loader.py` | `"zh-cn"` | Default locale for prompts |
| `prompt_loader.py` | `"general best practices"` | Default input-focus for prompts |

---

## Webhook Request Body Format

**Expected Gitea Webhook Payload:**
```json
{
  "repository": {
    "full_name": "owner/repo"
  },
  "after": "commit_sha",
  "ref": "refs/heads/main",
  "pusher": {
    "login": "username",
    "full_name": "Display Name"
  },
  "commits": [{
    "message": "Commit title",
    "url": "https://gitea.com/api/commit_url"
  }]
}
```

---

## Comment Template

**Format** ([`utils/utils.py`](utils/utils.py)):
```
文件名：{file_name}
文件变更:
```diff
{diff_content}
```
## 审查结果：
{response}
```

---

## Completed Refactoring (001-prompts-config-refactor)

### Summary
The codebase has been successfully refactored from a monolithic script with hardcoded prompts to a modular, containerized service with externalized prompt management and flexible LLM provider configuration.

### Key Changes
1. **Prompts Externalized**: System prompts moved from `copilot.py` to `prompts/code-review-pr.md`
2. **Config Class Refactored**: Added `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` with strict priority logic
3. **Prompt Loader Module**: Created `utils/prompt_loader.py` with YAML parsing and variable substitution
4. **Structured Logging**: Added JSON logging with `request_id`, `latency_ms`, `status` fields
5. **Docker Hot-Reload**: Added `./prompts` volume mount for instant prompt updates
6. **Multi-Provider Support**: Configurable LLM providers via environment variables

### Migration Guide
If upgrading from pre-refactor version:
1. Update `.env` file with new `LLM_*` variables (see `.env.example`)
2. Rename legacy `COPILOT_TOKEN` to `LLM_API_KEY` (or keep both for backward compatibility)
3. Copy any custom prompts from code to `prompts/` directory
4. Rebuild container: `docker-compose up --build`

### Related Documents
- Specification: [`specs/001-prompts-config-refactor/spec.md`](specs/001-prompts-config-refactor/spec.md)
- Implementation Plan: [`specs/001-prompts-config-refactor/plan.md`](specs/001-prompts-config-refactor/plan.md)
- Task Breakdown: [`specs/001-prompts-config-refactor/tasks.md`](specs/001-prompts-config-refactor/tasks.md)
