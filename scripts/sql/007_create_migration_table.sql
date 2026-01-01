-- Migration: 007_create_migration_table.sql
-- Purpose: Create schema_migrations table to track migration history
-- Dependencies: None (must run last to record previous migrations)
-- Idempotent: Yes (uses IF NOT EXISTS)

-- Create schema_migrations table
CREATE TABLE IF NOT EXISTS public.schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ DEFAULT now()
);

-- Add table comment for documentation
COMMENT ON TABLE public.schema_migrations IS 'Track database schema version and migration history. Prevents duplicate migrations.';

-- Add column comments
COMMENT ON COLUMN public.schema_migrations.version IS 'Migration version identifier (e.g., "001_create_extension.sql")';
COMMENT ON COLUMN public.schema_migrations.applied_at IS 'Timestamp of migration application';

-- Insert previous migration records (this migration and all previous ones)
INSERT INTO public.schema_migrations (version) VALUES
    ('001_create_extension.sql'),
    ('002_create_knowledge_base.sql'),
    ('003_create_learned_constraints.sql'),
    ('004_create_feedback_audit_log.sql'),
    ('005_create_vector_indexes.sql'),
    ('006_create_functions.sql'),
    ('007_create_migration_table.sql')
ON CONFLICT (version) DO NOTHING;

-- Verify all migrations recorded
SELECT version, applied_at
FROM public.schema_migrations
ORDER BY applied_at, version;

-- Expected output: All 7 migrations listed with timestamps
