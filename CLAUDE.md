# CLAUDE.md - Project Context & Refactoring Instructions

## Project Overview
**Project Name:** Gitea AI Code Reviewer
**Repository:** `bestK/gitea-ai-codereview` (local fork)
**Purpose:** A lightweight, self-hosted Python bot that integrates with Gitea. It listens for Webhook events (Push commits), fetches code diffs, sends them to an LLM (Large Language Model) for analysis, and posts the review comments back to Gitea Issues.

**Tech Stack:**
- **Framework:** FastAPI (Uvicorn server)
- **Python:** 3.10+ (pyproject.toml specifies ^3.11)
- **AI Provider:** Copilot (cocopilot.org API) with OpenAI-compatible interface
- **Configuration:** python-dotenv
- **Logging:** loguru
- **Containerization:** Docker + docker-compose

---

## Current Architecture & Codebase Documentation

### Directory Structure
```
gitea-ai-codereview/
├── codereview/              # AI review layer
│   ├── __init__.py
│   ├── ai.py                # Abstract base class for AI providers
│   └── copilot.py           # Copilot AI implementation
├── gitea/                   # Gitea integration layer
│   ├── __init__.py
│   └── client.py            # Gitea API client
├── utils/                   # Utilities
│   ├── __init__.py
│   ├── config.py            # Configuration management
│   ├── logger.py            # Logging setup (loguru)
│   └── utils.py             # Helper functions
├── logs/                    # Application logs (gitignored)
├── docs/                    # Documentation
├── .env                     # Environment variables (secrets)
├── .env.example            # Example environment file
├── main.py                  # FastAPI application entry point
├── Dockerfile               # Container configuration
├── docker-compose.yml       # Docker orchestration
├── pyproject.toml          # Poetry project configuration
├── requirements.txt        # Python dependencies
└── CLAUDE.md               # This file
```

### File-by-File Documentation

#### `main.py` - FastAPI Application Entry Point
**Location:** `/home/jgrewal/projects/gitea-ai-codereview/main.py`

**Key Components:**
```python
# Global instances (lines 14-20)
app = FastAPI()
config = Config()
gitea_client = GiteaClient(config.gitea_host, config.gitea_token)
copilot = Copilot(config.copilot_token)
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
   - Check if file suffix is in `IGNORED_FILE_SUFFIX`
   - Send to AI for code review
   - First file: Create new Gitea Issue
   - Subsequent files: Add comments to issue
   - Sleep 1.5s between requests
5. Add AI banner to final issue comment
6. Optional: Send notification webhook

**Uvicorn Configuration:**
- Host: `0.0.0.0`
- Port: `3008`
- Workers: `1`
- Reload: `True` (development mode)

---

#### `codereview/ai.py` - Abstract Base Class
**Location:** `/home/jgrewal/projects/gitea-ai-codereview/codereview/ai.py`

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
**Location:** `/home/jgrewal/projects/gitea-ai-codereview/codereview/copilot.py`

**Hardcoded System Prompt (lines 43-44):**
```
You are an AI programming assistant.
When asked for your name, you must respond with "GitHub Copilot".
Follow the user's requirements carefully & to the letter.
...
Respond in the following locale: zh-cn
```

**Key Methods:**

| Method | Purpose |
|--------|---------|
| `__init__(copilot_token)` | Initialize and get initial access token |
| `code_review(diff_content, model)` | Send diff to Copilot API for review |
| `get_access_token(renew=False)` | Get token from .env or renew from API |
| `banner` (property) | Returns "Power by GitHub Copilot" banner |

**API Endpoint:** `https://api.cocopilot.org/chat/completions`
**Token Endpoint:** `https://api.cocopilot.org/copilot_internal/v2/token`

**Request Parameters:**
- `model`: `"gpt-4-0125-preview"` (default)
- `max_tokens`: `4096`
- `temperature`: `0.1`
- `top_p`: `1`
- `stream`: `False`

**Headers Required:**
```
Content-Type: application/json
Authorization: Bearer {access_token}
editor-version: vscode/1.91.0
editor-plugin-version: copilot-chat/0.16.1
```

**Token Refresh Logic:**
- On 401 response: Call `get_access_token(renew=True)`
- New token is saved to `.env` file using `set_key()`
- Request is retried with new token

---

#### `gitea/client.py` - Gitea API Client
**Location:** `/home/jgrewal/projects/gitea-ai-codereview/gitea/client.py`

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
**Location:** `/home/jgrewal/projects/gitea-ai-codereview/utils/config.py`

**Environment Variables Required:**

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `GITEA_TOKEN` | Yes | - | Gitea API authentication token |
| `GITEA_HOST` | Yes | - | Gitea server host (e.g., `server:3000`) |
| `COPILOT_TOKEN` | Yes | - | Copilot authentication token |
| `OPENAI_KEY` | No | - | OpenAI API key (auto-renewed) |
| `IGNORED_FILE_SUFFIX` | No | - | Comma-separated file suffixes to ignore |

**Webhook Configuration (Optional):**
| Variable | Purpose |
|----------|---------|
| `WEBHOOK_URL` | Notification webhook URL |
| `WEBHOOK_HEADER_NAME` | Custom header name |
| `WEBHOOK_HEADER_VALUE` | Custom header value |
| `WEBHOOK_REQUEST_BODY` | JSON template with `{content}` and `{mention}` placeholders |

**Validation:**
- Raises `ValueError` if `GITEA_TOKEN`, `GITEA_HOST`, or `COPILOT_TOKEN` is missing

---

#### `utils/utils.py` - Helper Functions
**Location:** `/home/jgrewal/projects/gitea-ai-codereview/utils/utils.py`

```python
def extract_info_from_request(request_body):
    """Extract owner, repo, sha, ref, pusher, full_name, title, commit_url from webhook"""

def create_comment(file_name: str, diff_content: str, response: str) -> str:
    """Format comment as: 文件名：{file_name} 文件变更: {diff} 审查结果: {response}"""
```

---

#### `utils/logger.py` - Logging Configuration
**Location:** `/home/jgrewal/projects/gitea-ai-codereview/utils/logger.py`

**Log Configuration:**
- **Console Output:**
  ```
  {time:YYYY-MM-DD HH:mm:ss} | {level} | {line} - {message}
  ```
- **File Output:** `./logs/app.log`
  - Rotation: `10 MB`
  - Retention: `10 days`
  - Compression: `zip`
- **Disabled Modules:** `httpcore`, `httpx`, `apscheduler`, `elastic_transport`, `sqlalchemy`

---

### Current Dependencies
**From `requirements.txt`:**
```
fastapi>=0.111.0
requests>=2.32.3
loguru>=0.7.2
python-dotenv>=1.0.0
uvicorn[standard]
pyyaml
```

---

### Docker Configuration

#### `Dockerfile`
- Base: `python:3.10-slim`
- Workdir: `/app`
- Port: `3008`
- Cmd: `python main.py`

#### `docker-compose.yml`
- Container: `gitea-ai-codereview`
- Network: `gitea_gitea` (external)
- Volume: `./main.py:/app/main.py` (hot-reload)
- Port mapping: `3008:3008`
- Restart: `always`

**Missing:** No `./prompts` volume mount (needs to be added)

---

### Current Issues & Refactoring Needs

1. **Hardcoded Prompt in `copilot.py:43-44`**
   - The entire system prompt is hardcoded as a multi-line string
   - Cannot be modified without code changes
   - Chinese locale is hardcoded (`zh-cn`)

2. **Limited LLM Provider Support**
   - Only supports Copilot API (`cocopilot.org`)
   - No configurable `BASE_URL` for other providers
   - `LLM_MODEL` is not configurable (hardcoded to `gpt-4-0125-preview`)

3. **No Prompt Management System**
   - No `prompts/` directory
   - No YAML front matter support
   - No variable substitution

4. **Missing Configuration Options**
   - No `LLM_PROVIDER` env var
   - No `LLM_BASE_URL` env var
   - No `LLM_MODEL` env var
   - No backward compatibility fallback logic

---

## Refactoring Goals
You are tasked with transforming the codebase to meet the following three primary objectives:

### 1. Externalize Prompt Management
Move the System Prompt logic out of `main.py` and into the filesystem.
*   Create a directory `./prompts/`.
*   Load prompts from Markdown files (e.g., `./prompts/code-review-pr.md`).
*   Implement a parser to strip **YAML Front Matter** (metadata between `---` markers) from the markdown files.
*   Implement **Variable Substitution**: The system must replace placeholders (e.g., `${input-focus}`) with actual values defined in the code or environment.

### 2. Flexible Configuration (`.env`)
Standardize configuration using `python-dotenv`.
*   Create a `Config` class to centralize environment variable loading.
*   Support for `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, and `LLM_PROVIDER`.
*   Ensure backward compatibility (e.g., check for `OPENAI_KEY` if `LLM_API_KEY` is missing).

### 3. Dockerization & Hot-Reloading
Implement the specific Docker setup provided below.
*   Create a `Dockerfile` based on Python 3.10-slim.
*   Create a `docker-compose.yml` that mounts the `prompts/` directory and `main.py` so changes on the host reflect immediately in the container without rebuilding.

---

## Implementation Instructions

### Step 1: Update Dependencies
Ensure `requirements.txt` includes the following. Add them if missing:
```text
openai>=1.0.0
python-dotenv>=1.0.0
flask  # (or fastapi/starlette, depending on existing code)
gunicorn # (standard for production wsgi)
```

### Step 2: Implement Configuration Logic
In `main.py`, replace direct `os.getenv` calls with a centralized configuration structure.

**Action:** Create/Update the Config class:
```python
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # LLM Settings
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
    LLM_API_KEY = os.getenv("LLM_API_KEY", os.getenv("OPENAI_KEY")) # Backward compat
    LLM_BASE_URL = os.getenv("LLM_BASE_URL") # Critical for local/proxy LLMs
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4")
    
    # Gitea Settings
    GITEA_HOST = os.getenv("GITEA_HOST")
    GITEA_TOKEN = os.getenv("GITEA_TOKEN")
    
    # App Settings
    IGNORED_SUFFIX = os.getenv("IGNORED_FILE_SUFFIX", ".json,.md,.lock")

config = Config()
```

**Action:** Update the LLM Client initialization (e.g., OpenAI client) to use this config:
```python
from openai import OpenAI

client = OpenAI(
    api_key=config.LLM_API_KEY,
    base_url=config.LLM_BASE_URL if config.LLM_BASE_URL else None
)
```

### Step 3: Implement Prompt Loader
Create a robust function to load and parse the markdown prompts.

**Action:** Add this function to `main.py`:
```python
import os

def load_prompt(filename, context=None):
    """
    Loads a prompt from a markdown file, strips YAML front matter,
    and replaces template variables (e.g., ${key}).
    """
    if context is None:
        context = {}
    
    # Default context values
    context.setdefault('focus', 'general best practices, security, and performance')

    file_path = os.path.join(os.path.dirname(__file__), 'prompts', filename)

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 1. Strip YAML Front Matter
        if content.startswith('---'):
            parts = content.split('---')
            if len(parts) >= 3:
                content = parts[2].strip()
            else:
                content = content.split('---', 1)[-1].strip()

        # 2. Variable Substitution
        for key, value in context.items():
            placeholder = f"${{{key}}}"
            content = content.replace(placeholder, str(value))

        return content

    except FileNotFoundError:
        print(f"Warning: Prompt file {file_path} not found. Using fallback.")
        return "You are a senior code reviewer. Please analyze the provided code diff."
```

**Action:** Integrate this into the review generation logic.
Instead of:
```python
messages = [{"role": "system", "content": "You are a helpful assistant..."}]
```
Use:
```python
system_instruction = load_prompt('code-review-pr.md')
messages = [{"role": "system", "content": system_instruction}, ...]
```

### Step 4: Create Docker Artifacts
Create the following files in the project root exactly as specified.

#### `Dockerfile`
```dockerfile
# Use an official lightweight Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port
EXPOSE 3008

# Command to run the application
CMD ["python", "main.py"]
```

#### `docker-compose.yml`
```yaml
---
services:
  ai-codereview:
    build: .
    container_name: gitea-ai-codereview
    restart: always
    env_file: .env
    networks:
      gitea_gitea:
    ports:
      - "3008:3008"
    environment:
      - GITEA_HOST=http://server:3000
      - GITEA_TOKEN=${GITEA_TOKEN}
      - LLM_PROVIDER=${LLM_PROVIDER:-openai}
      - LLM_API_KEY=${LLM_API_KEY}
      - LLM_BASE_URL=${LLM_BASE_URL}
      - LLM_MODEL=${LLM_MODEL}
      - IGNORED_FILE_SUFFIX=${IGNORED_FILE_SUFFIX:-.json,.md,.lock,.png,.jpg,.svg,.map}
    extra_hosts:
      - "host.docker.internal:host-gateway"
    volumes:
      - ./main.py:/app/main.py
      - ./prompts:/app/prompts
networks:
  gitea_gitea:
    external: true
```

#### `.env` Example (Create if not exists)
```bash
LLM_PROVIDER=openai
LLM_API_KEY=sk-...
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4
GITEA_TOKEN=your_gitea_token
GITEA_HOST=http://server:3000
```

### Step 5: Create Default Prompt
Ensure the directory `./prompts/` exists. Create `./prompts/code-review-pr.md` with the improved prompt content provided in the context (including the `---` YAML headers).


---

## Spec-Driven Development (Spec Kit)

### References

- Constitution: `./.specify/memory/constitution.md`
- Spec Kit Framework: `./docs/Spec-Kit-Doc-Framework.md`
- Quick Reference: `./docs/Spec-Kit-Quick-Reference.md`
- Templates: `.specify/templates/`

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
|---|---|---|
|**User-level**|Claude Marketplace (pre-installed)|General-purpose capabilities|
|**Project-level**|`.claude/agents/`|ThinkEven-specific agents and skills|
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
|**Specialized**|Delegate to domain-specific skill|Neo4j queries → KG agent, LLM routing → RouteLLM skill|

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

1. **Project-level agents** (`.claude/agents/`) — Preferred for ThinkEven-specific tasks
2. **User-level skills** — For general development tasks
3. **Built-in capabilities** — Fallback for standard operations

> **Note:** The `.claude/` directory is excluded from linting and formatting per Constitution §248-254.

---
## Feature Implementation System Guidelines

### Feature Implementation Priority Rules
- IMMEDIATE EXECUTION: Launch parallel Tasks immediately upon feature requests.
- NO CLARIFICATION: Skip asking what type of implementation unless absolutely critical.
- PARALLEL BY DEFAULT: Always use 7-parallel-Task method for efficiency.

### Parallel Feature Implementation Workflow
1. **Component:** Create main component file.
2. **Styles:** Create component styles/CSS.
3. **Tests:** Create test files.
4. **Types:** Create type definitions.
5. **Hooks:** Create custom hooks/utilities.
6. **Integration:** Update routing, imports, exports.
7. **Remaining:** Update package.json, documentation, configuration files.
8. **Review and Validation:** Coordinate integration, run tests, verify build, check for conflicts.

### Context Optimization Rules
- Strip out all comments when reading code files for analysis.
- Each task handles ONLY specified files or file types.
## Success Criteria

The refactoring is complete when:
1.  **No Hardcoded Prompts:** `main.py` contains no large multi-line prompt strings; it uses `load_prompt`.
2.  **Configuration Loading:** The app successfully reads `LLM_BASE_URL` from `.env` and connects to a custom URL if provided.
3.  **YAML Parsing:** The app loads the markdown file, strips the top `---` block, and the AI receives only the instruction text.
4.  **Docker Build:** `docker-compose up --build` runs successfully.
5.  **Hot Reloading:** Editing `./prompts/code-review-pr.md` on the host machine updates the bot's behavior immediately (on the next PR) without restarting the container.

---

## Code Modification Reference

### Files That Need Modification

| File | Modification Type | Specific Changes |
|------|-------------------|------------------|
| `utils/config.py` | **Modify** | Add `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_MODEL` with backward compat |
| `codereview/copilot.py` | **Modify** | Replace hardcoded prompt (line 43-44) with `load_prompt()` call |
| `codereview/copilot.py` | **Modify** | Make `BASE_URL` configurable via Config class |
| `codereview/copilot.py` | **Modify** | Make `model` parameter configurable |
| `main.py` | **Modify** | Update `Copilot` instantiation to use Config values |
| `docker-compose.yml` | **Modify** | Add `./prompts:/app/prompts` volume mount |
| `prompts/code-review-pr.md` | **Create** | Extract hardcoded prompt into new file |

### Hardcoded Prompt to Extract

**Current Location:** `codereview/copilot.py` lines 43-44

**Content to extract to `prompts/code-review-pr.md`:**
```markdown
---
model: gpt-4-0125-preview
locale: zh-cn
temperature: 0.1
max_tokens: 4096
---

You are an AI programming assistant.
When asked for your name, you must respond with "GitHub Copilot".
Follow the user's requirements carefully & to the letter.
Follow Microsoft content policies.
Avoid content that violates copyrights.
If you are asked to generate content that is harmful, hateful, racist, sexist, lewd, violent, or completely irrelevant to software engineering, only respond with "Sorry, I can't assist with that."
Keep your answers short and impersonal.
You can answer general programming questions and perform the following tasks:
* Ask a question about the files in your current workspace
* Explain how the code in your active editor works
* Review the selected code in your active editor
* Generate unit tests for the selected code
* Propose a fix for the problems in the selected code
* Scaffold code for a new workspace
* Create a new Jupyter Notebook
* Find relevant code to your query
* Propose a fix for the a test failure
* Ask questions about VS Code
* Generate query parameters for workspace search
* Ask about VS Code extension development
* Ask how to do something in the terminal
* Explain what just happened in the terminal
You use the GPT-4 Turbo version of OpenAI's GPT models.
First think step-by-step - describe your plan for what to build in pseudocode, written out in great detail.
Then output the code in a single code block.
Minimize any other prose.
Use Markdown formatting in your answers.
Make sure to include the programming language name at the start of the Markdown code blocks.
Avoid wrapping the whole response in triple backticks.
The user works in an IDE called Visual Studio Code which has a concept for editors with open files, integrated unit test support, an output pane that shows the output of running the code as well as an integrated terminal.
The user is working on a Windows machine. Please respond with system specific commands if applicable.
The active document is the source code the user is looking at right now.
You can only give one reply for each conversation turn.
Respond in the following locale: ${locale}
```

### Webhook Request Body Format

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

### Comment Template

**Current format** (`utils/utils.py:16-17`):
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
| `main.py:99` | `1.5` | Sleep delay between API calls (seconds) |
| `copilot.py:52` | `4096` | max_tokens for API request |
| `copilot.py:53` | `0.1` | temperature for API request |
| `main.py:32` | `"[skip codereview]"` | Skip trigger string in commit title |
| `gitea/client.py:32` | `"jenkins"` | Default assignee for issues |
| `logger.py:60` | `"./logs/app.log"` | Log file path |
| `logger.py:63` | `"10 MB"` | Log rotation size |
| `logger.py:64` | `"10 days"` | Log retention period |

