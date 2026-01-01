# Implementation Plan: Local Supabase Docker Deployment

**Branch**: `002-local-supabase-docker` | **Date**: 2026-01-01 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-local-supabase-docker/spec.md`

## Summary

Transform the CortexReview Platform from using external Supabase Cloud services to a completely self-hosted, local-first deployment using Docker Compose. The platform will run entirely on a local Ubuntu server with no external dependencies for core functionality.

**Key Changes**:

1. **Self-Hosted Supabase**: Deploy Supabase services (PostgreSQL + pgvector, Studio, REST API) as Docker containers alongside existing API, Worker, and Redis services.

2. **Integrated Docker Compose**: Single docker-compose.yml file orchestrating all 6 services (API, Worker, Redis, Supabase DB, Supabase Studio, Supabase REST API) with proper networking and health checks.

3. **Automated Schema Initialization**: Database schema (pgvector extension, knowledge_base table, learned_constraints table, vector indexes, SQL functions) initializes automatically on first container startup.

4. **Data Persistence & Backup**: Named Docker volumes for database persistence; documented backup procedures with weekly backup frequency and 90-day retention policy.

5. **Resource Optimization**: Optional services (Studio, Realtime, Storage) can be disabled via docker-compose profiles to reduce resource footprint on hardware-constrained servers.

**Technical Approach**: Multi-container architecture with API (FastAPI), Worker (Celery), Redis (message broker), Supabase (self-hosted PostgreSQL + pgvector + Studio), Prometheus (metrics), and Grafana (dashboards). Pre-flight checks integrated into container startup for validation (environment variables, system resources). Migration support from external Supabase instances.

## Technical Context

**Language/Version**: Python 3.11+ (async-first, existing codebase)

**Primary Dependencies**:
- **Web Framework**: FastAPI 0.111+ (async, Pydantic v2, OpenAPI)
- **Task Queue**: Celery 5.3+ with Redis 7+ (existing)
- **Vector Database**: Self-hosted Supabase with pgvector extension (NEW - replacing external)
- **AI Provider**: OpenAI Python SDK 1.0+ (chat + embeddings, existing)
- **Observability**: prometheus_client + Grafana (existing)
- **Git Integration**: GitPython, PyGithub (existing)
- **Configuration**: pydantic-settings (existing)
- **Logging**: Loguru 0.7+ (existing)

**Storage**:
- **Redis**: Celery broker and result backend (existing)
- **Supabase PostgreSQL**: Self-hosted in Docker container with pgvector extension
  - Vector storage: knowledge_base table (KnowledgeEntry entities)
  - Learned constraints: learned_constraints table (LearnedConstraint entities)
  - Audit log: feedback_audit_log table (FeedbackRecord entities)
- **Docker Volumes**:
  - supabase-db-data: PostgreSQL data files
  - supabase-studio-data: Studio configuration
  - redis-data: Redis persistence (existing)
- **Filesystem**: Temporary directory for repository cloning (existing)

**Testing**:
- pytest, pytest-asyncio, pytest-celery, httpx, Factory Boy (existing)

**Package Manager**: `uv` for fast dependency management (existing)

**Static Analysis**: `ruff` for fast linting and formatting (existing)

**Target Platform**: Linux server (Ubuntu 20.04 LTS or 22.04 LTS)

**Project Type**: Single project with modular service architecture

**Performance Goals**:
- Deployment time: <10 minutes from fresh server to operational
- Container startup time: <60 seconds for Supabase services
- Vector search latency: <200ms (p95) for local similarity search
- Resource usage: <4GB RAM, <2 CPU cores for core services

**Constraints**:
- LLM API rate limits (OpenAI: 3500 requests/minute)
- Embedding API rate limits (OpenAI: 3000 requests/minute)
- Memory per worker container: <2GB (existing)
- Supabase connection pool: 20 connections across all workers
- Minimum server resources: 4GB RAM, 2 CPU cores, 20GB disk space

**Scale/Scope**:
- Target: 1000+ repositories, 10,000+ daily reviews (existing)
- Knowledge base: 10M+ embeddings with IVFFlat index tuning
- Feedback loop: 1000+ constraints with 90-day expiration
- Single-region deployment (local infrastructure only)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Phase 2 Compliance Gates (Constitution v3.1.0 - Existing)

#### Async-First Processing (Principle VII)
- [x] No LLM calls in webhook handlers (existing - Celery tasks)
- [x] Webhook endpoints return `202 Accepted` within 2 seconds (existing)
- [x] Task state queryable via polling endpoint (existing)
- [x] Failed tasks retry with exponential backoff (existing)

#### Platform Abstraction (Principle VIII)
- [x] Git operations through `GitPlatformAdapter` interface (existing)
- [x] Webhook payloads normalized to `PRMetadata` model (existing)
- [x] Platform selection via `PLATFORM` environment variable (existing)
- [x] No platform-specific logic in service layer (existing)

#### Observability (Principle XI)
- [x] Prometheus metrics emitted for all critical operations (existing)
- [x] `trace_id` propagated across request lifecycle (existing)
- [x] `/metrics` endpoint exposed for scraping (existing)
- [x] Token usage tracked for cost monitoring (existing)

#### Data Governance (Principle XIII)
- [x] Secret scanning before embedding generation (existing)
- [x] Repo-level data isolation in vector store (existing)
- [x] Feedback audit log for compliance (existing)
- [x] No secrets in embeddings (existing)

#### Interface Standardization (Principle XII)
- [x] REST endpoints use `/v1/` prefix (existing)
- [x] Pydantic models for all request/response (existing)
- [x] OpenAPI spec auto-generated (existing)
- [x] Breaking changes increment API version (existing)

#### Graceful Degradation (Principle IV - Expanded)
- [x] Cascading fallback levels (RAG → RLHF → Standard → Cached) (existing)
- [x] Supabase failure continues without RAG (existing - now applies to local Supabase)
- [x] Redis failure falls back to filesystem queuing (existing)
- [x] All fallbacks log WARNING with context (existing)

#### Test-Driven Development (Principle XIV)
- [x] Tests written BEFORE implementation (Red-Green-Refactor) (existing)
- [x] All production code has corresponding tests (existing)
- [x] Test files mirror source file structure (existing)
- [x] Using pytest 8.4+ as testing framework (existing)
- [x] Using uv as package manager (existing)
- [x] Using ruff for static analysis (existing)
- [x] All tests passing before committing (existing)
- [x] Test coverage ≥ 80% for new code (existing)

#### Container-First (Principle III - Expanded)
- [x] Multi-container architecture (api, worker, redis) (existing)
- [x] API container: uvicorn on port 3008 (existing)
- [x] Worker container: Celery with task queues (existing)
- [x] All services on shared network with health checks (existing)

### New Compliance Gates (Feature-Specific)

#### Self-Hosted Infrastructure (New for this feature)
- [x] Supabase services deployed via Docker containers (designed)
- [x] No external Supabase Cloud dependencies for core functionality (designed)
- [x] Database schema initializes automatically on first startup (contract defined)
- [x] Data persists across container restarts via named volumes (designed)
- [x] Backup procedures documented with weekly/90-day policy (contract defined)

#### Pre-Flight Validation (New for this feature)
- [x] Environment variable validation during container startup (designed)
- [x] System resource checks (RAM, CPU) with warnings (designed)
- [x] Fail-fast with clear error messages if validation fails (contract defined)
- [x] Pre-flight check integrated into container entrypoint (designed)

#### Configuration Management (New for this feature)
- [x] All Supabase secrets configurable via environment variables (designed)
- [x] .env.example file with all required variables documented (designed)
- [x] Database access restricted to internal Docker network by default (designed)
- [x] Studio can be disabled for production deployments (designed)

**Gate Status**: ✅ PASSED - All existing gates satisfied. All new gates designed and ready for implementation.

---

## Phase 1 Completion Status

**Status**: ✅ COMPLETE

**Artifacts Generated**:
- [x] `research.md` - Technical research findings (all unknowns resolved)
- [x] `data-model.md` - Complete database schema definition
- [x] `contracts/supabase-initialization.md` - Database initialization contract
- [x] `contracts/backup-procedures.md` - Backup and restore contract
- [x] `contracts/migration-procedures.md` - External Supabase migration contract
- [x] `quickstart.md` - Developer deployment guide

**Design Decisions Made**:
- Docker images: Official Supabase images (supabase/postgres:15.1.0.147)
- Initialization: Entrypoint script with SQL migrations
- Pre-flight checks: Python script in container entrypoint
- Backup: pg_dump via docker exec with 90-day retention
- Migration: Export/import scripts with vector preservation

**Constitution Re-Evaluation**: ✅ PASSED
- All existing gates still satisfied
- New feature gates defined and designed
- No violations identified

**Next Step**: Proceed to Phase 2 (`/speckit.tasks`) for implementation task breakdown.

## Project Structure

### Documentation (this feature)

```text
specs/002-local-supabase-docker/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   ├── supabase-initialization.md
│   ├── backup-procedures.md
│   └── migration-procedures.md
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Application Changes

```text
# Root-level additions
docker-compose.yml                 # UPDATED: Add Supabase services
.env.example                       # UPDATED: Add Supabase environment variables
scripts/
└── init_supabase.py               # UPDATED: Enhanced for local Supabase
docs/
└── supabase_setup.md              # UPDATED: Enhanced local deployment guide
```

### Docker Services

```text
# New containers in docker-compose.yml
supabase-db                         # PostgreSQL 15 with pgvector extension
supabase-rest                       # Supabase REST API (PostgREST)
supabase-studio                     # Supabase Studio dashboard (optional)
```

## Architecture Overview

### Current Architecture (External Supabase)

```
┌─────────────────────────────────────────────────────────────────┐
│                    CORTEXREVIEW v1.0 (Current)                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐                │
│  │   API    │     │  Worker  │     │  Redis   │                │
│  │ (FastAPI)│────▶│(Celery)  │────▶│  (Queue) │                │
│  └─────┬────┘     └─────┬────┘     └──────────┘                │
│        │                │                                       │
│        ▼                ▼                                       │
│  ┌────────────────────────────────────┐                        │
│  │    EXTERNAL SUPABASE CLOUD         │                        │
│  │  ┌────────────────────────────┐   │                        │
│  │  │ PostgreSQL + pgvector      │   │                        │
│  │  │ - knowledge_base           │   │                        │
│  │  │ - learned_constraints      │   │                        │
│  │  │ - feedback_audit_log       │   │                        │
│  │  └────────────────────────────┘   │                        │
│  └────────────────────────────────────┘                        │
│           ▲                                                        │
│           │ https://xyz.supabase.co                              │
│           │                                                        │
└───────────┴──────────────────────────────────────────────────────┘
```

### Target Architecture (Local Supabase)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CORTEXREVIEW v2.0 (Target)                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌─────────────────┐   │
│  │   API    │     │  Worker  │     │  Redis   │     │   Prometheus    │   │
│  │ (FastAPI)│────▶│(Celery)  │────▶│  (Queue) │     │    (Metrics)    │   │
│  └─────┬────┘     └─────┬────┘     └──────────┘     └────────┬────────┘   │
│        │                │                                    │             │
│        ▼                ▼                                    ▼             │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │                    LOCAL SUPABASE (Docker)                       │      │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐   │      │
│  │  │    DB       │  │   Studio   │  │     REST API            │   │      │
│  │  │(PostgreSQL  │  │(Dashboard) │  │   (PostgREST)           │   │      │
│  │  │+ pgvector)  │  │  :8000     │  │    :8000                │   │      │
│  │  │             │  │            │  │                         │   │      │
│  │  │Tables:      │  │            │  │Auto-initialization:     │   │      │
│  │  │- knowledge  │  │            │  │- pgvector extension     │   │      │
│  │  │  _base      │  │            │  │- Schema creation        │   │      │
│  │  │- learned    │  │            │  │- Vector indexes         │   │      │
│  │  │  _constraints│  │            │  │- SQL functions          │   │      │
│  │  │- feedback   │  │            │  │- Pre-flight checks      │   │      │
│  │  │  _audit_log │  │            │  │                         │   │      │
│  │  └─────────────┘  └─────────────┘  └─────────────────────────┘   │      │
│  │                                                                      │      │
│  │  Persistent Volumes:                                                  │      │
│  │  - supabase-db-data (PostgreSQL data)                                │      │
│  │  - supabase-studio-data (Studio config)                              │      │
│  └──────────────────────────────────────────────────────────────────────┘      │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                         Grafana (Dashboards)                          │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  Shared Docker Network: cortexreview-network                                │
│  All containers communicate via service names (no external dependencies)     │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Key Differences

| Aspect | Current (External) | Target (Local) |
|--------|-------------------|----------------|
| Supabase Location | Cloud (xyz.supabase.co) | Local Docker container |
| Network Dependency | Internet required | Offline after initial pull |
| Data Sovereignty | Hosted by Supabase | Full control on-premise |
| Cost | Supabase Cloud pricing | Infrastructure only |
| Startup Sequence | External service availability | Local container health checks |
| Backup | Supabase managed | Manual pg_dump to local storage |
| Studio Access | Cloud URL | localhost:8000 |

## Implementation Phases

### Phase 0: Research & Discovery

**Goal**: Resolve all technical unknowns and document best practices for self-hosted Supabase deployment.

**Output**: `research.md` with:
- Supabase Docker image selection and versioning
- pgvector extension installation procedures
- Docker Compose service configuration patterns
- Database initialization automation approaches
- Pre-flight check implementation strategies
- Backup/restore procedures for PostgreSQL in Docker
- Migration strategies from external Supabase

**Research Tasks**:
1. Evaluate official Supabase Docker images vs community alternatives
2. Document pgvector installation and configuration for PostgreSQL 15
3. Research Docker Compose health check patterns for database services
4. Investigate container entrypoint scripts for schema initialization
5. Study PostgreSQL backup strategies in containerized environments
6. Analyze Supabase external-to-local migration patterns

### Phase 1: Design & Contracts

**Goal**: Create concrete design artifacts and API contracts for implementation.

**Output**:
- `data-model.md`: Database schema, vector indexes, SQL functions
- `contracts/`: Interface definitions for Supabase initialization, backup, migration
- `quickstart.md`: Developer onboarding guide

**Design Tasks**:
1. Define database schema (tables, columns, types, constraints)
2. Specify vector index configuration (IVFFlat parameters, dimensions)
3. Design SQL functions (match_knowledge, check_constraints)
4. Create Docker Compose service definitions
5. Specify environment variable schema
6. Design pre-flight check validation logic
7. Document backup/restore procedures
8. Create migration scripts from external Supabase

### Phase 2: Implementation (NOT COVERED BY THIS PLAN)

**Goal**: Implement the feature according to Phase 1 design.

**Output**: `tasks.md` (generated by `/speckit.tasks` command)

**Execution**: Run `/speckit.tasks` after completing Phase 1.

---

## Next Steps

1. **Phase 0**: Run research tasks to resolve technical unknowns
2. **Phase 1**: Generate design artifacts (data-model.md, contracts/, quickstart.md)
3. **Post-Phase 1**: Re-evaluate Constitution Check gates
4. **Phase 2**: Run `/speckit.tasks` to generate implementation task breakdown

**Command to continue**: Current command (`/speckit.plan`) will execute Phases 0 and 1 automatically.
