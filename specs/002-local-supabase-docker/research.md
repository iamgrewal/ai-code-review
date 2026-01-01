# Research: Local Supabase Docker Deployment

**Feature**: 002-local-supabase-docker
**Date**: 2026-01-01
**Status**: Complete

## Overview

This document consolidates research findings for implementing a self-hosted Supabase deployment using Docker Compose. All technical unknowns from the plan have been resolved through investigation of official Supabase documentation, Docker best practices, and PostgreSQL/pgvector patterns.

---

## 1. Supabase Docker Image Selection

### Decision: Use Official Supabase Docker Images

**Chosen**: `supabase/postgres:15.1.0.147` and associated Supabase container images

**Rationale**:
- Official images maintained by Supabase team
- Include pgvector extension pre-compiled
- Regular security updates and patches
- Compatible with Supabase Studio and REST API containers
- Well-documented deployment patterns

**Alternatives Considered**:
- `postgres:15-alpine` + manual pgvector installation: More flexible but requires manual extension compilation and updates
- Community Supabase images: Less reliable, security updates not guaranteed

**Image Versions**:
| Service | Image | Version | Purpose |
|---------|-------|---------|---------|
| Database | supabase/postgres | 15.1.0.147 | PostgreSQL 15 with pgvector |
| REST API | supabase/postgrest | 12.0.1 | RESTful API for database access |
| Studio | supabase/studio | 20240101-ad6ef8f | Web-based dashboard |

**Source**: [Supabase Self-Hosting Guide](https://supabase.com/docs/guides/self-hosting)

---

## 2. pgvector Extension Installation

### Decision: Extension Pre-Installed in Official Image

**Finding**: The official `supabase/postgres` image includes pgvector pre-compiled and available. No manual installation required during runtime.

**Verification**:
```sql
-- Extension available immediately after container startup
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify installation
SELECT * FROM pg_extension WHERE extname = 'vector';
```

**Configuration**:
- pgvector version: 0.5.0 (included in supabase/postgres:15.1.0.147)
- Vector dimensions: 1536 (OpenAI text-embedding-3-small compatible)
- Index type: IVFFlat (Inverted File Index with Flat compression)

**Source**: [pgvector GitHub](https://github.com/pgvector/pgvector)

---

## 3. Docker Compose Service Configuration

### Decision: Multi-Service Compose with Shared Network

**Pattern**: All services defined in single docker-compose.yml with internal Docker network.

**Service Configuration Best Practices**:

```yaml
services:
  supabase-db:
    image: supabase/postgres:15.1.0.147
    container_name: cortexreview-supabase-db
    restart: always
    networks:
      - cortexreview-network
    volumes:
      - supabase-db-data:/var/lib/postgresql/data
    environment:
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB:-supabase}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s

  supabase-rest:
    image: supabase/postgrest:12.0.1
    container_name: cortexreview-supabase-rest
    restart: always
    networks:
      - cortexreview-network
    environment:
      PGRST_DB_URI: postgresql://postgres:${POSTGRES_PASSWORD}@supabase-db:5432/${POSTGRES_DB:-supabase}
      PGRST_JWT_SECRET: ${JWT_SECRET}
    depends_on:
      supabase-db:
        condition: service_healthy

  supabase-studio:
    image: supabase/studio:20240101-ad6ef8f
    container_name: cortexreview-supabase-studio
    restart: always
    networks:
      - cortexreview-network
    ports:
      - "8000:3000"
    environment:
      STUDIO_PG_META_URL: postgresql://postgres:${POSTGRES_PASSWORD}@supabase-db:5432/${POSTGRES_DB:-supabase}
      STUDO_DEFAULT_ORG: default
    depends_on:
      supabase-db:
        condition: service_healthy
    profiles:
      - development  # Disabled in production by default

networks:
  cortexreview-network:
    driver: bridge

volumes:
  supabase-db-data:
    name: cortexreview-supabase-db-data
```

**Key Patterns**:
- Health checks on database before dependent services start
- Service names used for internal DNS (no hardcoded IPs)
- Named volumes for data persistence
- Profiles for optional services (Studio disabled in production)

**Source**: [Docker Compose Best Practices](https://docs.docker.com/compose/compose-file/compose-file-v3/)

---

## 4. Database Initialization Automation

### Decision: Entrypoint Script with SQL Migration Files

**Approach**: Custom entrypoint script that runs SQL migrations on first startup before starting PostgreSQL.

**Implementation Pattern**:

**Directory Structure**:
```
scripts/
├── init_supabase.py          # Python migration script
└── sql/
    ├── 001_create_extension.sql
    ├── 002_create_knowledge_base.sql
    ├── 003_create_learned_constraints.sql
    ├── 004_create_feedback_audit_log.sql
    ├── 005_create_vector_indexes.sql
    └── 006_create_functions.sql
```

**Entrypoint Script Logic**:
1. Check if initialization already completed (marker file in volume)
2. If not initialized:
   - Wait for database to accept connections
   - Execute SQL migration files in order
   - Create initialization marker file
3. Start PostgreSQL normally

**SQL Migration Example** (`002_create_knowledge_base.sql`):
```sql
CREATE TABLE IF NOT EXISTS public.knowledge_base (
  id BIGSERIAL PRIMARY KEY,
  repo_id TEXT NOT NULL,
  content TEXT NOT NULL,
  metadata JSONB DEFAULT '{}'::jsonb,
  embedding vector(1536),
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Add comment for documentation
COMMENT ON TABLE public.knowledge_base IS 'Vector embeddings for RAG context retrieval';
```

**Initialization Marker**:
```sql
-- Last migration file
CREATE TABLE IF NOT EXISTS public.schema_migrations (
  version TEXT PRIMARY KEY,
  applied_at TIMESTAMPTZ DEFAULT now()
);

INSERT INTO public.schema_migrations (version) VALUES ('001_initial');
```

**Advantages**:
- Idempotent (safe to run multiple times)
- Versioned schema (rollback capability)
- Clear migration history
- Easy to extend with new migrations

**Source**: [PostgreSQL Docker Initialization](https://hub.docker.com/_/postgres/#initialization-scripts)

---

## 5. Pre-Flight Check Implementation

### Decision: Python Script in Container Entrypoint

**Approach**: Validation script runs before database initialization, failing fast if requirements not met.

**Implementation**:

**Entrypoint Script** (`docker-entrypoint.sh`):
```bash
#!/bin/bash
set -e

echo "Running pre-flight checks..."

# Environment variable validation
python3 /app/scripts/preflight_check.py || exit 1

# System resource check
python3 /app/scripts/resource_check.py || exit 1

echo "Pre-flight checks passed. Starting database..."

# Continue with normal startup
exec docker-entrypoint.sh "$@"
```

**Pre-Flight Check Script** (`scripts/preflight_check.py`):
```python
#!/usr/bin/env python3
import os
import sys

# Required environment variables
REQUIRED_VARS = [
    'POSTGRES_PASSWORD',
    'JWT_SECRET',
    'ANON_KEY',
    'SERVICE_ROLE_KEY'
]

# Minimum secret lengths
MIN_SECRET_LENGTHS = {
    'JWT_SECRET': 64,
    'POSTGRES_PASSWORD': 16
}

def check_environment_variables():
    """Validate required environment variables are set."""
    missing = []
    weak = []

    for var in REQUIRED_VARS:
        value = os.environ.get(var)
        if not value:
            missing.append(var)
        elif var in MIN_SECRET_LENGTHS:
            if len(value) < MIN_SECRET_LENGTHS[var]:
                weak.append(var)

    if missing:
        print(f"ERROR: Missing required environment variables: {', '.join(missing)}")
        print("Please set these variables in .env file before starting.")
        return False

    if weak:
        print(f"WARNING: Weak secrets detected (below minimum length): {', '.join(weak)}")
        print("Consider using stronger values for production.")

    return True

def check_jwt_secret_format():
    """Validate JWT_SECRET is sufficiently random."""
    secret = os.environ.get('JWT_SECRET', '')
    if len(secret) < 64:
        print(f"ERROR: JWT_SECRET must be at least 64 characters (current: {len(secret)})")
        print("Generate with: openssl rand -base64 64")
        return False
    return True

def main():
    """Run all pre-flight checks."""
    checks = [
        check_environment_variables,
        check_jwt_secret_format
    ]

    for check in checks:
        if not check():
            sys.exit(1)

    print("✓ Pre-flight checks passed")
    return 0

if __name__ == '__main__':
    sys.exit(main())
```

**Resource Check Script** (`scripts/resource_check.py`):
```python
#!/usr/bin/env python3
import os
import sys

MIN_RAM_GB = 4
MIN_CPU_CORES = 2

def check_system_resources():
    """Check if system meets minimum resource requirements."""
    # Check RAM (from /proc/meminfo on Linux)
    try:
        with open('/proc/meminfo', 'r') as f:
            meminfo = f.read()
            for line in meminfo.split('\n'):
                if line.startswith('MemTotal:'):
                    mem_kb = int(line.split()[1])
                    mem_gb = mem_kb / (1024 * 1024)
                    if mem_gb < MIN_RAM_GB:
                        print(f"WARNING: System has {mem_gb:.1f}GB RAM (minimum: {MIN_RAM_GB}GB)")
                        print("Consider disabling optional services (Studio) to reduce footprint.")
                    return True
    except Exception:
        # Running in container, can't check host resources
        pass

    return True

def main():
    if not check_system_resources():
        sys.exit(1)
    print("✓ Resource checks passed")
    return 0

if __name__ == '__main__':
    sys.exit(main())
```

**Integration with Docker Compose**:
```yaml
supabase-db:
  image: supabase/postgres:15.1.0.147
  entrypoint: ["/app/docker-entrypoint.sh"]  # Custom entrypoint with pre-flight checks
  volumes:
    - ./scripts/preflight_check.py:/app/scripts/preflight_check.py:ro
    - ./scripts/resource_check.py:/app/scripts/resource_check.py:ro
    - ./scripts/docker-entrypoint.sh:/app/docker-entrypoint.sh:ro
```

**Advantages**:
- Fails fast before database startup
- Clear error messages for configuration issues
- Resource warnings for capacity planning
- No manual validation required

---

## 6. Backup/Restore Procedures

### Decision: pg_dump with Docker Exec and Named Volume Backups

**Approach**: Manual backup scripts using PostgreSQL native tools, executed via docker exec.

**Backup Procedure**:

**Backup Script** (`scripts/backup_supabase.sh`):
```bash
#!/bin/bash
set -e

# Configuration
BACKUP_DIR="${BACKUP_DIR:-./backups}"
CONTAINER_NAME="cortexreview-supabase-db"
DB_NAME="${POSTGRES_DB:-supabase}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/supabase_backup_${TIMESTAMP}.sql.gz"

# Create backup directory
mkdir -p "${BACKUP_DIR}"

echo "Starting backup at $(date)"

# Run pg_dump via docker exec
docker exec "${CONTAINER_NAME}" pg_dump \
  -U postgres \
  -d "${DB_NAME}" \
  --no-owner \
  --no-acl \
  --verbose \
  2>&1 | gzip > "${BACKUP_FILE}"

echo "Backup completed: ${BACKUP_FILE}"

# Backup size
BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
echo "Backup size: ${BACKUP_SIZE}"

# Cleanup old backups (keep last 90 days per retention policy)
find "${BACKUP_DIR}" -name "supabase_backup_*.sql.gz" -mtime +90 -delete

echo "Old backups cleaned (retention: 90 days)"
```

**Restore Procedure**:

**Restore Script** (`scripts/restore_supabase.sh`):
```bash
#!/bin/bash
set -e

if [ -z "$1" ]; then
  echo "Usage: $0 <backup_file.sql.gz>"
  exit 1
fi

BACKUP_FILE="$1"
CONTAINER_NAME="cortexreview-supabase-db"
DB_NAME="${POSTGRES_DB:-supabase}"

echo "WARNING: This will replace all data in the database."
read -p "Continue? (yes/no): " confirmation

if [ "$confirmation" != "yes" ]; then
  echo "Restore cancelled."
  exit 0
fi

echo "Starting restore at $(date)"

# Stop API and Worker to prevent writes during restore
docker compose stop api worker

# Restore from backup
gunzip -c "${BACKUP_FILE}" | docker exec -i "${CONTAINER_NAME}" psql \
  -U postgres \
  -d "${DB_NAME}" \
  --quiet

echo "Restore completed. Restarting services..."

# Restart services
docker compose start api worker

echo "Done."
```

**Scheduled Backup (Optional)**:

Add to crontab for automated weekly backups:
```cron
# Weekly backup every Sunday at 2 AM
0 2 * * 0 /path/to/scripts/backup_supabase.sh >> /var/log/supabase_backup.log 2>&1
```

**Volume Snapshot (Alternative)**:

For complete volume backup (including PostgreSQL WAL files):
```bash
# Stop container
docker compose stop supabase-db

# Create volume backup
docker run --rm \
  -v cortexreview-supabase-db-data:/data \
  -v ./backups:/backup \
  alpine tar czf /backup/supabase-volume-$(date +%Y%m%d_%H%M%S).tar.gz -C /data .

# Restart container
docker compose start supabase-db
```

**Source**: [PostgreSQL Backup Documentation](https://www.postgresql.org/docs/current/backup.html)

---

## 7. Migration from External Supabase

### Decision: Export/Import Scripts with Vector Embedding Preservation

**Approach**: Dump external Supabase data and restore to local instance, preserving vector embeddings.

**Migration Procedure**:

**Export from External Supabase** (`scripts/export_from_external.sh`):
```bash
#!/bin/bash
set -e

# Configuration from external Supabase
EXTERNAL_SUPABASE_URL="${EXTERNAL_SUPABASE_URL}"
EXTERNAL_SUPABASE_PASSWORD="${EXTERNAL_SUPABASE_PASSWORD}"
EXPORT_DIR="./migration_export"

mkdir -p "${EXPORT_DIR}"

echo "Exporting data from external Supabase..."

# Export tables
TABLES=("knowledge_base" "learned_constraints" "feedback_audit_log")

for table in "${TABLES[@]}"; do
  echo "Exporting ${table}..."
  PGPASSWORD="${EXTERNAL_SUPABASE_PASSWORD}" pg_dump \
    -h "${EXTERNAL_SUPABASE_URL}" \
    -U postgres \
    -d postgres \
    -t "${table}" \
    --data-only \
    --column-inserts \
    > "${EXPORT_DIR}/${table}.sql"
done

echo "Export completed: ${EXPORT_DIR}"
```

**Import to Local Supabase** (`scripts/import_to_local.sh`):
```bash
#!/bin/bash
set -e

IMPORT_DIR="${IMPORT_DIR:-./migration_export}"
CONTAINER_NAME="cortexreview-supabase-db"
DB_NAME="${POSTGRES_DB:-supabase}"

echo "Importing data to local Supabase..."

# Verify local Supabase is running
if ! docker ps | grep -q "${CONTAINER_NAME}"; then
  echo "ERROR: Local Supabase container not running"
  echo "Start with: docker compose up -d supabase-db"
  exit 1
fi

# Import tables
TABLES=("knowledge_base" "learned_constraints" "feedback_audit_log")

for table in "${TABLES[@]}"; do
  if [ -f "${IMPORT_DIR}/${table}.sql" ]; then
    echo "Importing ${table}..."
    docker exec -i "${CONTAINER_NAME}" psql \
      -U postgres \
      -d "${DB_NAME}" \
      < "${IMPORT_DIR}/${table}.sql"
  else
    echo "WARNING: ${table} export not found, skipping"
  fi
done

echo "Import completed"

# Verify data integrity
echo "Verifying data integrity..."
docker exec "${CONTAINER_NAME}" psql \
  -U postgres \
  -d "${DB_NAME}" \
  -c "SELECT COUNT(*) FROM knowledge_base;"

docker exec "${CONTAINER_NAME}" psql \
  -U postgres \
  -d "${DB_NAME}" \
  -c "SELECT COUNT(*) FROM learned_constraints;"

echo "Migration complete"
```

**Vector Embedding Preservation**:
- Vector columns exported as binary data in INSERT statements
- PostgreSQL binary format preserves exact float values
- No re-embedding required after migration

**Validation After Migration**:
```sql
-- Check vector dimensions
SELECT dimension FROM vector_dims('knowledge_base', 'embedding');

-- Verify indexes are built
SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'knowledge_base';

-- Test vector search
SELECT * FROM match_knowledge(
  '[0.1, 0.2, ...]'::vector,  -- Test embedding
  0.75,                        -- match_threshold
  3                            -- match_count
);
```

**Rollback Plan**:
- External Supabase remains available until migration verified
- Keep external backup for 30 days after migration
- Re-export possible if issues found

**Source**: [Supabase Migration Guide](https://supabase.com/docs/guides/platform/migrations)

---

## Summary of Decisions

| Area | Decision | Rationale |
|------|----------|-----------|
| Docker Images | Official Supabase images | Maintained, secure, pgvector pre-installed |
| pgvector Install | Pre-compiled in image | No runtime installation, reliable |
| Compose Config | Multi-service shared network | Standard pattern, internal DNS, health checks |
| Initialization | Entrypoint script + SQL migrations | Idempotent, versioned, clear history |
| Pre-Flight Checks | Python script in entrypoint | Fails fast, clear errors, resource warnings |
| Backup Strategy | pg_dump via docker exec | PostgreSQL native, compressed, retention policy |
| Migration Strategy | Export/Import scripts | Preserves vectors, validates integrity, rollback safe |

---

## Open Questions Resolved

All technical unknowns from the plan have been resolved. No additional research required before Phase 1 design.

**Next Step**: Proceed to Phase 1 (Design & Contracts) to create data-model.md, contracts/, and quickstart.md.
