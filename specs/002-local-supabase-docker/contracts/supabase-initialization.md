# Contract: Supabase Database Initialization

**Version**: 1.0.0
**Status**: Final
**Date**: 2026-01-01

## Overview

This contract defines the automated database initialization process for the self-hosted Supabase deployment. The initialization runs automatically on first container startup and is idempotent (safe to run multiple times).

---

## Trigger Conditions

**When**: Container `supabase-db` starts for the first time

**Detection**: Absence of `schema_migrations` table or missing version marker

**Execution**: Entrypoint script (`docker-entrypoint.sh`) runs migration files in order

---

## Initialization Sequence

### Phase 1: Extension Installation

**Script**: `001_create_extension.sql`

**Action**: Install pgvector extension

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

**Success Criteria**:
- Extension `vector` appears in `pg_extension` table
- Function `vector_dims()` available
- Vector data type accepts 1536-dimensional arrays

**Failure Handling**:
- Extension pre-installed in official Supabase image
- If installation fails, container exits with error
- Resolution: Use correct Supabase Docker image with pgvector

---

### Phase 2: Table Creation

**Scripts**: `002_create_knowledge_base.sql`, `003_create_learned_constraints.sql`, `004_create_feedback_audit_log.sql`

**Actions**:
1. Create `knowledge_base` table with vector column
2. Create `learned_constraints` table with vector column
3. Create `feedback_audit_log` table with foreign key

**Success Criteria**:
- All tables exist in `public` schema
- Table columns match data-model.md specification
- Foreign key constraints created
- Default values applied

**Validation Query**:
```sql
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
AND table_name IN ('knowledge_base', 'learned_constraints', 'feedback_audit_log')
ORDER BY table_name, ordinal_position;
```

---

### Phase 3: Index Creation

**Script**: `005_create_vector_indexes.sql`

**Actions**:
1. Create IVFFlat index on `knowledge_base.embedding`
2. Create IVFFlat index on `learned_constraints.embedding`
3. Create supporting indexes (metadata, repo_id, expires_at)

**Success Criteria**:
- `idx_kb_vector` index exists (IVFFlat)
- `idx_lc_vector` index exists (IVFFlat)
- `idx_kb_metadata` index exists (GIN)
- `idx_lc_active` index exists (partial)

**Validation Query**:
```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename IN ('knowledge_base', 'learned_constraints');
```

**Performance Targets**:
- Index build time: < 60 seconds for empty tables
- Index build time: < 10 minutes for 1M rows

---

### Phase 4: Function Creation

**Script**: `006_create_functions.sql`

**Actions**:
1. Create `match_knowledge()` function
2. Create `check_constraints()` function

**Success Criteria**:
- Functions exist in `public` schema
- Functions accept vector(1536) parameters
- Functions return TABLE with correct columns
- Functions execute without errors

**Validation Query**:
```sql
SELECT routine_name, routine_type
FROM information_schema.routines
WHERE routine_schema = 'public'
AND routine_name IN ('match_knowledge', 'check_constraints');
```

**Test Execution**:
```sql
-- Test match_knowledge with dummy embedding
SELECT * FROM match_knowledge(
  '[0.1, 0.2]'::vector || array_fill(0.0, ARRAY[1534]),
  0.75,
  3
);

-- Test check_constraints with dummy embedding
SELECT * FROM check_constraints(
  '[0.1, 0.2]'::vector || array_fill(0.0, ARRAY[1534]),
  0.8
);
```

---

### Phase 5: Migration Tracking

**Script**: `007_create_migration_table.sql`

**Action**: Create `schema_migrations` table and insert initial version

```sql
CREATE TABLE IF NOT EXISTS public.schema_migrations (
  version TEXT PRIMARY KEY,
  applied_at TIMESTAMPTZ DEFAULT now()
);

INSERT INTO public.schema_migrations (version) VALUES ('001_initial');
```

**Success Criteria**:
- `schema_migrations` table exists
- Record with version='001_initial' exists
- Subsequent startups detect existing version and skip re-initialization

---

## Error Handling

### Pre-Flight Failures

**Scenario**: Required environment variables missing

**Behavior**: Container exits before PostgreSQL starts

**Error Message**:
```
ERROR: Missing required environment variables: POSTGRES_PASSWORD, JWT_SECRET
Please set these variables in .env file before starting.
```

**Recovery**: Set missing variables and restart container

---

### Migration Failures

**Scenario**: SQL script fails (syntax error, permission error)

**Behavior**: Container stops, initialization not complete

**Error Log**:
```
ERROR: Migration 002_create_knowledge_base.sql failed
DETAIL: syntax error at or near "CREATEE"
```

**Recovery**:
1. Fix SQL script
2. Remove initialization marker: `DELETE FROM schema_migrations WHERE version='001_initial';`
3. Restart container

---

### Partial Initialization

**Scenario**: Container crashes mid-migration

**Behavior**: Database in inconsistent state

**Detection**: `schema_migrations` table missing or version incomplete

**Recovery**:
1. Drop all tables: `DROP SCHEMA public CASCADE; CREATE SCHEMA public;`
2. Restart container (re-runs full initialization)

---

## Idempotency Guarantees

**All initialization steps are idempotent**:

| Step | Idempotency Mechanism |
|------|---------------------|
| Extension Install | `IF NOT EXISTS` clause |
| Table Creation | `IF NOT EXISTS` clause |
| Index Creation | `IF NOT EXISTS` clause |
| Function Creation | `OR REPLACE` clause |
| Migration Record | Primary key prevents duplicate insert |

**Safety**: Re-running initialization on existing database is safe

---

## Timing Expectations

| Phase | Duration (Fresh DB) | Duration (With Data) |
|-------|---------------------|----------------------|
| Extension Install | < 5 seconds | < 5 seconds |
| Table Creation | < 10 seconds | < 10 seconds |
| Index Creation | < 30 seconds | < 10 minutes* |
| Function Creation | < 5 seconds | < 5 seconds |
| Migration Tracking | < 5 seconds | < 5 seconds |
| **Total** | **< 60 seconds** | **~10 minutes*** |

*Depends on existing data volume

---

## Validation Checklist

**Automated Validation** (run by entrypoint script after initialization):

- [ ] pgvector extension installed
- [ ] All tables created
- [ ] All indexes created
- [ ] All functions created
- [ ] Migration record inserted
- [ ] `match_knowledge()` function executes
- [ ] `check_constraints()` function executes

**Manual Validation** (optional, for troubleshooting):

```bash
# Connect to database
docker exec -it cortexreview-supabase-db psql -U postgres -d supabase

# Run validation queries
\dt public.*                    # List tables
\di public.*                    # List indexes
df public.match_knowledge       # Function definition
SELECT * FROM schema_migrations; # Migration version
```

---

## Rollback Procedure

**Scenario**: Need to reset database to fresh state

**Procedure**:

```bash
# Stop containers
docker compose stop supabase-db supabase-rest supabase-studio

# Delete volume (WARNING: destroys all data)
docker volume rm cortexreview-supabase-db-data

# Restart containers (will re-initialize)
docker compose up -d supabase-db supabase-rest supabase-studio
```

**Alternative** (preserve data, reset schema only):

```sql
-- Drop and recreate schema
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;

-- Re-run initialization (remove migration marker first)
DELETE FROM schema_migrations WHERE version='001_initial';
```

---

## Integration Points

**Called By**: Container entrypoint script (`docker-entrypoint.sh`)

**Calls**:
- PostgreSQL server (via pg_isready for health check)
- Migration SQL files (via psql)

**Environment Variables Required**:
- `POSTGRES_DB`: Database name (default: supabase)
- `POSTGRES_PASSWORD`: Database password

**Environment Variables Optional**:
- None (uses PostgreSQL defaults)

---

## Testing

**Unit Test** (mock initialization):
```python
def test_initialization_idempotent():
    """Test that running initialization twice is safe."""
    # Run initialization
    run_initialization()

    # Verify tables created
    assert table_exists("knowledge_base")

    # Run initialization again
    run_initialization()

    # Verify no errors, tables still exist
    assert table_exists("knowledge_base")
```

**Integration Test** (real container):
```bash
# Start fresh container
docker compose up -d supabase-db

# Wait for initialization
sleep 60

# Verify tables exist
docker exec cortexreview-supabase-db psql -U postgres -d supabase -c "\dt public.*"

# Verify functions exist
docker exec cortexreview-supabase-db psql -U postgres -d supabase -c "df public.match_knowledge"

# Cleanup
docker compose down -v
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-01-01 | Initial specification |

---

## Related Documents

- [data-model.md](../data-model.md): Complete schema definition
- [backup-procedures.md](backup-procedures.md): Backup/restore procedures
- [research.md](../research.md): Technical research findings
