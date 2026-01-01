-- Migration: 002_create_knowledge_base.sql
-- Purpose: Create knowledge_base table for RAG context retrieval
-- Dependencies: 001_create_extension.sql (pgvector must be installed)
-- Idempotent: Yes (uses IF NOT EXISTS)

-- Create knowledge_base table
CREATE TABLE IF NOT EXISTS public.knowledge_base (
    id BIGSERIAL PRIMARY KEY,
    repo_id TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    embedding vector(1536) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Add table comment for documentation
COMMENT ON TABLE public.knowledge_base IS 'Vector embeddings for RAG context retrieval. Contains code patterns from indexed repositories.';

-- Add column comments
COMMENT ON COLUMN public.knowledge_base.id IS 'Auto-incrementing identifier';
COMMENT ON COLUMN public.knowledge_base.repo_id IS 'Repository identifier (e.g., "owner/repo")';
COMMENT ON COLUMN public.knowledge_base.content IS 'Code snippet or pattern content';
COMMENT ON COLUMN public.knowledge_base.metadata IS 'Additional metadata (file_path, commit_sha, language) in JSON format';
COMMENT ON COLUMN public.knowledge_base.embedding IS 'Vector embedding for similarity search (1536 dimensions for OpenAI text-embedding-3-small)';
COMMENT ON COLUMN public.knowledge_base.created_at IS 'Timestamp of record creation';

-- Create indexes (will be updated in 005_create_vector_indexes.sql)
-- Note: IVFFlat indexes are created separately after data is loaded
-- for optimal index build performance
