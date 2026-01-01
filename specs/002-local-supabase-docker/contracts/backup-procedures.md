# Contract: Backup and Restore Procedures

**Version**: 1.0.0
**Status**: Final
**Date**: 2026-01-01

## Overview

This contract defines the backup and restore procedures for the self-hosted Supabase deployment. Backups are manual (scheduled by operator) with a recommended weekly frequency and 90-day retention policy.

---

## Backup Strategy

### Backup Type: PostgreSQL Logical Backup (pg_dump)

**Tool**: `pg_dump` (included in PostgreSQL Docker image)

**Format**: Compressed SQL dump (`.sql.gz`)

**Scope**: Complete database (all tables, indexes, functions)

**Frequency**: Weekly (recommended, operator-controlled)

**Retention**: 90 days (local storage)

---

## Backup Procedure

### Manual Backup

**Script**: `scripts/backup_supabase.sh`

**Usage**:
```bash
./scripts/backup_supabase.sh
```

**Behavior**:
1. Create backup directory if missing
2. Run `pg_dump` via docker exec
3. Compress output with gzip
4. Save to timestamped file
5. Cleanup old backups (>90 days)
6. Log completion and file size

**Output File**: `./backups/supabase_backup_YYYYMMDD_HHMMSS.sql.gz`

**Duration**: 1-5 minutes (depends on data volume)

**Space Requirements**: Approximately 50% of database size (compressed)

---

### Backup File Naming

**Format**: `supabase_backup_<timestamp>.sql.gz`

**Timestamp Format**: `YYYYMMDD_HHMMSS` (24-hour)

**Example**: `supabase_backup_20260101_020000.sql.gz`

**Rationale**: Sortable by filename, human-readable timestamp

---

### Backup Contents

**Included**:
- All tables (knowledge_base, learned_constraints, feedback_audit_log)
- All indexes (IVFFlat, GIN, B-tree)
- All functions (match_knowledge, check_constraints)
- All sequences (serial columns)
- Schema and data

**Excluded**:
- PostgreSQL configuration files
- WAL (Write-Ahead Log) files
- Temporary files
- Role information (uses default postgres role)

**Restorable**: Complete database can be recreated from backup

---

## Restore Procedure

### Manual Restore

**Script**: `scripts/restore_supabase.sh`

**Usage**:
```bash
./scripts/restore_supabase.sh ./backups/supabase_backup_20260101_020000.sql.gz
```

**Behavior**:
1. Verify backup file exists
2. Prompt for confirmation (WARNING: destructive)
3. Stop API and Worker containers (prevent writes)
4. Drop existing database
5. Create fresh database
6. Restore from backup
7. Restart API and Worker containers
8. Verify data integrity

**Duration**: 2-10 minutes (depends on data volume)

**Safety**: Confirmation prompt prevents accidental data loss

---

### Point-in-Time Recovery (NOT SUPPORTED)

**Limitation**: Logical backups (pg_dump) do not support PITR

**Alternative**: Use volume snapshots for PITR (see Volume Backup section)

---

## Retention Policy

### Backup Cleanup

**Policy**: Delete backups older than 90 days

**Implementation**: Built into backup script

**Command**:
```bash
find ./backups -name "supabase_backup_*.sql.gz" -mtime +90 -delete
```

**Rationale**: 90 days aligns with learned constraint expiration and provides reasonable rollback window

**Customization**: Modify `-mtime +90` to change retention period

---

### Storage Requirements

**Calculation**:
- Database size: 10GB (example)
- Compressed backup: 5GB (50% compression)
- Weekly backups: 4 per month × 3 months = 12 backups
- Total storage: 5GB × 12 = 60GB

**Recommendation**: Provision 100GB for backup directory

---

## Volume Backup (Alternative)

### Volume Snapshot Backup

**Use Case**: Complete server backup including WAL files

**Procedure**:
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

**Duration**: 5-20 minutes (depends on volume size)

**Advantage**: Captures complete database state (WAL files)

**Disadvantage**: Requires container downtime

---

### Volume Restore

**Procedure**:
```bash
# Stop container
docker compose stop supabase-db

# Delete volume (WARNING: destroys existing data)
docker volume rm cortexreview-supabase-db-data

# Recreate volume
docker volume create cortexreview-supabase-db-data

# Restore from backup
docker run --rm \
  -v cortexreview-supabase-db-data:/data \
  -v ./backups:/backup \
  alpine tar xzf /backup/supabase-volume-TIMESTAMP.tar.gz -C /data

# Restart container
docker compose start supabase-db
```

**Duration**: 5-20 minutes (depends on volume size)

---

## Scheduled Backup (Optional)

### Cron Job Configuration

**File**: `/etc/cron.d/cortexreview-backup`

**Schedule**: Weekly (Sunday 2 AM)

```cron
# Weekly backup every Sunday at 2 AM
0 2 * * 0 root /path/to/scripts/backup_supabase.sh >> /var/log/supabase_backup.log 2>&1
```

**Activation**:
```bash
# Copy cron file
sudo cp scripts/cron/cortexreview-backup /etc/cron.d/

# Set permissions
sudo chmod 644 /etc/cron.d/cortexreview-backup

# Verify cron job
sudo crontab -l
```

**Logging**: `/var/log/supabase_backup.log`

---

## Disaster Recovery

### Recovery Time Objective (RTO)

**Target**: < 30 minutes from disaster to restored service

**Breakdown**:
- Detection: 5 minutes
- Decision to restore: 5 minutes
- Restore procedure: 15 minutes
- Verification: 5 minutes

**Achievable**: Yes, with weekly backups and documented procedures

---

### Recovery Point Objective (RPO)

**Target**: Maximum 7 days data loss

**Calculation**:
- Weekly backup frequency
- Worst case: Disaster occurs just before next backup
- Maximum lost data: 6 days 23 hours

**Achievable**: Yes, with weekly backups

**Improvement**: Increase to daily backups for RPO of 1 day

---

## Validation

### Backup Validation

**Procedure**: Test restore to staging database

**Frequency**: Monthly (recommended)

**Steps**:
1. Create staging Supabase instance
2. Restore most recent backup
3. Run validation queries
4. Verify data integrity
5. Document results

**Validation Queries**:
```sql
-- Check row counts
SELECT
  'knowledge_base' as table_name,
  COUNT(*) as row_count
FROM knowledge_base
UNION ALL
SELECT
  'learned_constraints',
  COUNT(*)
FROM learned_constraints
UNION ALL
SELECT
  'feedback_audit_log',
  COUNT(*)
FROM feedback_audit_log;

-- Test vector search
SELECT * FROM match_knowledge(
  '[0.1, 0.2]'::vector || array_fill(0.0, ARRAY[1534]),
  0.75,
  3
);

-- Verify indexes
SELECT indexname FROM pg_indexes
WHERE schemaname = 'public';
```

---

## Security Considerations

### Backup File Permissions

**Default**: 0600 (owner read/write only)

**Enforcement**:
```bash
chmod 600 ./backups/supabase_backup_*.sql.gz
```

**Rationale**: Backups contain sensitive data (embeddings, user feedback)

---

### Backup Encryption (Optional)

**Tool**: `gpg` for symmetric encryption

**Encrypted Backup**:
```bash
# Encrypt after backup
pg_dump ... | gzip | gpg --symmetric --cipher-algo AES256 > backup.sql.gz.gpg

# Decrypt before restore
gpg --decrypt backup.sql.gz.gpg | gunzip | psql ...
```

**Recommendation**: Use encryption if backups stored off-site

---

## Monitoring

### Backup Success Metrics

**Metrics to Track**:
- Backup completion status (success/failure)
- Backup file size
- Backup duration
- Disk space usage (backups directory)

**Prometheus Integration** (optional):
```python
# Example metric
backup_duration_seconds = Histogram(
    'supabase_backup_duration_seconds',
    'Duration of Supabase backup operation'
)

backup_size_bytes = Gauge(
    'supabase_backup_size_bytes',
    'Size of latest Supabase backup file'
)
```

**Alerting**:
- Alert on backup failure
- Alert on low disk space (< 20GB free)
- Alert on missing backup (> 8 days since last)

---

## Troubleshooting

### Common Issues

**Issue**: Permission denied reading backup file

**Resolution**:
```bash
chmod 600 ./backups/supabase_backup_*.sql.gz
```

---

**Issue**: Out of disk space during backup

**Resolution**:
1. Check disk usage: `df -h`
2. Clean old backups: `find ./backups -mtime +90 -delete`
3. Expand disk partition if needed

---

**Issue**: Restore fails with constraint violation

**Resolution**:
1. Drop existing database: `DROP DATABASE supabase;`
2. Create fresh database: `CREATE DATABASE supabase;`
3. Retry restore

---

**Issue**: Container exits during backup

**Resolution**:
1. Stop backup: `Ctrl+C`
2. Check container logs: `docker logs cortexreview-supabase-db`
3. Restart container: `docker compose restart supabase-db`
4. Retry backup

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-01-01 | Initial specification |

---

## Related Documents

- [data-model.md](../data-model.md): Complete schema definition
- [migration-procedures.md](migration-procedures.md): External Supabase migration
- [research.md](../research.md): Technical research findings
