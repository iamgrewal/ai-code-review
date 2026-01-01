# Contract: Migration from External Supabase

**Version**: 1.0.0
**Status**: Final
**Date**: 2026-01-01

## Overview

This contract defines the procedures for migrating data from an external Supabase Cloud instance to the self-hosted local Supabase deployment. The migration preserves all vector embeddings and ensures data integrity.

---

## Migration Strategy

### Approach: Export/Import with pg_dump

**Tool**: `pg_dump` (external) + `psql` (local)

**Method**: Logical backup and restore

**Data Types Migrated**:
- Relational tables (knowledge_base, learned_constraints, feedback_audit_log)
- Vector embeddings (binary data preserved)
- Indexes and constraints (recreated on import)
- Functions (match_knowledge, check_constraints)

**Data Types NOT Migrated**:
- Supabase Auth users (not used by CortexReview)
- Supabase Storage files (not used by CortexReview)
- Edge Functions (not used by CortexReview)

---

## Pre-Migration Checklist

### Source System (External Supabase)

**Requirements**:
- [ ] Access to external Supabase database URL
- [ ] Database password or service role key
- [ ] Read permissions on target tables
- [ ] Network connectivity to external Supabase

**Configuration**:
```bash
export EXTERNAL_SUPABASE_URL="xyz.supabase.co"
export EXTERNAL_SUPABASE_PASSWORD="your-service-role-key"
export EXPORT_DIR="./migration_export"
```

---

### Target System (Local Supabase)

**Requirements**:
- [ ] Local Supabase containers running
- [ ] Database initialized (schema created)
- [ ] Sufficient disk space for imported data
- [ ] No existing data (or data is acceptable to lose)

**Verification**:
```bash
# Check containers running
docker ps | grep supabase

# Check database accessible
docker exec cortexreview-supabase-db psql -U postgres -d supabase -c "SELECT 1;"
```

---

## Migration Procedure

### Step 1: Export from External Supabase

**Script**: `scripts/export_from_external.sh`

**Usage**:
```bash
./scripts/export_from_external.sh
```

**Behavior**:
1. Create export directory
2. Export knowledge_base table
3. Export learned_constraints table
4. Export feedback_audit_log table
5. Generate export manifest

**Output Files**:
- `migration_export/knowledge_base.sql`
- `migration_export/learned_constraints.sql`
- `migration_export/feedback_audit_log.sql`
- `migration_export/manifest.json`

**Duration**: 5-30 minutes (depends on data volume)

**Manifest Format**:
```json
{
  "exported_at": "2026-01-01T02:00:00Z",
  "external_url": "xyz.supabase.co",
  "tables": {
    "knowledge_base": 150000,
    "learned_constraints": 250,
    "feedback_audit_log": 5000
  },
  "total_rows": 152750
}
```

---

### Step 2: Import to Local Supabase

**Script**: `scripts/import_to_local.sh`

**Usage**:
```bash
./scripts/import_to_local.sh
```

**Behavior**:
1. Verify local Supabase running
2. Stop API and Worker containers (prevent writes)
3. Import tables in dependency order
4. Re-create indexes
5. Re-create functions
6. Verify data integrity
7. Restart API and Worker containers

**Duration**: 10-60 minutes (depends on data volume)

---

### Step 3: Post-Migration Validation

**Validation Queries**:

```sql
-- Check row counts match manifest
SELECT 'knowledge_base' as table_name, COUNT(*) as row_count FROM knowledge_base
UNION ALL
SELECT 'learned_constraints', COUNT(*) FROM learned_constraints
UNION ALL
SELECT 'feedback_audit_log', COUNT(*) FROM feedback_audit_log;

-- Verify vector dimensions
SELECT dimension FROM vector_dims('knowledge_base', 'embedding');

-- Test vector search
SELECT * FROM match_knowledge(
  '[0.1, 0.2]'::vector || array_fill(0.0, ARRAY[1534]),
  0.75,
  3
);

-- Verify indexes built
SELECT indexname FROM pg_indexes WHERE schemaname = 'public';

-- Check constraint expiration
SELECT COUNT(*) as active_constraints
FROM learned_constraints
WHERE expires_at > now();
```

**Success Criteria**:
- All row counts match manifest
- Vector dimensions correct (1536)
- match_knowledge() function executes
- Indexes present (IVFFlat, GIN, B-tree)
- Active constraints counted correctly

---

## Data Integrity Guarantees

### Vector Embedding Preservation

**Method**: PostgreSQL binary copy format

**Guarantee**: Float values preserved exactly (no precision loss)

**Verification**:
```sql
-- Before migration (external)
SELECT md5(convert_to(embedding::text, 'UTF-8')) as hash
FROM knowledge_base
LIMIT 10;

-- After migration (local)
SELECT md5(convert_to(embedding::text, 'UTF-8')) as hash
FROM knowledge_base
LIMIT 10;

-- Hashes should match
```

---

### Transaction Safety

**Export**: Each table exported in single transaction

**Import**: Each table imported in single transaction

**Rollback**: If import fails, no partial data committed

**Recovery**: Re-run import script (will skip existing data)

---

## Rollback Plan

### Scenario: Migration Fails or Data Corrupt

**Rollback Procedure**:

1. **Stop using local Supabase**
   ```bash
   docker compose stop api worker
   ```

2. **Reconnect to external Supabase**
   ```bash
   # Update .env
   SUPABASE_URL=https://xyz.supabase.co
   SUPABASE_SERVICE_KEY=original-key
   ```

3. **Restart services**
   ```bash
   docker compose up -d api worker
   ```

4. **Investigate migration failure**
   - Check import logs
   - Verify export files not corrupted
   - Test import on staging instance

5. **Retry migration** after fixing issue

---

### Scenario: External Supabase Still Available

**Cutover Strategy**:
1. Keep external Supabase running
2. Migrate to local Supabase
3. Validate local instance
4. Switch services to local (update .env)
5. Monitor for 30 days
6. Decommission external after validation period

---

## Performance Considerations

### Export Performance

**External Factors**:
- Network latency to Supabase Cloud
- Supabase query rate limits
- Table size and row count

**Optimization**:
- Export during off-peak hours
- Use `--jobs` flag for parallel export (pg_dump)
- Compress output during export

**Estimated Duration**:
- < 100K rows: 5 minutes
- 100K - 1M rows: 15 minutes
- 1M - 10M rows: 60 minutes

---

### Import Performance

**Local Factors**:
- Disk I/O speed
- CPU cores (index building)
- Available memory

**Optimization**:
- Increase maintenance_work_mem during import
- Disable autovacuum during import
- Rebuild indexes after data loaded

**Estimated Duration**:
- < 100K rows: 10 minutes
- 100K - 1M rows: 30 minutes
- 1M - 10M rows: 2 hours

---

## Troubleshooting

### Common Issues

**Issue**: Connection refused to external Supabase

**Resolution**:
```bash
# Verify credentials
export PGPASSWORD="${EXTERNAL_SUPABASE_PASSWORD}"
psql -h "${EXTERNAL_SUPABASE_URL}" -U postgres -d postgres -c "SELECT 1;"

# Check firewall
telnet "${EXTERNAL_SUPABASE_URL}" 5432
```

---

**Issue**: Permission denied on table access

**Resolution**:
- Use service role key (not anon key)
- Verify service role has SELECT permissions
- Contact Supabase support if permissions insufficient

---

**Issue**: Out of memory during import

**Resolution**:
```bash
# Increase Docker memory limit
docker update --memory 8g cortexreview-supabase-db

# Or import in batches (edit import script)
```

---

**Issue**: Vector dimension mismatch

**Resolution**:
```sql
-- Check dimensions on both sides
-- External
SELECT dimension FROM vector_dims('knowledge_base', 'embedding');

-- Local
SELECT dimension FROM vector_dims('knowledge_base', 'embedding');

-- Must both return 1536
```

---

**Issue**: Index build fails

**Resolution**:
```sql
-- Drop failing index
DROP INDEX IF EXISTS idx_kb_vector;

-- Rebuild with higher lists parameter
CREATE INDEX idx_kb_vector
  ON public.knowledge_base
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 200);
```

---

## Security Considerations

### Credentials Handling

**External Supabase**:
- Store service role key in `.env` file
- Never commit `.env` to version control
- Use environment variables, not command-line args

**Local Supabase**:
- Use temporary credentials during migration
- Change passwords after migration
- Restrict network access during migration

---

### Data in Transit

**External Supabase**:
- Requires SSL/TLS connection
- Verify certificate chain
- Use `sslmode=require` in connection string

**Local Storage**:
- Export files contain sensitive data
- Encrypt export files if stored off-site
- Delete export files after successful migration

---

### Data at Rest

**Local Supabase**:
- Database files stored in Docker volume
- Volume encrypted at rest (host-level encryption)
- Backup files encrypted (see backup-procedures.md)

---

## Post-Migration Tasks

### Application Configuration

**Update `.env` file**:
```bash
# Remove external Supabase credentials
# SUPABASE_URL=https://xyz.supabase.co
# SUPABASE_SERVICE_KEY=external-key

# Use local Supabase (default via docker-compose)
# These variables already point to localhost
SUPABASE_DB_URL=postgresql://postgres:${POSTGRES_PASSWORD}@supabase-db:5432/${POSTGRES_DB:-supabase}
```

**Restart services**:
```bash
docker compose restart api worker
```

---

### Monitoring

**Verify operations**:
- API endpoints responding
- Worker processing tasks
- Vector search working
- RAG context retrieval functional
- RLHF constraints applied

**Check logs**:
```bash
docker logs cortexreview-api --tail 100
docker logs cortexreview-worker --tail 100
docker logs cortexreview-supabase-db --tail 100
```

---

### External Supabase Decommission

**Timeline**: 30 days after successful migration

**Steps**:
1. Verify all operations working on local instance
2. Check costs: pause external Supabase project
3. Monitor for 30 days
4. Export final backup from external
5. Delete external Supabase project

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
- [quickstart.md](../quickstart.md): Deployment guide
