---

description: "Task breakdown for prompts and configuration refactoring"
---

# Tasks: Prompts and Configuration Refactoring

**Input**: Design documents from `/specs/001-prompts-config-refactor/`
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/openapi.yaml, research.md, quickstart.md

**Tests**: No automated tests included - manual testing via `/test` endpoint per specification (section "Testing")

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project structure**: All modules at repository root
- **Python modules**: `utils/`, `codereview/`, `gitea/`
- **Configuration**: `.env`, `docker-compose.yml`
- **Prompts**: `./prompts/` directory

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and verify dependencies

- [x] T001 Verify dependencies in requirements.txt include openai>=1.0.0, python-dotenv>=1.0.0, pyyaml
- [x] T002 Create prompts directory at ./prompts/ with README placeholder

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core configuration infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T003 Refactor Config class in utils/config.py to add LLM_PROVIDER, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL with strict priority (LLM_API_KEY > OPENAI_KEY > COPILOT_TOKEN)
- [x] T004 [P] Add Webhook class to utils/config.py for optional notification webhooks with is_init property
- [x] T005 [P] Add structured logging configuration in utils/logger.py with JSON formatter supporting request_id, latency_ms, status binding
- [x] T006 Verify .env.example includes all new environment variables (LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_PROVIDER)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Externalized Prompt Management (Priority: P1) 🎯 MVP

**Goal**: Enable repository maintainers to customize AI code review instructions by editing files in `./prompts/` directory without code changes

**Independent Test**: Edit `./prompts/code-review-pr.md` and verify the next code review uses updated prompt without container restart

### Implementation for User Story 1

- [x] T007 [P] [US1] Create utils/prompt_loader.py module with load_prompt() function signature
- [x] T008 [P] [US1] Implement _strip_yaml_front_matter() helper in utils/prompt_loader.py to remove --- delimited metadata
- [x] T009 [P] [US1] Implement _substitute_variables() helper in utils/prompt_loader.py with ${variable} regex replacement
- [x] T010 [US1] Implement load_prompt() main function in utils/prompt_loader.py with graceful degradation (fallback prompt on missing file)
- [x] T011 [P] [US1] Create default prompt file at prompts/code-review-pr.md with YAML front matter and ${locale} placeholder
- [x] T012 [US1] Extract hardcoded prompt from codereview/copilot.py:43-44 to prompts/code-review-pr.md
- [x] T013 [US1] Update codereview/copilot.py to call load_prompt("code-review-pr.md", context) instead of using hardcoded prompt
- [x] T014 [US1] Add logging to prompt_loader.py for WARNING level when using fallback prompts

**Checkpoint**: At this point, User Story 1 should be fully functional - prompts load from files with YAML stripping and variable substitution

---

## Phase 4: User Story 2 - Flexible LLM Provider Configuration (Priority: P2)

**Goal**: Enable DevOps engineers to switch LLM providers (OpenAI, Azure, Ollama, LocalAI) via environment variables

**Independent Test**: Set LLM_BASE_URL to local Ollama endpoint and verify requests go to local provider

### Implementation for User Story 2

- [x] T015 [P] [US2] Install openai>=1.0.0 package if not in requirements.txt
- [x] T016 [P] [US2] Update codereview/copilot.py imports to include OpenAI from openai package
- [x] T017 [US2] Refactor Copilot class in codereview/copilot.py to use Config.LLM_API_KEY and Config.LLM_BASE_URL
- [x] T018 [US2] Add 60-second timeout configuration to requests in codereview/copilot.py
- [x] T019 [US2] Update code_review() method in codereview/copilot.py to use Config.LLM_MODEL instead of hardcoded model
- [x] T020 [US2] Implement timeout error handling in code_review() to log WARNING and skip to next file per FR-016
- [x] T021 [US2] Add structured logging with request_id (UUID), latency_ms, and status for each LLM request in codereview/copilot.py
- [x] T022 [US2] Update main.py to pass Config instance to Copilot initialization instead of individual token parameter

**Checkpoint**: At this point, User Story 2 should work - LLM provider configurable via environment with timeout and structured logging

---

## Phase 5: User Story 3 - Container Deployment with Hot-Reload (Priority: P3)

**Goal**: Enable developers to iterate on prompts by editing files on host with immediate effect in running container

**Independent Test**: Run docker-compose up, edit prompts/code-review-pr.md on host, trigger webhook and verify new prompt used without restart

### Implementation for User Story 3

- [x] T023 [US3] Verify Dockerfile uses python:3.10-slim base image and copies all application code
- [x] T024 [P] [US3] Add ./prompts:/app/prompts volume mount to docker-compose.yml for hot-reload
- [x] T025 [P] [US3] Verify ./main.py:/app/main.py volume mount exists in docker-compose.yml
- [x] T026 [P] [US3] Update docker-compose.yml environment section to pass LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_PROVIDER variables
- [x] T027 [US3] Add prompts/ directory to .gitignore if not already present (to allow user-specific prompts)
- [x] T028 [US3] Update quickstart.md validation to verify hot-reload behavior works as documented

**Checkpoint**: At this point, User Story 3 should work - prompt file changes on host reflect in container immediately

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final improvements and validation

- [x] T029 [P] Update CLAUDE.md with refactored architecture documentation (remove hardcoded prompt references)
- [x] T030 [P] Update .env.example with all new variables including descriptions and defaults (done in T006)
- [x] T031 Run validation from quickstart.md: docker-compose up --build, verify startup without errors (COMPLETED: Container starts successfully)
- [x] T032 Manual test: Trigger /test endpoint with sample code and verify review is generated (COMPLETED: AI review working correctly)
- [ ] T033 Manual test: Edit prompts/code-review-pr.md and verify prompt hot-reloads without restart (PENDING: Requires testing)
- [x] T034 Manual test: Set LLM_BASE_URL to test provider switching and verify request goes to configured endpoint (COMPLETED: Works with OpenRouter/DeepSeek)
- [ ] T035 Manual test: Set OPENAI_KEY (without LLM_API_KEY) and verify deprecation warning appears in logs on startup (PENDING: Requires testing)
- [x] T036 Remove deprecated code comments and cleanup temporary debugging statements (VERIFIED: No temporary debugging statements found)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational completion - No dependencies on other user stories
- **User Story 2 (Phase 4)**: Depends on Foundational completion - Should be independently testable from US1
- **User Story 3 (Phase 5)**: Depends on Foundational completion - Should be independently testable from US1/US2
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Uses Config class but independent of prompt loading
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Only requires files to exist, independent of internal logic

### Within Each User Story

- **US1**: Helper functions (T008, T009) can run in parallel, then main function (T010), then integration (T011-T014)
- **US2**: Package install (T015) and imports (T016) parallel, then OpenAI client refactor (T017-T022)
- **US3**: Volume mounts (T024, T025) and env vars (T026) can be done in parallel

### Parallel Opportunities

- **Setup**: T001 and T002 can run in parallel
- **Foundational**: T004 (Webhook class) and T005 (logging) can run in parallel
- **User Story 1**: T008, T009, T011 (helper functions and file creation) can run in parallel
- **User Story 2**: T015 and T016 (package and imports) can run in parallel
- **User Story 3**: T024, T025, T026 (docker-compose edits) can run in parallel
- **Polish**: T029 and T030 (documentation) can run in parallel
- **With multiple developers**: US1, US2, US3 can be worked on in parallel after Foundational phase completes

---

## Parallel Example: User Story 1

```bash
# Launch helper functions and file creation together:
Task T008: "Implement _strip_yaml_front_matter() helper in utils/prompt_loader.py"
Task T009: "Implement _substitute_variables() helper in utils/prompt_loader.py"
Task T011: "Create default prompt file at prompts/code-review-pr.md"

# After helpers complete, launch main function:
Task T010: "Implement load_prompt() main function in utils/prompt_loader.py"

# Then integration tasks:
Task T012: "Extract hardcoded prompt from codereview/copilot.py"
Task T013: "Update codereview/copilot.py to call load_prompt()"
Task T014: "Add logging to prompt_loader.py"
```

---

## Parallel Example: User Story 2

```bash
# Launch package verification and imports together:
Task T015: "Install openai>=1.0.0 package if not in requirements.txt"
Task T016: "Update codereview/copilot.py imports to include OpenAI from openai package"

# After imports complete, launch client refactor:
Task T017: "Refactor Copilot class to use OpenAI client with Config"
Task T018: "Add 60-second timeout configuration"
Task T019: "Update code_review() to use Config.LLM_MODEL"
Task T020: "Implement timeout error handling"
Task T021: "Add structured logging with request_id, latency_ms, status"
Task T022: "Update main.py to pass Config instance to Copilot"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T002)
2. Complete Phase 2: Foundational (T003-T006) - CRITICAL
3. Complete Phase 3: User Story 1 (T007-T014)
4. **STOP and VALIDATE**: Test prompt externalization independently
5. Deploy/demo if ready

**MVP Validation Checklist**:
- [ ] Edit prompts/code-review-pr.md
- [ ] Trigger code review webhook
- [ ] Verify new prompt used without restart
- [ ] Verify fallback prompt works if file deleted

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test prompt externalization → Deploy/Demo (MVP!)
3. Add User Story 2 → Test provider switching → Deploy/Demo
4. Add User Story 3 → Test hot-reload → Deploy/Demo
5. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup (T001-T002) + Foundational (T003-T006) together
2. Once Foundational is done:
   - Developer A: User Story 1 (T007-T014) - Prompt externalization
   - Developer B: User Story 2 (T015-T022) - LLM provider config
   - Developer C: User Story 3 (T023-T028) - Docker hot-reload
3. Stories complete and integrate independently
4. Team converges for Polish phase (T029-T035)

---

## Notes

- **No automated tests**: Specification calls for manual testing via `/test` endpoint only
- **Graceful degradation**: Prompt loader must never crash - log WARNING and use fallbacks
- **Strict priority**: LLM_API_KEY > OPENAI_KEY > COPILOT_TOKEN (highest wins, ignore others)
- **60-second timeout**: LLM requests timeout per FR-016 clarification
- **Structured logging**: All LLM requests emit JSON logs with request_id, latency_ms, status
- **Hot-reload**: Volume mounts for ./prompts directory enable no-restart prompt changes
- **Constitution compliance**: All tasks follow Configuration as Code and Prompts as Data principles
- **Commit strategy**: Commit after each task or logical group for easier rollback
- **Checkpoints**: Stop at each checkpoint to validate story independence
