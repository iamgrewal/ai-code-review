# Build Step 1: Development Environment Setup

**Feature:** 001-prompts-config-refactor - Externalized Prompts, Flexible LLM Configuration, and Docker Hot-Reload
**Date:** 2025-01-01
**Status:** ✅ Complete

---

## Overview

This document covers the build and deployment process for the refactored Gitea AI Code Reviewer. The application has been transformed from a monolithic script with hardcoded prompts into a modular, containerized service with externalized prompt management and flexible LLM provider configuration.

---

## Prerequisites

### Required Software

| Tool | Version | Purpose |
|------|---------|---------|
| Docker | 20.10+ | Container runtime |
| Docker Compose | 2.0+ | Container orchestration |
| Python | 3.10+ | Local development (optional) |
| Git | Latest | Version control |

### Required Environment Variables

Create a `.env` file in the project root with the following variables:

```bash
# LLM Configuration (at least one authentication method required)
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://api.openai.com/v1  # Or your LLM provider endpoint
LLM_MODEL=gpt-4                              # Or gpt-3.5-turbo, deepseek-chat, etc.
LLM_PROVIDER=openai                           # For documentation purposes

# Legacy LLM Authentication (fallback, for backward compatibility)
OPENAI_KEY=your_openai_key
COPILOT_TOKEN=your_copilot_token

# Gitea Configuration (required)
GITEA_TOKEN=your_gitea_token
GITEA_HOST=http://server:3000

# Application Settings (optional)
IGNORED_FILE_SUFFIX=.json,.md,.lock
```

---

## Quick Start

### 1. Clone and Configure

```bash
# Clone the repository
git clone <repository-url>
cd gitea-ai-codereview

# Copy environment template
cp .env.example .env

# Edit .env with your API keys and configuration
nano .env
```

### 2. Build and Run with Docker

```bash
# Build and start the container
docker compose up -d --build

# View logs
docker logs -f gitea-ai-codereview

# Stop the container
docker compose down
```

The service will be available at `http://localhost:3008`

### 3. Verify Installation

Test the `/test` endpoint:

```bash
curl -X POST "http://localhost:3008/test?request_body=def%20hello%28%29%3A%0A%20%20%20%20return%20'hello%20world'"
```

Expected response: A JSON object with a code review message.

---

## Project Structure

```
gitea-ai-codereview/
├── codereview/              # AI review layer
│   ├── __init__.py
│   ├── ai.py                # Abstract base class
│   └── copilot.py           # Copilot AI implementation
├── gitea/                   # Gitea integration layer
│   ├── __init__.py
│   └── client.py            # Gitea API client
├── utils/                   # Utilities
│   ├── __init__.py
│   ├── config.py            # Configuration management (LLM_API_KEY, LLM_BASE_URL, etc.)
│   ├── logger.py            # Logging with structured JSON formatter
│   ├── prompt_loader.py     # Prompt loading with YAML parsing and variable substitution
│   └── utils.py             # Helper functions
├── prompts/                 # AI prompt files (externalized, gitignored)
│   ├── README.md            # Prompt file documentation
│   └── code-review-pr.md    # Default system prompt with YAML front matter
├── logs/                    # Application logs (gitignored)
├── docs/                    # Documentation
├── .env                     # Environment variables (gitignored)
├── .env.example            # Environment template
├── main.py                  # FastAPI application entry point
├── Dockerfile               # Container configuration
├── docker-compose.yml       # Docker orchestration
├── requirements.txt        # Python dependencies
├── pyproject.toml          # Poetry project configuration
└── CLAUDE.md               # Project architecture documentation
```

---

## Development

### Local Development (without Docker)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
nano .env

# Run the application
python main.py
```

The service will be available at `http://localhost:3008`

### Hot-Reload Development

The `docker-compose.yml` includes volume mounts for development:

```yaml
volumes:
  - ./main.py:/app/main.py      # Code changes reflect immediately
  - ./prompts:/app/prompts       # Prompt changes reflect immediately
```

Edit files on the host machine and changes will take effect immediately in the running container (no rebuild required).

---

## Configuration

### LLM Provider Switching

The application supports multiple LLM providers through environment variables:

#### OpenAI

```bash
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4
LLM_API_KEY=sk-...
```

#### Azure OpenAI

```bash
LLM_BASE_URL=https://your-resource.openai.azure.com/
LLM_MODEL=gpt-4
LLM_API_KEY=your-azure-key
```

#### DeepSeek

```bash
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
LLM_API_KEY=sk-...
```

#### OpenRouter (Multi-Provider Gateway)

```bash
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=deepseek/deepseek-chat
LLM_API_KEY=sk-or-...
```

#### Local LLMs (Ollama, LocalAI)

```bash
# For Ollama running locally
LLM_BASE_URL=http://host.docker.internal:11434/v1
LLM_MODEL=llama2
```

### Prompt Customization

Prompts are stored in `prompts/code-review-pr.md` with YAML front matter:

```markdown
---
model: gpt-4
locale: en
temperature: 0.1
max_tokens: 4096
---

# Code Review Agent

You are a senior software engineer...
[Rest of prompt]

Respond in the following locale: ${locale}
```

**Variable Substitution:**
- `${locale}` - Response language (e.g., `en`, `zh-cn`)
- `${input-focus}` - Review focus area (e.g., `security and performance`)
- `${model}` - Model name (for context)

---

## API Endpoints

### POST `/codereview`

Webhook receiver for Gitea push events.

**Request:** Gitea webhook JSON payload
**Response:** `{"message": "Code review completed"}`

### POST `/test`

Manual testing endpoint for code review.

**Query Parameter:** `request_body` (string) - Code to review
**Response:** `{"message": "<AI code review>"}`

**Example:**

```bash
curl -X POST "http://localhost:3008/test?request_body=def%20foo%28%29%3A%20pass"
```

---

## Docker Deployment

### Build

```bash
docker compose build
```

### Start

```bash
# Start in detached mode
docker compose up -d

# Start with logs in foreground
docker compose up
```

### Stop

```bash
docker compose down
```

### View Logs

```bash
# Follow logs
docker logs -f gitea-ai-codereview

# View last 100 lines
docker logs --tail 100 gitea-ai-codereview

# View logs from container
docker exec gitea-ai-codereview tail -f ./logs/app.log
```

### Restart

```bash
docker compose restart
```

### Rebuild with Code Changes

```bash
docker compose up -d --build --force-recreate
```

---

## Logging

Logs are written to:
- **Console:** Human-readable format (colors enabled)
- **File:** `./logs/app.log` (JSON format, structured)

### Log Rotation

- **Size:** 10 MB per file
- **Retention:** 10 days
- **Compression:** Zip (automatic)

### Structured Logging

LLM requests include additional context:

```json
{
  "timestamp": "2025-01-01T12:00:00",
  "level": "INFO",
  "message": "LLM request completed",
  "file": "copilot.py",
  "line": 121,
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "latency_ms": 1250,
  "status": "success"
}
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check container status
docker compose ps

# Check logs
docker logs gitea-ai-codereview

# Verify environment variables
docker exec gitea-ai-codereview env | grep LLM
```

### LLM Connection Errors

1. **Check API Key**: Verify `LLM_API_KEY` is set correctly in `.env`
2. **Check Base URL**: Ensure `LLM_BASE_URL` is correct for your provider
3. **Check Model Name**: Verify `LLM_MODEL` is supported by your provider
4. **Check Network**: Ensure container can reach the API endpoint

### Prompt Not Loading

```bash
# Verify prompt file exists in container
docker exec gitea-ai-codereview ls -la /app/prompts/

# Check prompt file content
docker exec gitea-ai-codereview cat /app/prompts/code-review-pr.md
```

### Hot-Reload Not Working

Verify volume mounts are configured correctly:

```bash
# Check volume mounts
docker inspect gitea-ai-codereview | grep -A 10 Mounts
```

Expected output should include:
- `/app/prompts` → `./prompts`
- `/app/main.py` → `./main.py`

---

## Validation Checklist

- [ ] Container builds successfully: `docker compose up --build`
- [ ] Container starts without errors: `docker compose ps` shows "Up"
- [ ] `/test` endpoint returns code review
- [ ] Prompt file changes are reflected immediately (hot-reload)
- [ ] Structured logs appear in `./logs/app.log`
- [ ] LLM provider can be switched via `LLM_BASE_URL`

---

## Success Criteria (from PRD)

- [x] All hardcoded prompts removed from code
- [x] `python-dotenv` implemented for `.env` loading
- [x] Application connects to custom `LLM_BASE_URL`
- [x] `docker compose up` runs successfully
- [x] Changes to `prompts/` folder affect running container immediately

**Status: ✅ All criteria met**
