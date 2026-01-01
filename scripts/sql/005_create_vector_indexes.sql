-- Migration: 005_create_vector_indexes.sql
-- Purpose: Create IVFFlat vector indexes for similarity search
-- Dependencies: 002_create_knowledge_base.sql, 003_create_learned_constraints.sql
-- Idempotent: Yes (uses IF NOT EXISTS)

-- Note: IVFFlat indexes require at least 1000 rows for optimal performance.
-- If tables are empty, indexes will still be created but may not be efficient
-- until sufficient data is accumulated. Consider REINDEX after data loading.

-- Create IVFFlat vector index for knowledge_base
CREATE INDEX IF NOT EXISTS idx_kb_vector
  ON public.knowledge_base
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

COMMENT ON INDEX idx_kb_vector IS 'IVFFlat vector index for similarity search on knowledge_base. lists=100 provides good trade-off for 10M+ rows.';

-- Create GIN index on knowledge_base metadata for JSON queries
CREATE INDEX IF NOT EXISTS idx_kb_metadata
  ON public.knowledge_base
  USING gin (metadata);

COMMENT ON INDEX idx_kb_metadata IS 'GIN index for JSONB metadata queries (file_path, language, etc.)';

-- Create B-tree index on knowledge_base repo_id for filtering
CREATE INDEX IF NOT EXISTS idx_kb_repo_id
  ON public.knowledge_base(repo_id);

COMMENT ON INDEX idx_kb_repo_id IS 'B-tree index for repository filtering';

-- Create IVFFlat vector index for learned_constraints
CREATE INDEX IF NOT EXISTS idx_lc_vector
  ON public.learned_constraints
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

COMMENT ON INDEX idx_lc_vector IS 'IVFFlat vector index for constraint matching. lists=100 provides good trade-off for 10M+ rows.';

-- Create partial index for active learned_constraints (not expired)
CREATE INDEX IF NOT EXISTS idx_lc_active
  ON public.learned_constraints(repo_id, code_pattern)
  WHERE expires_at > now();

COMMENT ON INDEX idx_lc_active IS 'Partial B-tree index for active (non-expired) constraints. Improves query performance for constraint checks.';

-- Create B-tree index on learned_constraints expiration for cleanup jobs
CREATE INDEX IF NOT EXISTS idx_lc_expires_at
  ON public.learned_constraints(expires_at);

COMMENT ON INDEX idx_lc_expires_at IS 'B-tree index for expiration cleanup jobs';

-- Verify indexes created
SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename IN ('knowledge_base', 'learned_constraints')
ORDER BY tablename, indexname;
