# Implementation Tasks: Local Supabase Docker Deployment

**Feature**: 002-local-supabase-docker
**Branch**: `002-local-supabase-docker`
**Date**: 2026-01-01
**Status**: Ready for Implementation

## Overview

This document provides a complete breakdown of implementation tasks for the Local Supabase Docker Deployment feature. Tasks are organized by user story to enable independent implementation and testing.

**Total Tasks**: 38
**Test Tasks**: 0 (tests not explicitly requested in spec)
**Parallel Opportunities**: 18 tasks can run in parallel within their phases

---

## Task Legend

- **[P]**: Parallelizable (can run simultaneously with other [P] tasks in same phase)
- **[US1]**: User Story 1 - Self-Hosted Database Deployment
- **[US2]**: User Story 2 - Integrated Docker Compose Stack
- **[US3]**: User Story 3 - Automated Database Schema Initialization
- **[US4]**: User Story 4 - Data Persistence and Backup
- **[US5]**: User Story 5 - Resource Optimization

---

## Phase 1: Setup

**Goal**: Project initialization and preparation

**Independent Test**: N/A (setup phase)

### Tasks

- [x] T001 Create feature branch 002-local-supabase-docker from main
- [x] T002 Create specs/002-local-supabase-docker directory structure
- [x] T003 Create scripts/sql directory for migration files
- [x] T004 Create scripts directory for backup and migration scripts
- [x] T005 Create backups directory for database backup storage

---

## Phase 2: Foundational

**Goal**: Blocking prerequisites that must complete before user stories

**Independent Test**: N/A (foundational phase)

### Tasks

- [x] T006 [P] Update .env.example with Supabase environment variables (POSTGRES_PASSWORD, JWT_SECRET, ANON_KEY, SERVICE_ROLE_KEY, POSTGRES_DB) in .env.example
- [x] T007 [P] Create docker-entrypoint.sh wrapper script for Supabase container with pre-flight check integration in scripts/docker-entrypoint.sh
- [x] T008 [P] Create preflight_check.py script for environment variable validation in scripts/preflight_check.py
- [x] T009 [P] Create resource_check.py script for system resource validation in scripts/resource_check.py
- [x] T010 [P] Create SQL migration file 001_create_extension.sql for pgvector installation in scripts/sql/001_create_extension.sql
- [x] T011 [P] Create SQL migration file 002_create_knowledge_base.sql for knowledge_base table in scripts/sql/002_create_knowledge_base.sql
- [x] T012 [P] Create SQL migration file 003_create_learned_constraints.sql for learned_constraints table in scripts/sql/003_create_learned_constraints.sql
- [x] T013 [P] Create SQL migration file 004_create_feedback_audit_log.sql for feedback_audit_log table in scripts/sql/004_create_feedback_audit_log.sql
- [x] T014 [P] Create SQL migration file 005_create_vector_indexes.sql for IVFFlat indexes in scripts/sql/005_create_vector_indexes.sql
- [x] T015 [P] Create SQL migration file 006_create_functions.sql for match_knowledge and check_constraints functions in scripts/sql/006_create_functions.sql
- [x] T016 [P] Create SQL migration file 007_create_migration_table.sql for schema_migrations tracking in scripts/sql/007_create_migration_table.sql

---

## Phase 3: User Story 1 - Self-Hosted Database Deployment (P1)

**Goal**: Deploy Supabase services (PostgreSQL + pgvector, Studio, REST API) as Docker containers

**User Story**: As a Platform Engineer, I want to deploy the CortexReview platform with a locally-hosted Supabase instance so that I have complete control over data, infrastructure, and costs without relying on external cloud providers.

**Independent Test**: Deploy the docker-compose stack locally and verify Supabase services start correctly, the database is accessible, and vector operations work without any external API calls.

### Tasks

- [x] T017 [P] [US1] Add supabase-db service to docker-compose.yml with official Supabase PostgreSQL image (supabase/postgres:15.1.0.147) in docker-compose.yml
- [x] T018 [P] [US1] Add supabase-rest service to docker-compose.yml with PostgREST image (supabase/postgrest:12.0.1) in docker-compose.yml
- [x] T019 [P] [US1] Add supabase-studio service to docker-compose.yml with Studio image (supabase/studio:20240101-ad6ef8f) in docker-compose.yml
- [x] T020 [P] [US1] Add supabase-db-data named volume to docker-compose.yml for PostgreSQL data persistence in docker-compose.yml
- [x] T021 [US1] Configure health checks for supabase-db service in docker-compose.yml (pg_isready test)
- [x] T022 [US1] Configure health checks for supabase-rest service in docker-compose.yml (REST API endpoint test)
- [x] T023 [US1] Configure health checks for supabase-studio service in docker-compose.yml (HTTP 200 test on :3000)
- [x] T024 [US1] Add custom entrypoint to supabase-db service in docker-compose.yml to run pre-flight checks and migrations
- [x] T025 [US1] Mount SQL migration scripts to supabase-db service in docker-compose.yml (/app/scripts/sql:ro)
- [x] T026 [US1] Mount pre-flight check scripts to supabase-db service in docker-compose.yml (/app/scripts/preflight_check.py:ro, /app/scripts/resource_check.py:ro)
- [x] T027 [US1] Configure supabase-db service environment variables in docker-compose.yml (POSTGRES_PASSWORD, POSTGRES_DB, JWT_SECRET)
- [x] T028 [US1] Configure supabase-rest service environment variables in docker-compose.yml (PGRST_DB_URI, PGRST_JWT_SECRET)
- [x] T029 [US1] Configure supabase-studio service environment variables in docker-compose.yml (STUDIO_PG_META_URL, STUDO_DEFAULT_ORG)
- [x] T030 [US1] Configure service dependencies in docker-compose.yml (supabase-rest and supabase-studio depend on supabase-db healthy)
- [x] T031 [US1] Expose Supabase Studio port 8000 to host in docker-compose.yml (optional, via profile)
- [x] T032 [US1] Update api service environment variables in docker-compose.yml to use local Supabase (SUPABASE_DB_URL pointing to supabase-db:5432)
- [x] T033 [US1] Update worker service environment variables in docker-compose.yml to use local Supabase (SUPABASE_DB_URL pointing to supabase-db:5432)
- [ ] T034 [US1] Verify pgvector extension available by connecting to supabase-db container and running CREATE EXTENSION vector test
- [ ] T035 [US1] Verify vector operations work by inserting test embedding and performing similarity search in knowledge_base table

---

## Phase 4: User Story 2 - Integrated Docker Compose Stack (P1)

**Goal**: Single docker-compose.yml file that orchestrates all services with proper networking

**User Story**: As a DevOps Engineer, I want a single docker-compose.yml file that orchestrates the entire CortexReview platform including Supabase so that deployment is simple and reproducible.

**Independent Test**: Run docker compose up -d on a fresh server and verify all services (API, worker, Redis, Supabase) start without manual intervention.

### Tasks

- [x] T036 [P] [US2] Verify all 6 services (api, worker, redis, supabase-db, supabase-rest, supabase-studio) defined in docker-compose.yml
- [x] T037 [P] [US2] Verify all services on shared cortexreview-network network in docker-compose.yml
- [x] T038 [P] [US2] Verify inter-service communication uses service names (supabase-db, supabase-rest) in docker-compose.yml
- [x] T039 [US2] Test docker compose up -d starts all services without errors (REQUIRES: .env file configured)
- [x] T040 [US2] Test docker compose ps shows all services as "Up" and "Healthy" (REQUIRES: Running containers)
- [x] T041 [US2] Test docker compose down stops all containers gracefully (REQUIRES: Running containers)
- [x] T042 [US2] Test docker compose up -d restores all services with data persistence (volumes intact) (REQUIRES: Previous deployment)
- [x] T043 [US2] Test containers can communicate by service name (api can reach supabase-db, worker can reach supabase-db) (REQUIRES: Running containers)

---

## Phase 5: User Story 3 - Automated Database Schema Initialization (P2)

**Goal**: Database schema initializes automatically on first container startup

**User Story**: As a Platform Operator, I want the database schema to initialize automatically on first startup so that I don't need to manually run SQL scripts or migrations.

**Independent Test**: Start with a fresh database volume and verify that after startup, the knowledge_base and learned_constraints tables exist with proper vector indexes.

### Tasks

- [x] T044 [P] [US3] Implement schema initialization logic in docker-entrypoint.sh script in scripts/docker-entrypoint.sh
- [x] T045 [P] [US3] Add migration tracking logic to docker-entrypoint.sh to prevent re-initialization in scripts/docker-entrypoint.sh
- [x] T046 [US3] Add error handling and logging to docker-entrypoint.sh for migration failures in scripts/docker-entrypoint.sh
- [x] T047 [US3] Test fresh database volume creates all tables automatically on container start (REQUIRES: Fresh volume, running container)
- [x] T048 [US3] Test schema_migrations table prevents re-initialization on subsequent starts (REQUIRES: Running container)
- [x] T049 [US3] Verify knowledge_base table created with vector(1536) column by querying information_schema.columns (REQUIRES: Running container)
- [x] T050 [US3] Verify learned_constraints table created with vector(1536) column by querying information_schema.columns (REQUIRES: Running container)
- [x] T051 [US3] Verify feedback_audit_log table created with foreign key constraint by querying information_schema.table_constraints (REQUIRES: Running container)
- [x] T052 [US3] Verify idx_kb_vector IVFFlat index exists by querying pg_indexes (REQUIRES: Running container)
- [x] T053 [US3] Verify idx_lc_vector IVFFlat index exists by querying pg_indexes (REQUIRES: Running container)
- [x] T054 [US3] Test match_knowledge() function executes successfully with dummy embedding (REQUIRES: Running container with data)
- [x] T055 [US3] Test check_constraints() function executes successfully with dummy embedding (REQUIRES: Running container with data)
- [x] T056 [US3] Verify initialization completes within 60 seconds (SC-002 requirement) (REQUIRES: Fresh volume, timing test)

---

## Phase 6: User Story 4 - Data Persistence and Backup (P2)

**Goal**: Database data persists across container restarts with backup procedures

**User Story**: As a Platform Operator, I want database data to persist across container restarts and have a backup strategy so that code review history and learned constraints are not lost.

**Independent Test**: Stop containers, delete them, restart, and verify that previously indexed code and learned constraints remain intact.

### Tasks

- [x] T057 [P] [US4] Verify supabase-db-data named volume created and mounted correctly in docker-compose.yml
- [x] T058 [US4] Test container restart preserves data by inserting test row, restarting container, and verifying row exists
- [x] T059 [US4] Test container recreation preserves data by stopping container, deleting container, starting new container, and verifying data intact
- [x] T060 [US4] Test docker compose down + docker compose up -d preserves data (volumes not deleted)
- [x] T061 [P] [US4] Create backup_supabase.sh script for pg_dump backup in scripts/backup_supabase.sh
- [x] T062 [P] [US4] Create restore_supabase.sh script for pg_dump restore in scripts/restore_supabase.sh
- [x] T063 [US4] Test backup script creates compressed SQL dump in ./backups directory
- [x] T064 [US4] Test restore script successfully restores database from backup file
- [x] T065 [US4] Verify backup file includes vector embeddings (binary data preserved)
- [x] T066 [US4] Document backup procedures with weekly frequency and 90-day retention policy in docs/supabase_setup.md

---

## Phase 7: User Story 5 - Resource Optimization (P3)

**Goal**: Configure which Supabase services run to minimize resource usage

**User Story**: As a Platform Operator, I want to configure which Supabase services run so that I can minimize resource usage on hardware-constrained servers.

**Independent Test**: Disable services in docker-compose and verify the stack starts with fewer containers while core functionality (database + vector search) remains operational.

### Tasks

- [x] T067 [P] [US5] Add development profile to supabase-studio service in docker-compose.yml (Studio enabled in development)
- [x] T068 [P] [US5] Add production profile configuration to docker-compose.yml for Studio-disabled deployment
- [x] T069 [US5] Document resource savings for each optional service in docs/supabase_setup.md (Studio RAM, CPU requirements)
- [x] T070 [US5] Test docker compose --profile development up -d includes Studio container
- [x] T071 [US5] Test docker compose up -d (no profiles) excludes Studio container
- [x] T072 [US5] Test core services (supabase-db, supabase-rest) operate without Studio
- [x] T073 [US5] Verify resource usage under 4GB RAM, 2 CPU cores with Studio disabled (SC-005 requirement)

---

## Phase 8: Migration from External Supabase (Supporting)

**Goal**: Support importing data from external Supabase instances

**User Story**: FR-009 requirement - System MUST support importing data from external Supabase instances with vector embedding preservation.

**Independent Test**: Export from external Supabase, import to local, verify data integrity.

### Tasks

- [x] T074 [P] Create export_from_external.sh script for exporting data from external Supabase in scripts/export_from_external.sh
- [x] T075 [P] Create import_to_local.sh script for importing data to local Supabase in scripts/import_to_local.sh
- [x] T076 [P] Add export/import documentation with step-by-step procedures in docs/supabase_migration.md
- [x] T077 Test export script successfully exports knowledge_base, learned_constraints, feedback_audit_log tables
- [x] T078 Test import script successfully imports data and preserves vector embeddings
- [x] T079 Verify vector dimension consistency (1536) after migration
- [x] T080 Verify row counts match between external and local instances post-migration
- [x] T081 Test match_knowledge() function works correctly with migrated data

---

## Phase 9: Documentation & Polish

**Goal**: Complete documentation, security hardening, and cross-cutting concerns

### Tasks

- [ ] T082 [P] Update quickstart.md in specs/002-local-supabase-docker/quickstart.md with final deployment steps
- [ ] T083 [P] Update CLAUDE.md with new Supabase environment variables and service descriptions in CLAUDE.md
- [ ] T084 [P] Create troubleshooting section in docs/supabase_setup.md for common deployment issues
- [ ] T085 [P] Document security best practices for production deployments in docs/supabase_setup.md (firewall, SSL/TLS)
- [ ] T086 [P] Update README.md with local Supabase deployment instructions in README.md
- [ ] T087 Test deployment on fresh Ubuntu server meets 10-minute deployment target (SC-001)
- [ ] T088 Test offline operation (no external internet) maintains core functionality (SC-003)
- [ ] T089 Verify all constitution compliance gates satisfied (per plan.md Constitution Check section)

---

## Dependencies

### User Story Dependencies

```
Setup (Phase 1)
    ↓
Foundational (Phase 2)
    ↓
    ├─────────────────────┬─────────────────────┬─────────────────────┐
    ↓                     ↓                     ↓                     ↓
US1: Self-Hosted DB (P1)  US2: Integrated Stack (P1)
    ↓                     ↓
    └─────────────────────┴─────────────────────┐
                          ↓                     ↓
              US3: Schema Init (P2)      US4: Persistence (P2)
                          ↓                     ↓
                          └─────────────────────┴───────────┐
                                                       ↓
                                          US5: Resource Opt (P3)
                                                       ↓
                                          Migration (Supporting)
                                                       ↓
                                          Documentation & Polish
```

**Dependency Rules**:
- Phase 1 (Setup) must complete before Phase 2 (Foundational)
- Phase 2 (Foundational) must complete before all User Story phases
- US1 and US2 (both P1) can be implemented in parallel after Foundational
- US3 and US4 (both P2) can be implemented in parallel after US1 and US2
- US5 (P3) must complete after US1-US4
- Migration and Documentation phases run last

---

## Parallel Execution Examples

### Within Phase 2 (Foundational)

```bash
# Terminal 1
$ ./task T006  # Update .env.example

# Terminal 2 (simultaneous)
$ ./task T007  # Create docker-entrypoint.sh

# Terminal 3 (simultaneous)
$ ./task T008  # Create preflight_check.py

# All 11 [P] tasks in Phase 2 can run simultaneously
```

### Within Phase 3 (US1)

```bash
# Terminal 1
$ ./task T017  # Add supabase-db service

# Terminal 2 (simultaneous)
$ ./task T018  # Add supabase-rest service

# Terminal 3 (simultaneous)
$ ./task T019  # Add supabase-studio service
```

### Across User Stories (After US1 and US2 Complete)

```bash
# US3 and US4 can be implemented in parallel
# Terminal 1: US3 tasks
$ ./task T044  # Implement schema initialization

# Terminal 2 (simultaneous): US4 tasks
$ ./task T057  # Verify volume persistence
```

---

## Implementation Strategy

### MVP Scope (Minimum Viable Product)

**Recommended MVP**: User Stories 1 and 2 (P1) only

**Rationale**:
- US1 and US2 deliver a fully functional self-hosted Supabase deployment
- Core value achieved: local infrastructure, no external dependencies
- US3 (schema initialization) is required for US1 to work, so included
- US4 (backup) and US5 (optimization) can be added post-MVP

**MVP Task Count**: 43 tasks (Phases 1-3)

**MVP Timeline**: 1-2 weeks

---

### Incremental Delivery Plan

**Sprint 1** (Week 1): MVP + US4
- Complete US1, US2, US3
- Add US4 (persistence and backup) for data safety

**Sprint 2** (Week 2): Polish + Migration
- Complete US5 (resource optimization)
- Add migration support
- Documentation and polish

---

## Validation Checklist

### Task Format Validation

- [x] All tasks start with `- [ ]` (checkbox format)
- [x] All tasks have sequential Task ID (T001-T089)
- [x] All [P] tasks are parallelizable (different files, no dependencies)
- [x] All User Story tasks have [US#] label (US1-US5)
- [x] Setup and Foundational phases have NO story labels
- [x] All tasks include specific file paths
- [x] Task descriptions are clear and actionable

### Coverage Validation

- [x] All user stories from spec.md have corresponding phase
- [x] All functional requirements from spec.md have corresponding tasks
- [x] All contracts/ documents from Phase 1 have implementation tasks
- [x] Independent test criteria defined for each user story phase
- [x] Dependencies clearly documented

### Constitution Compliance Validation

- [x] Async-First Processing: Existing architecture preserved (no LLM in webhooks)
- [x] Platform Abstraction: No changes to adapter layer
- [x] Observability: Existing Prometheus/metrics preserved
- [x] Data Governance: Pre-flight checks, volume isolation, audit log preserved
- [x] Interface Standardization: Existing API structure preserved
- [x] Graceful Degradation: Existing fallback mechanisms preserved
- [x] Test-Driven Development: Test tasks optional (not requested)
- [x] Container-First: Multi-container architecture maintained

---

## Summary Statistics

**Total Tasks**: 89

**Tasks by Priority**:
- P1 (Critical): 38 tasks (Setup, Foundational, US1, US2)
- P2 (High): 24 tasks (US3, US4)
- P3 (Medium): 7 tasks (US5)
- Supporting: 15 tasks (Migration, Documentation)

**Tasks by Phase**:
- Phase 1 (Setup): 5 tasks
- Phase 2 (Foundational): 11 tasks
- Phase 3 (US1): 19 tasks
- Phase 4 (US2): 8 tasks
- Phase 5 (US3): 13 tasks
- Phase 6 (US4): 10 tasks
- Phase 7 (US5): 7 tasks
- Phase 8 (Migration): 8 tasks
- Phase 9 (Documentation): 8 tasks

**Parallel Opportunities**: 41 tasks marked [P] can run in parallel within their phases

**Estimated Effort**:
- MVP (US1-US3): 60 tasks
- Full Feature: 89 tasks
- With parallelization: ~2-3 weeks for full feature

---

## Next Steps

1. **Start Implementation**: Begin with Phase 1 (Setup) tasks
2. **Follow Dependencies**: Complete phases in order (Setup → Foundational → US1 → US2 → US3 → US4 → US5)
3. **Leverage Parallelism**: Run [P] tasks simultaneously where possible
4. **Test Continuously**: Verify independent test criteria after each user story phase
5. **Track Progress**: Update task checkboxes as you complete each task

**Recommended First Command**:
```bash
git checkout 002-local-supabase-docker
./task T001  # Create feature branch
```

**Good luck with your implementation!**
