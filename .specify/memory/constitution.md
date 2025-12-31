# Gitea AI Code Reviewer Constitution
<!--
Sync Impact Report:
- Version change: Initial → 2.0.0
- Added sections: All core principles (I-VI), Must-Haves, Should-Haves, Prohibited Actions, Governance
- Ratified: 2025-01-01
- Templates updated:
  - spec-template.md: Aligned with Graceful Degradation and Configuration as Code principles
  - plan-template.md: Constitution Check section validates against Must-Haves
  - tasks-template.md: Task organization supports modular service architecture
- No placeholders deferred
-->

## Core Principles

### I. Configuration as Code
All environment-specific settings MUST be externalized to `.env` files. The system MUST NOT hardcode API keys, URLs, model names, or other deployment-specific values in source code. Configuration MUST be centralized through a single `Config` class using `python-dotenv`.

**Rationale**: Enables seamless deployment across environments (development, staging, production) without code changes. Prevents accidental credential exposure in version control. Supports multiple LLM providers through environment variable substitution.

### II. Prompts as Data
AI system prompts are configuration assets, NOT code. They MUST be stored in `./prompts/` directory as Markdown files and loaded at runtime. Prompts MUST support YAML Front Matter for metadata and variable substitution for dynamic content.

**Rationale**: Decouples prompt engineering from code logic. Enables non-technical users to modify AI behavior without deployments. Supports version control and A/B testing of different prompt strategies. Hot-reloading in containerized environments.

### III. Container-First
The application MUST always run inside a Docker container. Development and production environments MUST be identical. The container MUST use the official `python:3.10-slim` base image and expose port 3008 for webhook reception.

**Rationale**: Eliminates "works on my machine" problems. Ensures consistent dependency management. Simplifies deployment scaling. Volume mounts for prompt hot-reloading enable rapid iteration without rebuilds.

### IV. Graceful Degradation
If a specific asset (like a custom prompt file) is missing, the system MUST fallback to a safe default rather than crashing. Missing configuration MUST trigger a WARNING log with clear guidance on required action. Critical errors MUST prevent startup with actionable error messages.

**Rationale**: System resilience for partial deployments. Enables staged configuration rollout. Prevents cascade failures from non-critical asset issues. Clear error messaging reduces debugging time.

### V. OpenAI-Compatible API
LLM integration MUST use the OpenAI client interface with `base_url` and `api_key` configuration. This enables compatibility with OpenAI, Azure OpenAI, local LLMs (Ollama, LocalAI), and enterprise proxies without code changes.

**Rationale**: Future-proofs against LLM provider changes. Supports local development without API costs. Enables enterprise deployment through standard proxy patterns. Reduces vendor lock-in.

### VI. Modular Service Architecture
The codebase MUST follow modular separation: configuration utilities, prompt loading, Gitea API client, and AI provider abstraction. Each module MUST have clear interfaces and independent testability.

**Rationale**: Enables isolated testing and development. Supports swapping components (e.g., AI providers) without touching core logic. Reduces cognitive load when modifying specific functionality.

## Must-Haves (Hard Constraints)

### Prompt Management
- MUST: Never hardcode system prompts as multi-line strings in `main.py`
- MUST: Use the `load_prompt(filename, context)` utility to fetch instruction text
- MUST: Support YAML Front Matter stripping—AI API must not receive `---` metadata markers
- MUST: Support Variable Substitution—replace `${variable}` placeholders from context dictionary
- MUST: Default `./prompts/code-review-pr.md` must exist in the repository

### Configuration Management
- MUST: Use `python-dotenv` to load environment variables
- MUST: Utilize a `Config` class (or dataclass) to centralize variable access—do not scatter `os.getenv` calls
- MUST: Support `LLM_BASE_URL` for local LLMs and enterprise proxies
- MUST: Maintain backward compatibility—if `LLM_API_KEY` is missing, check legacy `OPENAI_KEY`

### LLM Integration
- MUST: Initialize LLM Client using `base_url` and `api_key` from Config object
- MUST: Construct messages array with prompt loaded from file passed as `role: system`
- MUST: Handle authentication failures with token renewal where applicable

### Docker & Deployment
- MUST: Use `Dockerfile` based on `python:3.10-slim`
- MUST: Use `docker-compose.yml` with proper network configuration
- MUST: Mount `./prompts` directory as volume for hot-reloading
- MUST: Expose port 3008 for webhook listener

## Should-Haves (Soft Constraints)

- **Type Hinting**: All functions MUST use Python type hints (`str`, `dict`, `Optional`) for IDE support
- **Error Logging**: If prompt file fails to load, log WARNING indicating fallback is in use
- **Documentation**: Update `README.md` when adding new environment variables
- **PEP 8**: Adhere to Python style guidelines (line length < 100 chars, `snake_case` naming)

## Refactoring Context

**Current Phase**: Moving from Monolithic Script to Modular Service

When modifying the codebase:
1. Identify hardcoded AI instruction strings → move to `./prompts/code-review-pr.md`
2. Identify direct API key usage → move to `.env` and load via Config
3. Verify Docker container rebuilds successfully (`docker-compose up --build`)

## Prohibited Actions

- DO NOT commit real API keys or secrets to the repository
- DO NOT modify exposed port 3008 without updating `docker-compose.yml` and documentation
- DO NOT remove error handling for `load_prompt` function—missing files must NOT crash the app
- DO NOT scatter `os.getenv` calls—centralize through Config class only

## Governance

This Constitution supersedes all other development practices. Any conflict between this document and external guidance MUST be resolved in favor of Constitution principles.

### Amendment Procedure
1. Propose amendment with rationale and impact analysis
2. Document version bump according to semantic versioning:
   - **MAJOR**: Backward-incompatible governance/principle removals or redefinitions
   - **MINOR**: New principle/section added or materially expanded guidance
   - **PATCH**: Clarifications, wording fixes, non-semantic refinements
3. Update dependent templates (spec, plan, tasks) to reflect changes
4. Update `LAST_AMENDED_DATE` and increment `CONSTITUTION_VERSION`

### Compliance Review
All pull requests MUST verify compliance with Must-Haves before merge. Complexity violations MUST be justified with explicit rationale in implementation plan. Use `CLAUDE.md` for runtime development guidance not covered here.

**Version**: 2.0.0 | **Ratified**: 2025-01-01 | **Last Amended**: 2025-01-01
