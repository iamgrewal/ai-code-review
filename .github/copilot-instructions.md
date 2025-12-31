# Gitea AI Code Reviewer - Copilot Instructions

## Project Architecture

This is a **webhook-based FastAPI service** that automatically reviews code changes in Gitea repositories using AI providers (primarily Copilot). The system processes push events, fetches diffs, and creates issue comments with AI-generated code reviews.

### Core Components

- **FastAPI App** ([main.py](main.py)): Single-file webhook server with `/codereview` and `/test` endpoints
- **AI Layer** ([codereview/](codereview/)): Abstract base class with Copilot implementation
- **Gitea Integration** ([gitea/client.py](gitea/client.py)): API client for fetching diffs and creating issues
- **Configuration** ([utils/config.py](utils/config.py)): Environment-based config with validation
- **External Prompts** ([prompts/code-review-pr.md](prompts/code-review-pr.md)): Markdown files define AI behavior

## Key Patterns & Conventions

### Webhook Processing Flow
1. Extract commit info from Gitea webhook payload using `extract_info_from_request()`
2. Skip processing if commit title contains `[skip codereview]`
3. Fetch diff blocks via `gitea_client.get_diff_blocks()` - splits on `diff --git` markers
4. Process each file individually, filtering by `IGNORED_FILE_SUFFIX` (.json, .md, .lock, etc.)
5. First file creates new issue, subsequent files add comments to same issue
6. Sleep 1.5s between AI requests to avoid rate limiting

### Configuration Management
- All config via environment variables loaded through `Config` class
- Required vars: `GITEA_TOKEN`, `GITEA_HOST`, `COPILOT_TOKEN`
- Uses python-dotenv for `.env` file support
- Config validation happens in constructor with descriptive errors

### AI Provider Pattern
- Abstract base class `AI` in [codereview/ai.py](codereview/ai.py) with `code_review()`, `get_access_token()`, `banner()` methods
- Current implementation: `Copilot` class using cocopilot.org API
- Prompts loaded from external markdown files in [prompts/](prompts/) directory
- AI responses formatted with Chinese headers: "文件名", "文件变更", "审查结果"

### Docker & Deployment
- Uses Python 3.10-slim base image
- Exposes port 3008 (hardcoded in `main.py`)
- Volume mounts for hot-reloading: `./main.py:/app/main.py`
- Designed to run in same Docker network as Gitea (`gitea_gitea`)

## Development Workflows

### Running Locally
```bash
# Install deps (Poetry or pip)
pip install -r requirements.txt

# Configure environment
cp .env.example .env  # Edit with your tokens

# Run with hot reload
python main.py  # Uvicorn starts on 0.0.0.0:3008
```

### Docker Development
```bash
# Build and run with compose
docker-compose up -d --build

# Hot reload: Edit main.py or prompts/ on host
```

### Testing
- Use `/test` endpoint for manual testing without webhooks
- Check logs via `loguru` in [utils/logger.py](utils/logger.py)
- Test webhook integration using Gitea's webhook test feature

## Critical Integration Points

### Gitea API Endpoints
- **Diff fetching**: `GET /api/v1/repos/{owner}/{repo}/git/commits/{sha}.diff?access_token={token}`
- **Issue creation**: `POST /api/v1/repos/{owner}/{repo}/issues?access_token={token}`
- **Comment creation**: `POST /api/v1/repos/{owner}/{repo}/issues/{id}/comments?access_token={token}`

### Copilot API Integration
- Uses cocopilot.org with OpenAI-compatible interface
- Sends prompts loaded from markdown files in [prompts/](prompts/)
- Includes diff content and file context in requests

### Error Handling
- Network failures return None, logged via `logger.error()`
- Invalid config raises `ValueError` on startup
- File filtering uses suffix checking with continue statements

## Speckit Command System

This project includes a specification and planning system with custom commands:

- **@workspace /specify** [description] - Create feature specification from natural language
- **@workspace /plan** [context] - Generate technical implementation plan  
- **@workspace /tasks** [context] - Break plan into actionable tasks
- **@workspace /checklist** [domain] - Create domain-specific checklists

See [.github/copilot/commands.md](.github/copilot/commands.md) for detailed usage.

### Script Integration
- [.specify/scripts/bash/](.specify/scripts/bash/) - Command implementation scripts
- [.specify/templates/](.specify/templates/) - Specification templates
- [specs/](specs/) - Generated feature specifications and plans

## File-Specific Notes

- [main.py](main.py#L14-L20): Global instances created at module level (app, config, gitea_client, copilot)
- [utils/utils.py](utils/utils.py): Contains webhook parsing and comment formatting helpers
- [prompts/code-review-pr.md](prompts/code-review-pr.md): Extensive prompt engineering with YAML frontmatter
- [gitea/client.py](gitea/client.py#L14-L25): Regex parsing of diff blocks using `re.split("diff --git ")`