# Quickstart: Prompts and Configuration Refactoring

**Feature**: 001-prompts-config-refactor
**Branch**: `001-prompts-config-refactor`
**Date**: 2025-01-01

## Overview

This guide helps you understand and work with the refactored Gitea AI Code Reviewer. The refactoring externalizes AI prompts to Markdown files, centralizes configuration via environment variables, and enables flexible LLM provider switching.

## Prerequisites

- **Docker** and **Docker Compose** installed
- **Gitea** server running (or access to a Gitea instance)
- **LLM Provider**: OpenAI API key, Azure OpenAI, or local LLM (Ollama, LocalAI)
- **Git** repository with push webhook capability

## Quick Start (5 Minutes)

### 1. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
nano .env  # Or use your preferred editor
```

**Required Variables**:
```bash
# Gitea Configuration
GITEA_TOKEN=your_gitea_token_here
GITEA_HOST=http://server:3000

# LLM Configuration (choose one)
LLM_API_KEY=sk-your-openai-key-here
LLM_BASE_URL=https://api.openai.com/v1  # Or local: http://localhost:11434/v1
LLM_MODEL=gpt-4
```

### 2. Start the Service

```bash
docker-compose up --build
```

The service starts on port 3008. Watch for `Application startup complete` in logs.

### 3. Configure Gitea Webhook

1. Go to your Gitea repository → Settings → Webhooks
2. Click "Add Webhook" → "Gitea"
3. Configure:
   - **Target URL**: `http://gitea-ai-codereview:3008/codereview`
   - **Content Type**: `application/json`
   - **Push Events**: ✅ Checked
4. Click "Add Webhook"

### 4. Test the Integration

Push a commit to your repository:

```bash
git commit --allow-empty -m "Test code review"
git push
```

Check the Gitea repository Issues—you should see a new issue with AI code review comments.

## Customizing AI Prompts

### Edit the Default Prompt

The default prompt is at `./prompts/code-review-pr.md`:

```bash
nano prompts/code-review-pr.md
```

**Prompt File Structure**:
```markdown
---
model: gpt-4
locale: en-us
temperature: 0.1
---

You are a senior code reviewer. Analyze the provided code diff for:
- Security vulnerabilities
- Performance issues
- Code style and readability
- Potential bugs

Provide constructive feedback in ${locale}.
```

### Hot-Reload

Changes to `./prompts/*.md` files take effect immediately—no container restart needed. The next webhook trigger will use the updated prompt.

### Variable Substitution

Use `${variable}` placeholders in prompts:

| Variable | Description | Example |
|----------|-------------|---------|
| `${locale}` | Language for review output | `en-us`, `zh-cn` |
| `${input-focus}` | Review focus area | `security vulnerabilities` |
| `${model}` | Current LLM model name | `gpt-4-turbo` |

## Switching LLM Providers

### OpenAI (Default)

```bash
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4
```

### Azure OpenAI

```bash
LLM_BASE_URL=https://your-resource.openai.azure.com/openai/deployments/your-deployment
LLM_API_KEY=your-azure-api-key
LLM_MODEL=gpt-4  # Must match Azure deployment name
```

### Ollama (Local LLM)

```bash
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama  # Ollama doesn't require a key, but set a placeholder
LLM_MODEL=llama3
```

### LocalAI

```bash
LLM_BASE_URL=http://localhost:8080/v1
LLM_API_KEY=your-localai-key
LLM_MODEL=mixtral-8x7b
```

## Development Workflow

### Local Development (Without Docker)

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
nano .env

# Run application (auto-reload on code changes)
python main.py
```

The application runs on `http://localhost:3008`.

### Hot-Reload Development

```bash
# Terminal 1: Start Docker Compose
docker-compose up

# Terminal 2: Edit prompts and see changes immediately
nano prompts/code-review-pr.md

# Terminal 3: Trigger a test
curl -X POST http://localhost:3008/test -d 'def foo(): pass'
```

### Viewing Logs

```bash
# Container logs
docker logs -f gitea-ai-codereview

# Application logs (mounted volume)
tail -f logs/app.log
```

### Manual Testing

Use the `/test` endpoint to test without triggering a webhook:

```bash
curl -X POST http://localhost:3008/test \
  -H "Content-Type: text/plain" \
  -d 'def add(a, b): return a + b'
```

## Troubleshooting

### Issue: "Prompt file not found" Warning

**Cause**: The `./prompts/code-review-pr.md` file doesn't exist.

**Solution**: The system uses a fallback prompt. To fix, create the file:

```bash
mkdir -p prompts
cat > prompts/code-review-pr.md << 'EOF'
---
model: gpt-4
locale: en-us
---

You are a senior code reviewer. Analyze the provided code diff for:
- Security vulnerabilities
- Performance issues
- Code style and readability
- Potential bugs

Provide constructive feedback in ${locale}.
EOF
```

### Issue: "ValueError: At least one LLM authentication method required"

**Cause**: No LLM authentication variables set.

**Solution**: Set one of the following in `.env`:
- `LLM_API_KEY` (recommended)
- `OPENAI_KEY` (deprecated, shows warning)
- `COPILOT_TOKEN` (legacy Copilot support)

### Issue: "Connection refused" to Gitea

**Cause**: `GITEA_HOST` points to wrong URL or container can't reach Gitea.

**Solution**:
- Inside Docker: Use `http://server:3000` (container name)
- Outside Docker: Use `http://localhost:3000` or `http://192.168.x.x:3000`
- Verify network: `docker network inspect gitea_gitea`

### Issue: LLM Request Times Out

**Cause**: LLM request exceeds 60-second timeout.

**Solution**: The system logs a warning and skips to the next file. Check:
- LLM endpoint is responsive
- `LLM_BASE_URL` is correct
- Network connectivity to LLM provider

## Configuration Reference

### All Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GITEA_TOKEN` | Yes | - | Gitea API token |
| `GITEA_HOST` | Yes | - | Gitea server URL |
| `LLM_API_KEY` | No | - | Primary LLM API key |
| `LLM_BASE_URL` | No | - | Custom LLM endpoint URL |
| `LLM_MODEL` | No | `gpt-4` | Model name |
| `LLM_PROVIDER` | No | `openai` | Provider identifier (logging) |
| `COPILOT_TOKEN` | No | - | Legacy Copilot token |
| `OPENAI_KEY` | No | - | Legacy OpenAI key (deprecated) |
| `IGNORED_FILE_SUFFIX` | No | `.json,.md,.lock` | File extensions to skip |

### Backward Compatibility

The system supports legacy variables for migration:

1. **LLM_API_KEY** (new, highest priority)
2. **OPENAI_KEY** (legacy, deprecation warning logged)
3. **COPILOT_TOKEN** (legacy Copilot support)

If multiple are set, `LLM_API_KEY` takes precedence.

## Next Steps

- **Customize prompts**: Edit `./prompts/code-review-pr.md` to focus on security, performance, or style
- **Configure ignored files**: Update `IGNORED_FILE_SUFFIX` in `.env` to skip file types
- **Set up notifications**: Configure `WEBHOOK_URL` in `.env` for review notifications
- **Explore the codebase**: See [CLAUDE.md](CLAUDE.md) for development guidelines

## References

- [Feature Specification](spec.md)
- [Implementation Plan](plan.md)
- [Data Model](data-model.md)
- [API Contracts](contracts/openapi.yaml)
- [Project Constitution](/.specify/memory/constitution.md)
