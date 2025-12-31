# Gitea AI Code Reviewer - Existing Code Documentation

**Version:** 0.1.0
**Documentation Date:** 2025-12-31
**Status:** Pre-Refactoring Reference

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Directory Structure](#directory-structure)
4. [Module Documentation](#module-documentation)
5. [API Reference](#api-reference)
6. [Configuration](#configuration)
7. [Data Flow](#data-flow)
8. [Dependencies](#dependencies)
9. [Deployment](#deployment)
10. [Known Issues & Limitations](#known-issues--limitations)

---

## Project Overview

### Purpose
A lightweight, self-hosted Python bot that integrates with Gitea to provide automated code reviews using Large Language Models (LLMs). The application listens for Gitea webhook events (push commits), fetches code diffs, sends them to an AI service for analysis, and posts review comments as Gitea Issues.

### Technology Stack

| Component | Technology | Version |
|-----------|------------|---------|
| **Language** | Python | ^3.11 (pyproject.toml) / 3.10+ (Dockerfile) |
| **Web Framework** | FastAPI | ^0.111.0 |
| **ASGI Server** | Uvicorn | ^0.30.1 |
| **HTTP Client** | Requests | ^2.32.3 |
| **Configuration** | python-dotenv | ^1.0.1 |
| **Logging** | loguru | ^0.7.2 |
| **YAML Parsing** | PyYAML | ^6.0.1 |
| **Containerization** | Docker | python:3.10-slim |

### Key Features
- Automated code review on push events
- Gitea Issue creation with review comments
- File type filtering (ignore specific file extensions)
- Webhook notification support
- Copilot AI integration with automatic token refresh
- Chinese language support (hardcoded)

### Current Limitations
- Hardcoded system prompts in code
- Limited to Copilot API (cocopilot.org)
- No configurable LLM provider support
- Chinese locale hardcoded
- No external prompt management
- Limited configuration options

---

## Architecture

### System Architecture Diagram

```
┌─────────────────┐     Webhook      ┌──────────────────────────┐
│     Gitea       │ ────────────────> │  FastAPI (main.py)       │
│   (Server)      │   POST /codereview│  Port: 3008              │
└─────────────────┘                  └──────────┬───────────────┘
                                                 │
                                                 ▼
                                      ┌──────────────────────────┐
                                      │  Request Processing      │
                                      │  - Extract info          │
                                      │  - Skip if [skip review] │
                                      │  - Get diff blocks       │
                                      └──────────┬───────────────┘
                                                 │
                    ┌────────────────────────────┼────────────────────────────┐
                    │                            │                            │
                    ▼                            ▼                            ▼
        ┌───────────────────┐       ┌─────────────────────┐    ┌───────────────────┐
        │   GiteaClient     │       │      Copilot        │    │   Webhook Notify  │
        │   (gitea/)        │       │   (codereview/)     │    │   (Optional)      │
        ├───────────────────┤       ├─────────────────────┤    ├───────────────────┤
        │ • get_diff_blocks │       │ • code_review()     │    │ • POST to URL     │
        │ • create_issue    │       │ • get_access_token  │    │ • Custom headers  │
        │ • add_comment     │       │ • Auto-token refresh│    │                   │
        └───────────────────┘       └─────────────────────┘    └───────────────────┘
                    │                            │
                    └────────────┬───────────────┘
                                 ▼
                      ┌─────────────────────┐
                      │   Copilot API       │
                      │  (cocopilot.org)    │
                      │  - GPT-4 Turbo      │
                      └─────────────────────┘
```

### Component Interaction

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              main.py                                       │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                │
│  │   FastAPI    │───>│    Config    │───>│ GiteaClient  │                │
│  │   (app)      │    │   (config)   │    │  (gitea_*)    │                │
│  └──────────────┘    └──────────────┘    └──────────────┘                │
│         │                                    │                            │
│         └────────────────────────────────────┼──────────────┐             │
│                                              │              │             │
│                                              ▼              ▼             │
│                                    ┌──────────────┐  ┌──────────────┐   │
│                                    │   Copilot    │  │  Webhook     │   │
│                                    │  (copilot)   │  │  (notify)    │   │
│                                    └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Design Patterns

| Pattern | Usage | Location |
|---------|-------|----------|
| **Abstract Base Class** | AI provider abstraction | `codereview/ai.py` |
| **Singleton-like** | Global config/instances | `main.py:14-20` |
| **Factory Pattern** | Webhook notification config | `utils/config.py:31-40` |

---

## Directory Structure

```
gitea-ai-codereview/
├── codereview/                    # AI Review Layer
│   ├── __init__.py               # (Missing - should export AI classes)
│   ├── ai.py                     # Abstract base class for AI providers
│   └── copilot.py                # Copilot AI implementation
│
├── gitea/                         # Gitea Integration Layer
│   ├── __init__.py               # (Missing - should export client)
│   └── client.py                 # Gitea API client wrapper
│
├── utils/                         # Utilities Layer
│   ├── __init__.py               # Empty package marker
│   ├── config.py                 # Configuration management (Env vars)
│   ├── logger.py                 # Logging setup (loguru wrapper)
│   └── utils.py                  # Helper functions
│
├── logs/                          # Application Logs (gitignored)
│   └── app.log                   # Rotating log file
│
├── docs/                          # Documentation
│   └── OLD_Documentation.md      # This file
│
├── .env                           # Environment Variables (SECRETS - not in git)
├── .env.example                   # Example environment file template
├── .gitignore                     # Git ignore patterns
├── CLAUDE.md                      # Claude Code project instructions
├── Dockerfile                     # Docker image definition
├── docker-compose.yml             # Docker orchestration
├── main.py                        # FastAPI application entry point
├── pyproject.toml                 # Poetry project configuration
├── requirements.txt               # Python dependencies
├── README.md                      # User documentation
├── README.md.old                  # Previous README version
└── README.zh.md                   # Chinese documentation
```

---

## Module Documentation

### `main.py` - Application Entry Point

**File:** `/home/jgrewal/projects/gitea-ai-codereview/main.py`

**Purpose:** FastAPI application that serves as the webhook receiver and orchestrates the code review workflow.

#### Global Instances

```python
app = FastAPI()                              # FastAPI application instance
config = Config()                            # Configuration instance
gitea_clinet = GiteaClient(...)             # Gitea API client
copilot = Copilot(config.copilot_token)     # Copilot AI instance
```

#### API Endpoints

##### `POST /codereview`
**Purpose:** Primary webhook endpoint for Gitea push events

**Request Flow:**
```
1. Extract info from webhook payload
2. Check for [skip codereview] in commit title
3. Fetch diff blocks from Gitea
4. For each diff block:
   a. Check file suffix against ignored list
   b. Send to AI for code review
   c. First file: Create new Gitea Issue
   d. Subsequent files: Add comment to issue
   e. Sleep 1.5 seconds (rate limiting)
5. Add AI banner to issue
6. Send notification webhook (if configured)
```

**Request Body (Gitea Push Event):**
```json
{
  "repository": {
    "full_name": "owner/repo"
  },
  "after": "commit_sha_hash",
  "ref": "refs/heads/main",
  "pusher": {
    "login": "username",
    "full_name": "Display Name"
  },
  "commits": [{
    "message": "Commit title here",
    "url": "https://gitea.com/api/commit_url"
  }]
}
```

**Skip Condition:** If commit title contains `[skip codereview]`, returns immediately with `{"message": "Skip codereview"}`

**Ignored Files:** Files matching suffixes in `IGNORED_FILE_SUFFIX` env var (default: `.json,.md,.lock`)

##### `POST /test`
**Purpose:** Manual testing endpoint for code review

**Request Body:** String containing code to review

**Response:** `{"message": "<AI review response>"}`

#### Uvicorn Configuration

```python
serv_config = uvicorn.Config(
    "main:app",           # Application import path
    host="0.0.0.0",       # Listen on all interfaces
    port=3008,            # Port number
    access_log=True,      # Enable access logging
    workers=1,            # Single worker process
    reload=True,          # Auto-reload on code changes (dev mode)
)
```

---

### `codereview/ai.py` - Abstract Base Class

**File:** `/home/jgrewal/projects/gitea-ai-codereview/codereview/ai.py`

**Purpose:** Defines the interface for AI provider implementations.

#### Abstract Methods

```python
from abc import ABC, abstractmethod

class AI(ABC):
    @abstractmethod
    def code_review(self, diff_content: str, model: str) -> str:
        """
        Generate code review for diff content.

        Args:
            diff_content: The code diff to review
            model: The model identifier to use

        Returns:
            str: The AI-generated review text
        """
        pass

    @abstractmethod
    def get_access_token(self) -> str:
        """
        Get or renew API access token.

        Returns:
            str: Valid access token for API requests
        """
        pass

    @abstractmethod
    def banner(self) -> str:
        """
        Return attribution banner text.

        Returns:
            str: Banner text to append to review comments
        """
        pass
```

**Implementing Classes:** `Copilot` in `codereview/copilot.py`

---

### `codereview/copilot.py` - Copilot AI Implementation

**File:** `/home/jgrewal/projects/gitea-ai-codereview/codereview/copilot.py`

**Purpose:** Concrete implementation of AI interface using Copilot API (cocopilot.org).

#### Class: `Copilot(AI)`

##### Constructor
```python
def __init__(self, copilot_token: str):
    """
    Initialize Copilot AI instance.

    Args:
        copilot_token: Copilot authentication token

    Raises:
        ValueError: If copilot_token is None or empty

    Side Effects:
        - Stores copilot_token
        - Calls get_access_token() to obtain initial access token
    """
```

##### Method: `code_review(diff_content: str, model: str = "gpt-4-0125-preview") -> str`

**Purpose:** Send code diff to Copilot API for review

**API Endpoint:** `https://api.cocopilot.org/chat/completions`

**Request Headers:**
```python
{
    "Content-Type": "application/json",
    "Authorization": f"Bearer {self.access_token}",
    "editor-version": "vscode/1.91.0",
    "editor-plugin-version": "copilot-chat/0.16.1",
}
```

**Request Body:**
```json
{
  "messages": [
    {
      "role": "system",
      "content": "<HARDCODED_SYSTEM_PROMPT>"
    },
    {
      "role": "user",
      "content": "<diff_content> Code review"
    }
  ],
  "model": "gpt-4-0125-preview",
  "max_tokens": 4096,
  "temperature": 0.1,
  "top_p": 1,
  "n": 1,
  "stream": false
}
```

**Hardcoded System Prompt (lines 43-44):**
```
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
Respond in the following locale: zh-cn
```

**Error Handling:**
- **401 Unauthorized:** Calls `get_access_token(renew=True)`, updates token, retries request
- **Other Errors:** Logs error, returns raw response text

**Returns:** AI-generated review text as string

##### Method: `get_access_token(renew: bool = False) -> str`

**Purpose:** Get or renew Copilot API access token

**Token Endpoint:** `https://api.cocopilot.org/copilot_internal/v2/token`

**Headers:**
```python
{
    "Content-Type": "application/json",
    "Authorization": f"token {self.copilot_token}",
    "editor-version": "vscode/1.91.0",
    "editor-plugin-version": "copilot-chat/0.16.1",
}
```

**Behavior:**
| renew | Behavior |
|-------|----------|
| `False` | Reads `OPENAI_KEY` from `.env` file |
| `True` | Fetches new token from API, saves to `.env` via `set_key()` |

**Returns:** Access token string

**Raises:** `Exception` if token fetch fails

##### Property: `banner -> str`

**Returns:** `"## Power by \n ![GitHub_Copilot_logo](/attachments/c99d46b9-d26f-4859-ad4f-d77650b27f8e)"`

---

### `gitea/client.py` - Gitea API Client

**File:** `/home/jgrewal/projects/gitea-ai-codereview/gitea/client.py`

**Purpose:** Wrapper for Gitea API operations (fetching diffs, creating issues, adding comments).

#### Class: `GiteaClient`

##### Constructor
```python
def __init__(self, host: str, token: str):
    """
    Initialize Gitea API client.

    Args:
        host: Gitea server host (e.g., "server:3000" or "gitea.example.com")
        token: Gitea API access token
    """
```

##### Method: `get_diff_blocks(owner: str, repo: str, sha: str) -> List[str]`

**Purpose:** Fetch and parse commit diff

**API Endpoint:** `GET /api/v1/repos/{owner}/{repo}/git/commits/{sha}.diff?access_token={token}`

**Returns:** List of diff blocks (one per file)

**Parsing Logic:**
```python
# Split diff by "diff --git " delimiter
diff_blocks = re.split("diff --git ", res.text.strip())
# Filter empty blocks
diff_blocks = [block for block in diff_blocks if block]
# Remove prefix from each block
diff_blocks = [block.replace("diff --git ", "") for block in diff_blocks]
```

**Error Handling:** Returns `None` on failure, logs error

##### Method: `create_issue(owner: str, repo: str, title: str, body: str, ref: str, pusher: str)`

**Purpose:** Create a new issue in Gitea

**API Endpoint:** `POST /api/v1/repos/{owner}/{repo}/issues?access_token={token}`

**Request Body:**
```json
{
  "assignee": "jenkins",
  "assignees": ["<pusher>"],
  "body": "<issue body>",
  "closed": false,
  "due_date": null,
  "labels": [0],
  "milestone": 0,
  "ref": "<branch_ref>",
  "title": "<issue title>"
}
```

**Hardcoded Values:**
- `assignee`: `"jenkins"`
- `labels`: `[0]`
- `milestone`: `0`

**Returns:** API response JSON on success (status 201), `None` on failure

##### Method: `add_issue_comment(owner: str, repo: str, issue_id: int, comment: str)`

**Purpose:** Add comment to existing issue

**API Endpoint:** `POST /api/v1/repos/{owner}/{repo}/issues/{issue_id}/comments?access_token={token}`

**Request Body:**
```json
{
  "body": "<comment text>"
}
```

**Returns:** API response JSON on success (status 201), `None` on failure

##### Static Method: `extract_info_from_request(request_body: Dict) -> Tuple`

**Purpose:** Extract relevant information from Gitea webhook payload

**Returns:** `(owner, repo, sha, ref, pusher, full_name, title, commit_url)`

**Note:** This method is duplicated in `utils/utils.py`

---

### `utils/config.py` - Configuration Management

**File:** `/home/jgrewal/projects/gitea-ai-codereview/utils/config.py`

**Purpose:** Centralized configuration loading from environment variables.

#### Class: `Config`

##### Constructor
```python
def __init__(self, config_file=None):
    """
    Load configuration from .env file.

    Args:
        config_file: Optional path to custom .env file

    Raises:
        ValueError: If required environment variables are missing
    """
```

**Required Environment Variables:**
| Variable | Description |
|----------|-------------|
| `GITEA_TOKEN` | Gitea API authentication token |
| `GITEA_HOST` | Gitea server host address |
| `COPILOT_TOKEN` | Copilot authentication token |

**Optional Environment Variables:**
| Variable | Description |
|----------|-------------|
| `OPENAI_KEY` | OpenAI API key (auto-managed by Copilot) |
| `IGNORED_FILE_SUFFIX` | Comma-separated file suffixes to ignore |

#### Class: `Webhook`

**Purpose:** Webhook notification configuration

**Attributes:**
```python
url: str                    # Webhook URL
header_name: str            # Custom header name
header_value: str           # Custom header value
request_body: str           # JSON template with {content} and {mention} placeholders
```

**Property:** `is_init -> bool`
Returns `True` if both `url` and `request_body` are set

---

### `utils/logger.py` - Logging Configuration

**File:** `/home/jgrewal/projects/gitea-ai-codereview/utils/logger.py`

**Purpose:** Centralized logging setup using loguru.

#### Class: `InterceptHandler(logging.Handler)`

**Purpose:** Intercept standard Python logging and redirect to loguru

#### Configuration

**Console Output:**
```
<white>{time:YYYY-MM-DD HH:mm:ss}</white> | <level>{level: <8}</level> | <cyan><b>{line}</b></cyan> - <white><b>{message}</b></white>
```

**File Output:** `./logs/app.log`
- Rotation: `10 MB`
- Retention: `10 days`
- Compression: `zip`
- Level: `DEBUG`

**Disabled Modules:** `httpcore`, `httpx`, `apscheduler`, `elastic_transport`, `sqlalchemy`

#### Functions

| Function | Purpose |
|----------|---------|
| `stop_logging()` | Disable logging for specified modules |
| `setup_logging()` | Configure loguru handlers and intercept stdlib logging |

---

### `utils/utils.py` - Helper Functions

**File:** `/home/jgrewal/projects/gitea-ai-codereview/utils/utils.py`

#### Function: `extract_info_from_request(request_body: Dict) -> Tuple`

**Purpose:** Extract information from Gitea webhook payload

**Returns:** `(owner, repo, sha, ref, pusher, full_name, title, commit_url)`

**Note:** Duplicate of `gitea/client.extract_info_from_request()`

#### Function: `create_comment(file_name: str, diff_content: str, response: str) -> str`

**Purpose:** Format review comment for Gitea issue

**Returns:**
```
文件名：{file_name}
文件变更:
```
{diff_content}
```
## 审查结果：
{response}
```

---

## API Reference

### FastAPI Endpoints

#### `POST /codereview`
Webhook receiver for Gitea push events.

**Request:**
```json
{
  "repository": {
    "full_name": "owner/repo"
  },
  "after": "sha",
  "ref": "refs/heads/main",
  "pusher": {
    "login": "username",
    "full_name": "Display Name"
  },
  "commits": [{
    "message": "title",
    "url": "commit_url"
  }]
}
```

**Response:** `{"message": "review_result"}`

#### `POST /test`
Manual testing endpoint.

**Request:** Raw string (code to review)

**Response:** `{"message": "ai_response"}`

### External APIs Used

#### Copilot API (cocopilot.org)

**Chat Completions:**
```
POST https://api.cocopilot.org/chat/completions
Headers:
  - Authorization: Bearer {access_token}
  - editor-version: vscode/1.91.0
  - editor-plugin-version: copilot-chat/0.16.1
```

**Token Refresh:**
```
GET https://api.cocopilot.org/copilot_internal/v2/token
Headers:
  - Authorization: token {copilot_token}
  - editor-version: vscode/1.91.0
  - editor-plugin-version: copilot-chat/0.16.1
```

#### Gitea API

**Get Commit Diff:**
```
GET /api/v1/repos/{owner}/{repo}/git/commits/{sha}.diff?access_token={token}
```

**Create Issue:**
```
POST /api/v1/repos/{owner}/{repo}/issues?access_token={token}
```

**Add Issue Comment:**
```
POST /api/v1/repos/{owner}/{repo}/issues/{id}/comments?access_token={token}
```

---

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GITEA_TOKEN` | Yes | - | Gitea API access token |
| `GITEA_HOST` | Yes | - | Gitea server host (e.g., `server:3000`) |
| `COPILOT_TOKEN` | Yes | - | Copilot authentication token |
| `OPENAI_KEY` | No | - | OpenAI API key (auto-managed) |
| `IGNORED_FILE_SUFFIX` | No | - | Comma-separated file suffixes to ignore |
| `WEBHOOK_URL` | No | - | Notification webhook URL |
| `WEBHOOK_HEADER_NAME` | No | - | Custom webhook header name |
| `WEBHOOK_HEADER_VALUE` | No | - | Custom webhook header value |
| `WEBHOOK_REQUEST_BODY` | No | - | Webhook JSON template |

### .env.example

```bash
GITEA_TOKEN=
OPENAI_KEY=
COPILOT_TOKEN=
GITEA_HOST=
IGNORED_FILE_SUFFIX=
WEBHOOK_URL=
WEBHOOK_HEADER_NAME=
WEBHOOK_HEADER_VALUE=
WEBHOOK_REQUEST_BODY=
```

### Magic Numbers & Constants

| Location | Value | Purpose |
|----------|-------|---------|
| `main.py:99` | `1.5` | Sleep delay between API calls (seconds) |
| `main.py:32` | `"[skip codereview]"` | Skip trigger string |
| `copilot.py:52` | `4096` | max_tokens for AI request |
| `copilot.py:53` | `0.1` | temperature for AI request |
| `copilot.py:54` | `1` | top_p for AI request |
| `copilot.py:56` | `false` | stream flag for AI request |
| `gitea/client.py:32` | `"jenkins"` | Default assignee |
| `gitea/client.py:37` | `0` | Default label ID |
| `gitea/client.py:39` | `0` | Default milestone ID |
| `logger.py:63` | `"10 MB"` | Log rotation size |
| `logger.py:64` | `"10 days"` | Log retention period |

---

## Data Flow

### Webhook Processing Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Gitea Push Event Triggered                          │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  1. POST /codereview                                                      │
│     - Receive webhook payload                                            │
│     - Extract: owner, repo, sha, ref, pusher, title, commit_url           │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  2. Skip Check                                                            │
│     - Does title contain "[skip codereview]"?                             │
│     - Yes: Return {"message": "Skip codereview"}                          │
│     - No: Continue                                                        │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  3. Fetch Diff                                                            │
│     - Call gitea_clinet.get_diff_blocks(owner, repo, sha)                │
│     - Parse diff into file blocks                                         │
│     - Return None on error                                                │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  4. Process Each File Diff                                               │
│     For each diff_block:                                                  │
│       a. Extract file name from diff                                      │
│       b. Check if file suffix in ignored list                             │
│          - Ignored: Log warning, continue to next file                    │
│          - Not ignored: Continue processing                               │
│       c. Send to AI: copilot.code_review(diff_content)                   │
│       d. Format comment: create_comment(file_name, diff, response)       │
│       e. First file?                                                      │
│          - Yes: Create new issue with review                              │
│          - No: Add comment to existing issue                              │
│       f. Sleep 1.5 seconds (rate limiting)                                │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  5. Add Banner                                                            │
│     - Add copilot.banner as final comment to issue                        │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  6. Notification (Optional)                                               │
│     - Is webhook configured?                                              │
│     - Yes: POST notification with review URL                              │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  7. Return                                                                │
│     - Return {"message": response}                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### AI Request Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  1. Prepare Request                                                       │
│     - URL: https://api.cocopilot.org/chat/completions                    │
│     - Headers: Include Bearer token, editor versions                      │
│     - Body: System prompt (hardcoded) + User message (diff)               │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  2. Send Request                                                          │
│     - POST to Copilot API                                                 │
│     - Wait for response                                                   │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  3. Check Response                                                        │
│     - Status 401?                                                        │
│       - Yes: Call get_access_token(renew=True)                           │
│              Update self.access_token                                     │
│              Retry code_review()                                          │
│     - Status 200?                                                        │
│       - Yes: Extract message from response["choices"][0]["message"]      │
│              Return message                                               │
│     - Other?                                                             │
│       - Log error                                                         │
│       - Return response.text                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Dependencies

### Production Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | ^0.111.0 | Web framework |
| `uvicorn` | ^0.30.1 | ASGI server |
| `requests` | ^2.32.3 | HTTP client |
| `python-dotenv` | ^1.0.1 | Environment configuration |
| `loguru` | ^0.7.2 | Logging |
| `PyYAML` | ^6.0.1 | YAML parsing (for future prompt front matter) |
| `pydantic` | ^2.8.2 | Data validation (FastAPI dependency) |
| `starlette` | ^0.37.2 | ASGI toolkit (FastAPI dependency) |

### Development Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `poetry` | - | Dependency management |

---

## Deployment

### Docker Configuration

#### Dockerfile
```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 3008

CMD ["python", "main.py"]
```

#### docker-compose.yml
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
      - OPENAI_KEY=${OPENAI_KEY}
      - COPILOT_TOKEN=none
      - IGNORED_FILE_SUFFIX=.json,.md,.lock,.png,.jpg,.svg,.map
    extra_hosts:
      - "host.docker.internal:host-gateway"
    volumes:
      - ./main.py:/app/main.py
networks:
  gitea_gitea:
    external: true
```

**Current Limitations:**
- No `./prompts` volume mount (needs to be added for hot-reload)
- `COPILOT_TOKEN=none` workaround in environment

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your values

# Run application
python main.py
```

**Server:** Uvicorn on `0.0.0.0:3008` with auto-reload enabled

### Gitea Webhook Configuration

**Settings → Repository → Webhooks → Add Webhook → Gitea**

- **Target URL:** `http://gitea-ai-codereview:3008/codereview` (Docker network)
- **Content Type:** `application/json`
- **Trigger On:**
  - [x] Push Events
  - [ ] Pull Request (currently not implemented - uses push events)

---

## Known Issues & Limitations

### Critical Issues

1. **Hardcoded System Prompt**
   - Location: `codereview/copilot.py:43-44`
   - Impact: Cannot modify AI behavior without code changes
   - Locale hardcoded to `zh-cn`

2. **Limited LLM Provider Support**
   - Only supports Copilot API (cocopilot.org)
   - No configurable `BASE_URL`
   - No `LLM_PROVIDER`, `LLM_MODEL` configuration

3. **Missing Prompt Management**
   - No `prompts/` directory
   - No YAML front matter support
   - No variable substitution

4. **Code Duplication**
   - `extract_info_from_request()` exists in both `gitea/client.py` and `utils/utils.py`

### Minor Issues

1. **Hardcoded Values**
   - `assignee: "jenkins"` in `gitea/client.py:32`
   - Sleep delay `1.5` in `main.py:99`
   - Various magic numbers throughout codebase

2. **Missing Exports**
   - `codereview/__init__.py` missing (should export `AI`, `Copilot`)
   - `gitea/__init__.py` missing (should export `GiteaClient`)

3. **Inconsistent Naming**
   - `gitea_clinet` (typo) in `main.py:18`

4. **No Error Recovery**
   - No retry logic for transient failures
   - No circuit breaker for API failures

5. **Limited Testing**
   - No unit tests
   - No integration tests
   - Manual testing via `/test` endpoint only

### Future Enhancements (Not in Current Implementation)

1. Support for multiple LLM providers
2. External prompt management with hot-reload
3. Pull Request support (currently uses push events)
4. Configurable review focus (security, performance, style, etc.)
5. Review templates per repository/branch
6. Batch processing for large diffs
7. Caching for repeated reviews
8. Metrics and monitoring
9. Rate limiting configuration
10. Webhook signature verification

---

## Document Metadata

**Created:** 2025-12-31
**Author:** Claude Code
**Purpose:** Reference documentation for existing codebase before refactoring
**Version:** 0.1.0

**Related Documents:**
- `CLAUDE.md` - Project refactoring instructions
- `README.md` - User-facing documentation
- `.env.example` - Environment configuration template
