-- Migration: 003_create_learned_constraints.sql
-- Purpose: Create learned_constraints table for RLHF negative examples
-- Dependencies: 001_create_extension.sql (pgvector must be installed)
-- Idempotent: Yes (uses IF NOT EXISTS)

-- Create learned_constraints table
CREATE TABLE IF NOT EXISTS public.learned_constraints (
    id BIGSERIAL PRIMARY KEY,
    repo_id TEXT NOT NULL,
    violation_reason TEXT,
    code_pattern TEXT NOT NULL,
    user_reason TEXT NOT NULL,
    embedding vector(1536) NOT NULL,
    confidence_score FLOAT DEFAULT 1.0,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Add table comment for documentation
COMMENT ON TABLE public.learned_constraints IS 'Negative examples from RLHF feedback. Contains patterns that should be suppressed in future reviews.';

-- Add column comments
COMMENT ON COLUMN public.learned_constraints.id IS 'Auto-incrementing identifier';
COMMENT ON COLUMN public.learned_constraints.repo_id IS 'Repository identifier';
COMMENT ON COLUMN public.learned_constraints.violation_reason IS 'Original review comment that was rejected';
COMMENT ON COLUMN public.learned_constraints.code_pattern IS 'Code pattern that triggered false positive';
COMMENT ON COLUMN public.learned_constraints.user_reason IS 'User explanation for rejection (why this was a false positive)';
COMMENT ON COLUMN public.learned_constraints.embedding IS 'Vector embedding for pattern matching (1536 dimensions)';
COMMENT ON COLUMN public.learned_constraints.confidence_score IS 'Aggregated confidence from multiple feedback (0.0 to 1.0)';
COMMENT ON COLUMN public.learned_constraints.expires_at IS 'Expiration timestamp (default: 90 days from creation)';
COMMENT ON COLUMN public.learned_constraints.created_at IS 'Timestamp of constraint creation';

-- Create indexes (will be updated in 005_create_vector_indexes.sql)
-- Note: IVFFlat indexes are created separately after data is loaded
-- for optimal index build performance
