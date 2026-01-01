-- Migration: 006_create_functions.sql
-- Purpose: Create SQL functions for vector similarity search
-- Dependencies: 001_create_extension.sql, 002_create_knowledge_base.sql, 003_create_learned_constraints.sql
-- Idempotent: Yes (uses OR REPLACE)

-- Create match_knowledge function for RAG context retrieval
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
STABLE
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

-- Add function comment
COMMENT ON FUNCTION public.match_knowledge IS 'Retrieve similar code patterns from knowledge_base for RAG context. Parameters: query_embedding (vector), match_threshold (float, default 0.75), match_count (int, default 3). Returns table of matching entries with similarity scores.';

-- Create check_constraints function for RLHF constraint matching
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
STABLE
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

-- Add function comment
COMMENT ON FUNCTION public.check_constraints IS 'Check if code pattern matches learned constraints (false positives). Parameters: query_embedding (vector), match_threshold (float, default 0.8). Returns table of matching constraints with user reasons. Higher threshold (0.8) ensures only very similar patterns are suppressed.';

-- Verify functions created
SELECT
    p.proname as function_name,
    pg_get_function_arguments(p.oid) as arguments,
    pg_get_functiondef(p.oid) as definition
FROM pg_proc p
JOIN pg_namespace n ON p.pronamespace = n.oid
WHERE n.nspname = 'public'
  AND p.proname IN ('match_knowledge', 'check_constraints');
