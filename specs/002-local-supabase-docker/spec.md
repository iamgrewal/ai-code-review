# Feature Specification: Local Supabase Docker Deployment

**Feature Branch**: `002-local-supabase-docker`
**Created**: 2026-01-01
**Status**: Draft
**Input**: User description: "for Local first self dependent platform build supabase docker locally and run it on the local ubuntu server as a docker using docker compose to serve the project. This will avoid dependency on the external supabase provider"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Self-Hosted Database Deployment (Priority: P1)

As a **Platform Engineer**, I want to deploy the CortexReview platform with a locally-hosted Supabase instance so that I have complete control over data, infrastructure, and costs without relying on external cloud providers.

**Why this priority**: This is foundational for self-sufficiency. Removing dependency on external Supabase hosting reduces costs, eliminates vendor lock-in, and ensures data sovereignty. It enables the platform to run entirely on local infrastructure.

**Independent Test**: Can be tested by deploying the docker-compose stack locally and verifying Supabase services start correctly, the database is accessible, and vector operations work without any external API calls.

**Acceptance Scenarios**:

1. **Given** a local Ubuntu server with Docker installed, **When** the docker-compose stack is started, **Then** all Supabase services (PostgreSQL, Studio, API, Realtime) start successfully and report healthy status
2. **Given** the Supabase containers are running, **When** accessing Supabase Studio, **Then** the dashboard loads at http://localhost:8000 with configured credentials
3. **Given** the local Supabase instance, **When** the CortexReview API connects, **Then** it can create tables, insert vector embeddings, and perform similarity searches
4. **Given** the system is running, **When** external internet connectivity is lost, **Then** all features continue to function (webhook processing, code review, RAG context retrieval)

---

### User Story 2 - Integrated Docker Compose Stack (Priority: P1)

As a **DevOps Engineer**, I want a single docker-compose.yml file that orchestrates the entire CortexReview platform including Supabase so that deployment is simple and reproducible.

**Why this priority**: Simplification of deployment is critical for adoption. A single compose file eliminates manual setup steps, reduces configuration errors, and ensures all services are properly networked together.

**Independent Test**: Can be tested by running `docker compose up -d` on a fresh server and verifying all services (API, worker, Redis, Supabase) start without manual intervention.

**Acceptance Scenarios**:

1. **Given** a fresh Ubuntu server, **When** docker-compose is executed, **Then** all 6 services start: API, worker, Redis, Supabase DB, Supabase Studio, Supabase REST API
2. **Given** the docker-compose stack is running, **When** containers are inspected, **Then** they are all on the same Docker network and can communicate by service name
3. **Given** the stack is running, **When** `docker compose down` is executed, **Then** all containers stop gracefully and data volumes persist for next startup
4. **Given** environment variables are configured, **When** containers start, **Then** Supabase auto-initializes with pgvector extension and required schema

---

### User Story 3 - Automated Database Schema Initialization (Priority: P2)

As a **Platform Operator**, I want the database schema to initialize automatically on first startup so that I don't need to manually run SQL scripts or migrations.

**Why this priority**: Automation reduces deployment errors and ensures consistency across environments. Manual schema setup is error-prone and creates a barrier to entry.

**Independent Test**: Can be tested by starting with a fresh database volume and verifying that after startup, the knowledge_base and learned_constraints tables exist with proper vector indexes.

**Acceptance Scenarios**:

1. **Given** a fresh Supabase deployment, **When** containers start for the first time, **Then** the pgvector extension is automatically installed
2. **Given** the extension is installed, **When** initialization completes, **Then** the knowledge_base and learned_constraints tables exist with proper schema
3. **Given** the tables exist, **When** queried, **Then** the ivfflat vector indexes are present and functional
4. **Given** the schema is initialized, **When** the match_knowledge and check_constraints functions are called, **Then** they return valid results

---

### User Story 4 - Data Persistence and Backup (Priority: P2)

As a **Platform Operator**, I want database data to persist across container restarts and have a backup strategy so that code review history and learned constraints are not lost.

**Why this priority**: Data persistence is essential for the learning loop functionality. Losing embeddings or learned constraints would reset the system's "memory" and waste all prior feedback.

**Independent Test**: Can be tested by stopping containers, deleting them, restarting, and verifying that previously indexed code and learned constraints remain intact.

**Acceptance Scenarios**:

1. **Given** the system has indexed repositories and stored learned constraints, **When** containers are restarted, **Then** all data remains accessible
2. **Given** data volumes persist, **When** `docker compose down` and `docker compose up -d` are executed, **Then** the system resumes without data loss
3. **Given** the system is running, **When** a backup is triggered, **Then** a PostgreSQL dump is created and stored in a configured backup location
4. **Given** a backup exists, **When** a restore is performed, **Then** the database returns to the backed-up state

---

### User Story 5 - Resource Optimization (Priority: P3)

As a **Platform Operator**, I want to configure which Supabase services run so that I can minimize resource usage on hardware-constrained servers.

**Why this priority**: Not all deployments need every Supabase service. Disabling unused features (like real-time subscriptions or storage) reduces memory and CPU requirements.

**Independent Test**: Can be tested by disabling services in docker-compose and verifying the stack starts with fewer containers while core functionality (database + vector search) remains operational.

**Acceptance Scenarios**:

1. **Given** a resource-constrained server, **When** optional services are disabled, **Then** only core services (DB, API, Studio) start
2. **Given** Studio is disabled, **When** the stack runs, **Then** the database and API remain accessible programmatically
3. **Given** Realtime is disabled, **When** the system operates, **Then** code review functionality is unaffected
4. **Given** Storage is disabled, **When** embeddings are stored, **Then** they use the database directly without file storage

---

### Edge Cases

**EC-001: Insufficient system resources**
- **Scenario**: Server has less than 4GB RAM or 2 CPU cores
- **Resolution**: Automated pre-flight check during container startup displays warning and suggests minimum resources; optional services can be disabled to reduce footprint

**EC-002: Port conflicts on host**
- **Scenario**: Required ports (5432, 8000, 3000) are already in use
- **Resolution**: Docker compose fails with clear error message indicating which ports conflict; documentation provides guidance on port remapping

**EC-003: Database initialization failure**
- **Scenario**: Schema initialization script fails due to syntax error or permission issue
- **Resolution**: Container logs show detailed error; initialization can be retried with `docker compose restart db`; manual SQL execution option documented

**EC-004: Volume permission errors**
- **Scenario**: Database volume has incorrect permissions preventing writes
- **Resolution**: Container fails to start with permission error; fix with `chown` command on volume directory or run with correct user ID via PGID environment variable

**EC-005: pgvector extension not available**
- **Scenario**: pgvector extension fails to install (missing in base image)
- **Resolution**: Use official Supabase Docker image which includes pgvector; fallback to manual extension installation documented in troubleshooting

**EC-006: Environment variable misconfiguration**
- **Scenario**: Required Supabase environment variables (JWT_SECRET, POSTGRES_PASSWORD) are unset or weak
- **Resolution**: Automated pre-flight check during container startup validates all required variables; fails fast with clear error listing missing variables

**EC-007: Network isolation issues**
- **Scenario**: API container cannot reach Supabase DB container
- **Resolution**: Containers must be on same Docker network; docker-compose handles this automatically; manual setup requires explicit network configuration

**EC-008: Data volume corruption**
- **Scenario**: Database volume becomes corrupted after unclean shutdown
- **Resolution**: PostgreSQL recovery runs on startup; if recovery fails, backup restore is required; documentation includes recovery procedures

## Requirements *(mandatory)*

### Functional Requirements

**FR-001: Local Supabase Deployment**
- System MUST deploy Supabase services using Docker containers
- System MUST use official Supabase Docker images for compatibility
- System MUST configure Supabase to run entirely on local infrastructure
- System MUST NOT require connectivity to external Supabase Cloud services

**FR-002: Integrated Docker Compose Configuration**
- System MUST provide a single docker-compose.yml file that orchestrates all services
- System MUST include the following services: API, worker, Redis, Supabase DB, Supabase Studio, Supabase REST API
- System MUST configure services on a shared Docker network for internal communication
- System MUST expose only necessary ports to the host (8000, 3000, optional 5432)

**FR-003: Automated Schema Initialization**
- System MUST automatically install pgvector extension on database startup
- System MUST create knowledge_base table with vector embedding column
- System MUST create learned_constraints table with vector embedding column
- System MUST create ivfflat vector indexes on both tables
- System MUST register match_knowledge and check_constraints SQL functions
- System MUST initialize schema on first container startup without manual intervention

**FR-004: Data Persistence**
- System MUST use named Docker volumes for database data storage
- System MUST persist data across container restarts and recreations
- System MUST support volume backup and restore procedures
- System MUST document backup procedures in operations guide
- System MUST recommend weekly backup frequency with 90-day retention policy

**FR-005: Environment Configuration**
- System MUST accept Supabase configuration via environment variables
- System MUST require configuration of: POSTGRES_PASSWORD, JWT_SECRET, ANON_KEY, SERVICE_ROLE_KEY
- System MUST provide .env.example file with all required variables documented
- System MUST validate required variables during container startup before services start
- System MUST fail fast with clear error messages if required variables are missing

**FR-006: Service Health Monitoring**
- System MUST configure health checks for all Supabase containers
- System MUST report unhealthy status if critical services fail
- System MUST log container health status for debugging
- System MUST support graceful shutdown of all services

**FR-007: Optional Service Configuration**
- System MUST support disabling optional Supabase services (Studio, Realtime, Storage)
- System MUST maintain core functionality (DB + vector search) when optional services are disabled
- System MUST document resource savings for each optional service

**FR-008: Security Configuration**
- System MUST generate secure default secrets on first startup
- System MUST allow override of all secrets via environment variables
- System MUST restrict database access to internal Docker network by default
- System MUST document secure production deployment practices

**FR-009: Migration from External Supabase**
- System MUST support importing data from external Supabase instances
- System MUST provide migration scripts for knowledge_base and learned_constraints
- System MUST preserve vector embeddings during migration
- System MUST validate data integrity after migration

**FR-010: Development and Production Profiles**
- System MUST support development docker-compose profile with Studio enabled
- System MUST support production docker-compose profile with Studio disabled
- System MUST allow resource limits configuration per environment
- System MUST maintain feature parity across profiles

### Key Entities

**LocalSupabaseDeployment**: Docker Compose configuration defining all services required for self-hosted Supabase including database, REST API, Studio dashboard, and optional services (Realtime, Storage). Configured via environment variables for secrets and network settings.

**DatabaseSchema**: Automated initialization scripts that create pgvector extension, knowledge_base table, learned_constraints table, vector indexes, and SQL functions for similarity search. Executes on first container startup.

**DataVolume**: Persistent Docker volume storing PostgreSQL data files. Survives container restarts and recreations. Can be backed up and restored for disaster recovery.

**EnvironmentConfiguration**: Set of required and optional environment variables including database credentials, JWT secrets, API keys, and feature flags. Validated before service startup.

**ServiceHealthCheck**: Docker health check configuration that periodically verifies service availability. Reports status to Docker container health system. Used for orchestration decisions (restart, stop).

## Success Criteria *(mandatory)*

### Measurable Outcomes

**SC-001**: Deployment time under 10 minutes from fresh Ubuntu server to fully operational CortexReview platform with local Supabase

**SC-002**: Container startup time under 60 seconds for all Supabase services after initial deployment

**SC-003**: Zero external dependencies required for core functionality (webhook processing, code review, RAG, RLHF)

**SC-004**: Data persistence verified across container restarts with 100% data integrity (zero data loss)

**SC-005**: Resource usage under 4GB RAM and 2 CPU cores for core services (excluding optional Studio)

**SC-006**: Vector search query latency under 200ms for similarity search on local database

**SC-007**: Schema initialization succeeds on first startup for 100% of fresh deployments without manual intervention

**SC-008**: Backup and restore procedures successfully preserve and recover 100% of embeddings and learned constraints

## Dependencies & Assumptions

### Dependencies

- **Docker Engine**: Version 20.10 or higher for container orchestration
- **Docker Compose**: Version 2.0 or higher for multi-container management
- **Ubuntu Server**: 20.04 LTS or 22.04 LTS (or compatible Linux distribution)
- **System Resources**: Minimum 4GB RAM, 2 CPU cores, 20GB disk space
- **Supabase Docker Images**: Official images from supabase/supabase Docker Hub repository

### Assumptions

- User has root or sudo access on the target server
- Server has network access to Docker Hub for pulling images
- Server firewall allows inbound traffic on ports 3000 (API), 8000 (Studio), and optionally 5432 (DB)
- User has basic familiarity with Docker and docker-compose commands
- Server meets minimum resource requirements (4GB RAM, 2 CPU cores)
- Production deployments will use secure secrets management (not default values)

## Clarifications

### Session 2026-01-01

- Q: Which Supabase services are required vs optional? → A: Core services required (DB, REST API, pgvector); optional services (Studio, Realtime, Storage) can be disabled to save resources
- Q: How are database backups handled? → A: Named Docker volumes persist data; manual pg_dump procedures documented for backup to external storage
- Q: Can this run on non-Ubuntu systems? → A: Yes, any Linux distribution with Docker support; Ubuntu specified as reference but not a hard requirement
- Q: What about migration from external Supabase? → A: Migration scripts provided to export from external and import to local instance
- Q: Is internet access required after initial deployment? → A: No, once images are pulled, the system operates entirely offline for core functionality
- Q: What is the recommended backup frequency and retention policy? → A: Weekly backups with 90-day retention (lower operational overhead than daily)
- Q: How is the pre-flight check triggered? → A: Automated check integrated into container startup; fails fast with clear error messages if validation fails

## Out of Scope

The following are explicitly excluded from this feature (out of scope):
- High availability deployment (single-node only)
- Database replication or clustering
- Automatic backup scheduling automation (manual weekly backups with 90-day retention policy documented)
- SSL/TLS termination (reverse proxy configuration left to user)
- Supabase Edge Functions (not used by CortexReview)
- Supabase Auth (not used by CortexReview)
- Multi-region deployment
- Database sharding or partitioning
- Automated failover or disaster recovery
- Performance tuning and optimization beyond basic configuration
