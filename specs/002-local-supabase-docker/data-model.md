# Data Model: Local Supabase Deployment

**Feature**: 002-local-supabase-docker
**Date**: 2026-01-01
**Status**: Final

## Overview

This document defines the complete database schema for the self-hosted Supabase deployment. The schema supports three core functions: Context Engine (RAG), Learning Loop (RLHF), and Repository Indexing.

All tables use PostgreSQL 15 with the pgvector extension for vector similarity search.

---

## Database Configuration

**Database Name**: `supabase` (configurable via `POSTGRES_DB`)
**Schema**: `public`
**Extension**: `pgvector` (vector type and similarity functions)
**Vector Dimensions**: 1536 (OpenAI text-embedding-3-small compatible)
**Index Type**: IVFFlat (Inverted File Index with Flat compression)

---

## Tables

### 1. knowledge_base

**Purpose**: Store vector embeddings for RAG context retrieval. Contains code patterns from indexed repositories.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | BIGSERIAL | PRIMARY KEY | Auto-incrementing identifier |
| `repo_id` | TEXT | NOT NULL | Repository identifier (e.g., "owner/repo") |
| `content` | TEXT | NOT NULL | Code snippet or pattern content |
| `metadata` | JSONB | DEFAULT '{}' | Additional metadata (file_path, commit_sha, language) |
| `embedding` | vector(1536) | NOT NULL | Vector embedding for similarity search |
| `created_at` | TIMESTAMPTZ | DEFAULT now() | Timestamp of record creation |

**Indexes**:
```sql
-- IVFFlat vector index for similarity search
CREATE INDEX idx_kb_vector
  ON public.knowledge_base
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

-- GIN index on metadata for JSON queries
CREATE INDEX idx_kb_metadata
  ON public.knowledge_base
  USING gin (metadata);

-- B-tree index on repo_id for filtering
CREATE INDEX idx_kb_repo_id
  ON public.knowledge_base(repo_id);
```

**Validation Rules**:
- `content` must not be empty
- `embedding` must have exactly 1536 dimensions
- `repo_id` must follow pattern "owner/repo" or be a valid URL

**Rationale**:
- IVFFlat index provides fast approximate nearest neighbor search
- `lists = 100` provides good trade-off between speed and accuracy for 10M+ rows
- JSONB metadata allows flexible schema evolution
- Created at timestamp enables data retention policies

---

### 2. learned_constraints

**Purpose**: Store negative examples from RLHF feedback. Contains patterns that should be suppressed in future reviews.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | BIGSERIAL | PRIMARY KEY | Auto-incrementing identifier |
| `repo_id` | TEXT | NOT NULL | Repository identifier |
| `violation_reason` | TEXT | | Original review comment that was rejected |
| `code_pattern` | TEXT | NOT NULL | Code pattern that triggered false positive |
| `user_reason` | TEXT | NOT NULL | User's explanation for rejection |
| `embedding` | vector(1536) | NOT NULL | Vector embedding for pattern matching |
| `confidence_score` | FLOAT | DEFAULT 1.0 | Aggregated confidence from multiple feedback |
| `expires_at` | TIMESTAMPTZ | NOT NULL | Expiration timestamp (default: 90 days) |
| `created_at` | TIMESTAMPTZ | DEFAULT now() | Timestamp of constraint creation |

**Indexes**:
```sql
-- IVFFlat vector index for constraint matching
CREATE INDEX idx_lc_vector
  ON public.learned_constraints
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

-- Partial index for active constraints (not expired)
CREATE INDEX idx_lc_active
  ON public.learned_constraints(repo_id, code_pattern)
  WHERE expires_at > now();

-- B-tree index on expiration for cleanup jobs
CREATE INDEX idx_lc_expires_at
  ON public.learned_constraints(expires_at);
```

**Validation Rules**:
- `user_reason` must not be empty
- `confidence_score` must be between 0.0 and 1.0
- `expires_at` must be in the future
- `embedding` must have exactly 1536 dimensions

**Rationale**:
- Partial index on active constraints improves query performance
- Expiration index enables efficient cleanup jobs
- Confidence score allows aggregation of multiple feedback
- 90-day default expiration prevents stale constraints

---

### 3. feedback_audit_log

**Purpose**: Audit trail for all RLHF feedback submissions. Supports compliance and debugging.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | BIGSERIAL | PRIMARY KEY | Auto-incrementing identifier |
| `review_comment_id` | TEXT | NOT NULL | Reference to original review comment |
| `user_id` | TEXT | NOT NULL | User who submitted feedback |
| `action` | TEXT | NOT NULL | Action taken: "accepted", "rejected", "modified" |
| `reason` | TEXT | | User's explanation for action |
| `constraint_id` | BIGINT | FK → learned_constraints.id | Associated constraint (if created) |
| `created_at` | TIMESTAMPTZ | DEFAULT now() | Timestamp of feedback submission |

**Indexes**:
```sql
-- B-tree index on user_id for user history
CREATE INDEX idx_fal_user_id
  ON public.feedback_audit_log(user_id, created_at DESC);

-- B-tree index on constraint_id for constraint provenance
CREATE INDEX idx_fal_constraint_id
  ON public.feedback_audit_log(constraint_id);

-- B-tree index on created_at for retention policies
CREATE INDEX idx_fal_created_at
  ON public.feedback_audit_log(created_at);
```

**Validation Rules**:
- `action` must be one of: "accepted", "rejected", "modified"
- `user_id` must not be empty
- `reason` required if action is "rejected" or "modified"

**Rationale**:
- Audit log is append-only (no updates/deletes)
- Foreign key to constraints provides provenance
- User index enables feedback history queries
- Time-based index supports retention policies

---

### 4. schema_migrations

**Purpose**: Track database schema version and migration history.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `version` | TEXT | PRIMARY KEY | Migration version identifier |
| `applied_at` | TIMESTAMPTZ | DEFAULT now() | Timestamp of migration application |

**Validation Rules**:
- `version` must follow semantic versioning or timestamp format

**Rationale**:
- Prevents duplicate migrations
- Provides rollback capability
- Enables schema version tracking

---

## SQL Functions

### match_knowledge

**Purpose**: Retrieve similar code patterns from knowledge_base for RAG context.

**Signature**:
```sql
CREATE OR REPLACE FUNCTION public.match_knowledge(
  query_embedding vector(1536),
  match_threshold float DEFAULT 0.75,
  match_count int DEFAULT 3
)
RETURNS table (
  id bigint,
  repo_id text,
  content text,
  metadata jsonb,
  similarity float
)
LANGUAGE sql
AS $$
  SELECT
    kb.id,
    kb.repo_id,
    kb.content,
    kb.metadata,
    1 - (kb.embedding <=> query_embedding) as similarity
  FROM public.knowledge_base kb
  WHERE 1 - (kb.embedding <=> query_embedding) > match_threshold
  ORDER BY kb.embedding <=> query_embedding
  LIMIT match_count;
$$;
```

**Parameters**:
- `query_embedding`: Vector embedding of input code diff
- `match_threshold`: Minimum similarity score (0-1, default: 0.75)
- `match_count`: Maximum number of results (default: 3)

**Returns**: Table of matching knowledge entries with similarity scores

**Usage Example**:
```sql
SELECT * FROM match_knowledge(
  '[0.1, 0.2, ...]'::vector,
  0.75,
  5
);
```

---

### check_constraints

**Purpose**: Check if code pattern matches any learned constraints (false positives).

**Signature**:
```sql
CREATE OR REPLACE FUNCTION public.check_constraints(
  query_embedding vector(1536),
  match_threshold float DEFAULT 0.8
)
RETURNS table (
  id bigint,
  repo_id text,
  violation_reason text,
  user_reason text,
  similarity float
)
LANGUAGE sql
AS $$
  SELECT
    lc.id,
    lc.repo_id,
    lc.violation_reason,
    lc.user_reason,
    1 - (lc.embedding <=> query_embedding) as similarity
  FROM public.learned_constraints lc
  WHERE
    1 - (lc.embedding <=> query_embedding) > match_threshold
    AND lc.expires_at > now()
  ORDER BY lc.embedding <=> query_embedding
  LIMIT 3;
$$;
```

**Parameters**:
- `query_embedding`: Vector embedding of input code diff
- `match_threshold`: Minimum similarity score (0-1, default: 0.8)

**Returns**: Table of matching constraints with user reasons

**Usage Example**:
```sql
SELECT * FROM check_constraints(
  '[0.1, 0.2, ...]'::vector,
  0.8
);
```

**Note**: Higher threshold (0.8 vs 0.75) ensures we only suppress very similar patterns.

---

## Entity Relationships

```
┌─────────────────────┐         ┌──────────────────────┐
│  knowledge_base     │         │ learned_constraints  │
│  ────────────────   │         │  ─────────────────   │
│  id (PK)            │         │  id (PK)             │
│  repo_id            │         │  repo_id             │
│  content            │         │  code_pattern        │
│  embedding (vector) │         │  embedding (vector)  │
│  metadata (jsonb)   │         │  confidence_score    │
│  created_at         │         │  expires_at          │
└─────────────────────┘         │  created_at          │
                                  └──────────┬───────────┘
                                             │
                                             │ 1:N
                                             │
                                             ▼
                                  ┌──────────────────────┐
                                  │ feedback_audit_log   │
                                  │  ─────────────────   │
                                  │  id (PK)             │
                                  │  constraint_id (FK)  │
                                  │  user_id             │
                                  │  action              │
                                  │  reason              │
                                  │  created_at          │
                                  └──────────────────────┘
```

**Relationship Rules**:
- `feedback_audit_log.constraint_id` references `learned_constraints.id`
- On constraint deletion, audit log records preserved (no CASCADE)
- One constraint can have multiple feedback records

---

## Data Retention Policies

### Learned Constraints Expiration

**Policy**: Constraints expire after 90 days by default. Renewable by re-submitting feedback.

**Implementation**:
```sql
-- Query to identify expired constraints
SELECT * FROM learned_constraints
WHERE expires_at <= now();

-- Query to renew a constraint
UPDATE learned_constraints
SET expires_at = now() + interval '90 days'
WHERE id = <constraint_id>;
```

**Cleanup Job** (recommended):
```sql
-- Delete expired constraints (run weekly)
DELETE FROM learned_constraints
WHERE expires_at <= now();
```

---

### Feedback Audit Log Retention

**Policy**: Audit records retained indefinitely for compliance. No automatic deletion.

**Rationale**: Audit log is critical for debugging, compliance, and system analysis.

---

### Knowledge Base Retention

**Policy**: Knowledge base entries retained indefinitely. Manual deletion by repo_id supported.

**Implementation**:
```sql
-- Delete all knowledge for a specific repository
DELETE FROM knowledge_base
WHERE repo_id = 'owner/repo';

-- Delete knowledge older than specific date
DELETE FROM knowledge_base
WHERE created_at < '2024-01-01'::timestamptz;
```

---

## Vector Similarity Functions

pgvector provides three distance functions:

| Function | Operation | Use Case |
|----------|-----------|----------|
| `<=>` | Cosine distance | **Default** - Normalized vectors (embeddings) |
| `<->` | L2 distance | Euclidean distance (not used) |
| `<#>` | Negative inner product | Dot product (not used) |

**Why Cosine Distance?**
- OpenAI embeddings are normalized to unit length
- Cosine similarity measures angle between vectors (ignores magnitude)
- Range: 0 (identical) to 2 (opposite)
- Converted to similarity: `1 - cosine_distance` (range: -1 to 1)

---

## Performance Considerations

### IVFFlat Index Tuning

**Parameters**:
- `lists = 100`: Number of inverted lists
- Trade-off: More lists = faster build, slower query

**Guidelines**:
| Row Count | Recommended lists |
|-----------|-------------------|
| < 100K | 100 |
| 100K - 1M | 100 - 200 |
| 1M - 10M | 200 - 400 |
| > 10M | 400 - 1000 |

**Rebuild Required**:
- IVFFlat indexes must be rebuilt after significant data changes (20%+ inserts)
- Rebuild command: `REINDEX INDEX idx_kb_vector;`

---

### Connection Pooling

**Configuration** (environment variable):
```
SUPABASE_DB_CONNECTION_POOL_SIZE=20
```

**Recommendation**: 20 connections across all workers (4 workers × 5 connections each)

---

### Query Optimization

**RAG Query Pattern**:
```sql
-- Efficient: Limit results, use function
SELECT * FROM match_knowledge(
  query_embedding,
  0.75,
  3  -- Dynamic based on diff size
);

-- Inefficient: Direct table scan with complex filter
SELECT * FROM knowledge_base
WHERE embedding <=> query_embedding < 0.25
ORDER BY embedding <=> query_embedding
LIMIT 3;
```

**RLHF Query Pattern**:
```sql
-- Efficient: Use function with partial index
SELECT * FROM check_constraints(
  query_embedding,
  0.8
);

-- Inefficient: Scan all constraints including expired
SELECT * FROM learned_constraints
WHERE embedding <=> query_embedding < 0.2;
```

---

## Security Considerations

### Access Control

**Database User Permissions**:
- `postgres`: Superuser (for initialization only)
- `supabase_auth`: No access (not used)
- `authenticated`: Read/write on application tables
- `anon`: No access (not used)

**Network Isolation**:
- Database port 5432 exposed ONLY on internal Docker network
- No external access without explicit port mapping
- API and Worker containers access via service name `supabase-db`

### Data Isolation

**Repo-Level Isolation**:
- All queries include `repo_id` filter
- No cross-repo vector search
- Constraints scoped to repository

**Embedding Security**:
- No secrets in embeddings (pre-embedding validation)
- Secret scanning before vector generation
- Embeddings stored as binary (not human-readable)

---

## Migration Scripts

**File Structure**:
```
scripts/sql/
├── 001_create_extension.sql         -- Install pgvector
├── 002_create_knowledge_base.sql    -- Create knowledge_base table
├── 003_create_learned_constraints.sql -- Create learned_constraints table
├── 004_create_feedback_audit_log.sql  -- Create feedback_audit_log table
├── 005_create_vector_indexes.sql    -- Create IVFFlat indexes
├── 006_create_functions.sql         -- Create match_knowledge and check_constraints
└── 007_create_migration_table.sql   -- Create schema_migrations table
```

**Execution Order**: Numerical order via entrypoint script

---

## Summary

This data model supports:
- **RAG Context Retrieval**: `knowledge_base` table with `match_knowledge()` function
- **RLHF Learning Loop**: `learned_constraints` table with `check_constraints()` function
- **Audit Compliance**: `feedback_audit_log` table for feedback tracking
- **Repository Indexing**: Automated embedding storage with metadata
- **Data Retention**: 90-day constraint expiration, indefinite audit log

**Next Step**: Create API contracts (contracts/) and quickstart guide.
