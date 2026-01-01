# CortexReview Platform

**A Self-Learning, Context-Aware AI Code Review Platform** with RAG (Retrieval-Augmented Generation) and RLHF (Reinforcement Learning from Human Feedback).

CortexReview transforms code review from a stateless checklist into a stateful, intelligent system that learns from your codebase and adapts to your team's patterns. It supports multi-platform operation (GitHub & Gitea), indexes repository history for context-aware reviews, and continuously improves through user feedback.

## 🚀 Key Features

### Phase 2 (Current Release)
- **Platform Abstraction**: Single codebase supporting both GitHub and Gitea via adapter pattern
- **Async Processing**: Webhook acknowledgment within 2 seconds with background Celery task processing
- **Multi-Container Architecture**: API (FastAPI), Worker (Celery), Redis, Prometheus, and Grafana

### Phase 2+ (Roadmap)
- **Context-Aware Reviews (RAG)**: Index repository history and retrieve relevant context for reviews with citations
- **Learning Loop (RLHF)**: Accept feedback to suppress false positives and adapt to team-specific patterns
- **Auto-Fix Patches**: Generate `git apply` compatible patches for simple issues
- **MCP Integration**: Model Context Protocol support for IDE agents (Cursor, Windsurf)
- **Observability**: Prometheus metrics and Grafana dashboards for monitoring

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Client Layer                                 │
├─────────────┬─────────────┬─────────────────────────────────────────────┤
│   GitHub     │    Gitea    │  IDE Agents (MCP) / REST / CLI           │
│   Webhooks   │   Webhooks   │                                             │
└──────┬────────┴──────┬───────┴─────────────────────────────────────────────┘
       │               │
       ▼               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    API Gateway (FastAPI)                              │
│  - Webhook Signature Verification (HMAC-SHA256)                         │
│  - Platform Adapter Selection                                                │
│  - 202 Accepted → Celery Task Dispatch                                   │
└───────┬───────────────────────────────────────┬───────────────────────┘
        │                                       │
        ▼                                       ▼
┌───────────────────┐               ┌───────────────────────────────────────┐
│  Async Worker      │               │       Knowledge Layer (Supabase)      │
│  (Celery)          │               │  ┌─────────────┬───────────────────┐  │
│  - Code Review     │               │  │knowledge_base│  learned_constraints│  │
│  - RAG Retrieval    │◄─────────────┼─▶ │  (RAG Context)│   (RLHF Filter)   │  │
│  - RLHF Learning   │               │  └─────────────┴───────────────────┘  │
│  - Repo Indexing   │               │         PostgreSQL + pgvector          │
└───────────────────┘               └───────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         AI Layer                                      │
│  - OpenAI GPT-4 (LLM)                                                      │
│  - OpenAI Embeddings (text-embedding-3-small)                               │
└─────────────────────────────────────────────────────────────────────┘
```

## 🛠 Prerequisites

| Component | Version/Requirement |
|-----------|---------------------|
| **Python** | 3.11+ |
| **Docker** | Latest (with Docker Compose) |
| **Git Platform** | GitHub (any) or Gitea 1.19+ |
| **LLM API** | OpenAI-compatible (OpenAI, Azure, Ollama, LocalAI, etc.) |
| **Vector Database** | Supabase (PostgreSQL + pgvector) - **Local or Cloud** |
| **Message Broker** | Redis 7+ |

## 📦 Installation & Deployment

### Deployment Options

The CortexReview platform supports **two deployment modes** for Supabase:

1. **Local Supabase (Recommended)**: Self-hosted Supabase using Docker Compose
   - ✅ No external dependencies
   - ✅ Full data control and sovereignty
   - ✅ Reduced operational costs
   - ✅ Offline operation capability
   - See: [Local Supabase Quickstart](specs/002-local-supabase-docker/quickstart.md)

2. **External Supabase Cloud**: Use Supabase Cloud hosting
   - ❌ Requires Supabase Cloud account
   - ❌ External dependency
   - ❌ Ongoing operational costs
   - See: [docs/supabase_migration.md](docs/supabase_migration.md)

### Quick Start (Local Supabase)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/bestK/gitea-ai-codereview.git
   cd gitea-ai-codereview
   git checkout main
   ```

2. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```
   **Critical**: Replace all `CHANGE_ME_*` placeholders with secure values:
   ```bash
   # Generate secure secrets
   openssl rand -base64 64  # JWT_SECRET
   openssl rand -base64 32  # POSTGRES_PASSWORD
   ```

3. **Start the services:**
   ```bash
   docker-compose up -d
   ```

4. **Verify deployment:**
   ```bash
   # Check all containers are healthy
   docker-compose ps

   # Test health endpoint
   curl http://localhost:3008/health
   ```

For detailed deployment instructions, see:
- [Local Supabase Quickstart Guide](specs/002-local-supabase-docker/quickstart.md)
- [Supabase Setup & Troubleshooting](docs/supabase_setup.md)
- [Supabase Migration Guide](docs/supabase_migration.md)

### Environment Variables

| Category | Variable | Required | Default |
|----------|----------|----------|---------|
| **Git Platform** | `PLATFORM` | ✅ | `gitea` |
| | `GITEA_HOST` | ✅ (if Gitea) | - |
| | `GITEA_TOKEN` | ✅ (if Gitea) | - |
| | `GITHUB_TOKEN` | ✅ (if GitHub) | - |
| **LLM** | `LLM_API_KEY` | ✅ | - |
| | `LLM_BASE_URL` | ❌ | `https://api.openai.com/v1` |
| | `LLM_MODEL` | ❌ | `gpt-4` |
| | `EMBEDDING_MODEL` | ❌ | `text-embedding-3-small` |
| **Celery** | `CELERY_BROKER_URL` | ✅ | `redis://redis:6379/0` |
| | `CELERY_RESULT_BACKEND` | ✅ | `redis://redis:6379/0` |
| **Local Supabase** | `POSTGRES_PASSWORD` | ✅ (local) | `CHANGE_ME_*` |
| | `POSTGRES_DB` | ✅ (local) | `supabase` |
| | `JWT_SECRET` | ✅ (local) | `CHANGE_ME_*` |
| | `ANON_KEY` | ✅ (local) | `CHANGE_ME_*` |
| | `SERVICE_ROLE_KEY` | ✅ (local) | `CHANGE_ME_*` |
| | `SUPABASE_DB_URL` | ✅ (local) | `postgresql://...` |
| **External Supabase** | `SUPABASE_URL` | ✅ (cloud) | - |
| | `SUPABASE_SERVICE_KEY` | ✅ (cloud) | - |
| **Webhook Secrets** | `PLATFORM_GITHUB_WEBHOOK_SECRET` | ❌ | - |
| | `PLATFORM_GITEA_WEBHOOK_SECRET` | ❌ | - |
| | `PLATFORM_GITEA_WEBHOOK_SECRET` | ❌ | - |

See [`.env.example`](.env.example) for all available configuration options.

## 🔗 Connecting Git Platforms

### GitHub

1. Navigate to **Repository Settings** → **Webhooks** → **Add webhook**
2. **Payload URL:** `https://your-domain.com/v1/webhook/github`
3. **Content type:** `application/json`
4. **Secret:** Generate and add to `.env` as `PLATFORM_GITHUB_WEBHOOK_SECRET`
5. **Events:** Pull requests, Pull request reviews

### Gitea

1. Navigate to **Repository Settings** → **Webhooks** → **Add Webhook** → **Gitea**
2. **Target URL:** `https://your-domain.com/v1/webhook/gitea`
3. **Secret:** Generate and add to `.env` as `PLATFORM_GITEA_WEBHOOK_SECRET`
4. **Trigger On:** Pull Request events

## 📝 Usage

### Webhook-Based Reviews

1. Create a branch and commit your changes
2. Open a Pull Request
3. CortexReview receives the webhook and returns `202 Accepted`
4. Review processes asynchronously in background worker
5. Review comments posted to the PR within ~60 seconds

### REST API

```bash
# Submit a review directly
curl -X POST "https://your-domain.com/v1/reviews" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "local_cli",
    "diff_content": "diff --git a/file.py b/file.py...",
    "config": {
      "use_rag_context": true,
      "apply_learned_suppressions": true
    }
  }'
```

### Task Status Polling

```bash
# Check review status
curl "https://your-domain.com/v1/tasks/{task_id}"
```

### Repository Indexing (RAG)

```bash
# Trigger repository indexing for context-aware reviews
curl -X POST "https://your-domain.com/v1/repositories/{repo_id}/index" \
  -H "Content-Type: application/json" \
  -d '{
    "git_url": "https://github.com/user/repo",
    "access_token": "ghp_...",
    "branch": "main",
    "index_depth": "deep"
  }'
```

### Feedback (RLHF)

```bash
# Submit feedback to improve future reviews
curl -X POST "https://your-domain.com/v1/reviews/{review_id}/feedback" \
  -H "Content-Type: application/json" \
  -d '{
    "comment_id": "cmt_123",
    "action": "rejected",
    "reason": "false_positive",
    "developer_comment": "This pattern is acceptable in our codebase",
    "final_code_snapshot": "def example(): ..."
  }'
```

## 🔍 Observability

### Prometheus Metrics

Access metrics at `/metrics`:
- `cortexreview_review_duration_seconds` - Review completion time
- `cortexreview_rag_retrieval_latency_seconds` - RAG context retrieval
- `cortexreview_llm_tokens_total` - Token usage by model type
- `cortexreview_feedback_submitted_total` - RLHF feedback submissions

### Grafana Dashboards

With observability profile enabled:
```bash
docker-compose --profile observability up
```

Access Grafana at `http://localhost:3000` (default: `admin/admin`)

## 🎯 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API information |
| `/health` | GET | Health check |
| `/docs` | GET | Interactive API documentation (Swagger UI) |
| `/metrics` | GET | Prometheus metrics |
| `/mcp/manifest` | GET | MCP manifest for IDE agents |
| `/v1/webhook/{platform}` | POST | Platform webhook endpoint |
| `/v1/tasks/{task_id}` | GET | Task status polling |
| `/v1/repositories/{repo_id}/index` | POST | Trigger repository indexing |
| `/v1/reviews/{review_id}/feedback` | POST | Submit feedback (RLHF) |

### Legacy Endpoints (Phase 1 Compatibility)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/codereview` | POST | Legacy Gitea webhook (deprecated) |
| `/test` | POST | Manual testing endpoint (deprecated) |

## ⚙️ Customization

### Prompt Engineering

Edit `./prompts/code-review-pr.md` to customize the AI's behavior:

```markdown
---
model: gpt-4
locale: en_us
temperature: 0.1
---

You are a senior software engineer specializing in security and performance.

## Review Focus
Focus on: ${input-focus}

## Guidelines
- Flag security vulnerabilities with high severity
- Suggest performance optimizations
- Follow the team's coding standards defined in the repository context
```

### Configuration via Files

The system supports hot-reloading for:
- **Prompts**: `./prompts/*.md` - AI system prompts
- **Code**: `main.py` - API changes (development mode)

## 🚀 Development

### Local Development Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Start Redis (required for Celery)
docker-compose up -d redis

# Start API server
uvicorn main:app --reload --host 0.0.0.0 --port 3008

# Start Celery worker (separate terminal)
celery -A celery_app worker --loglevel=info
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=.

# Run specific test module
pytest tests/unit/test_models.py
```

## 📖 Documentation

- **[PRD](docs/PRD.md)** - Product Requirements Document
- **[Architecture](docs/Architecture.md)** - System Architecture
- **[API Design](docs/API-Design.md)** - API Specification
- **[Spec Kit Framework](docs/Spec-Kit-Doc-Framework.md)** - Documentation Framework

## 🗺️ Roadmap

### Phase 2 (Current) - Platform Foundation
- ✅ Pydantic models and data contracts
- ✅ Platform abstraction (GitHub/Gitea adapters)
- ✅ Async processing with Celery
- ✅ Docker multi-container architecture
- ✅ Observability infrastructure (Prometheus metrics)

### Phase 3 - Async Processing & Platform Abstraction
- ⏳ Celery task orchestration
- ⏳ Webhook signature verification middleware
- ⏳ Task status polling endpoint
- ⏳ Retry logic with exponential backoff

### Phase 4 - Context-Aware Reviews (RAG)
- ⏳ Repository indexing pipeline
- ⏳ Vector embeddings (OpenAI text-embedding-3-small)
- ⏳ Supabase pgvector integration
- ⏳ Context retrieval with citations

### Phase 5 - Learning Loop (RLHF)
- ⏳ Feedback processing workflow
- ⏳ Learned constraints with embedding matching
- ⏳ 90-day constraint expiration
- ⏳ False positive suppression

### Phase 6 - Observability
- ⏳ Prometheus metrics integration
- ⏳ Grafana dashboards
- ⏳ Alerting rules

### Phase 7 - IDE Integration (MCP)
- ⏳ MCP manifest endpoint
- ⏳ Tool schema definitions
- ⏳ IDE agent support

## ❓ Troubleshooting

### Common Issues

**Webhook returns 401 Unauthorized:**
- Verify `PLATFORM_GITHUB_WEBHOOK_SECRET` or `PLATFORM_GITEA_WEBHOOK_SECRET` is set
- Check webhook secret matches between platform and `.env`

**Celery worker not processing tasks:**
- Ensure Redis is running: `docker-compose ps`
- Check worker logs: `docker logs cortexreview-worker`
- Verify `CELERY_BROKER_URL` matches Redis container

**Supabase connection failures:**
- Verify `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` are correct
- Test connection: `python scripts/test_supabase.py`
- Check network access from container

**Reviews missing context citations:**
- Ensure repository has been indexed: `POST /v1/repositories/{repo_id}/index`
- Check Supabase `knowledge_base` table has embeddings
- Verify RAG is enabled in review config: `use_rag_context: true`

### Debug Mode

Enable detailed logging by setting `LOG_LEVEL=DEBUG` in `.env`:

```bash
LOG_LEVEL=DEBUG docker-compose up api worker
```

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines and submit pull requests to the `001-cortexreview-platform` branch.

## 🙏 Acknowledgments

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework for building APIs
- [Celery](https://docs.celeryproject.org/) - Distributed task queue
- [Supabase](https://supabase.com/) - Open-source Firebase alternative
- [OpenAI](https://openai.com/) - AI model provider
- [Prometheus](https://prometheus.io/) - Metrics collection
- [Grafana](https://grafana.com/) - Visualization platform
