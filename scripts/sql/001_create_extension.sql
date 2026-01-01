-- Migration: 001_create_extension.sql
-- Purpose: Install pgvector extension for vector similarity search
-- Dependencies: None
-- Idempotent: Yes (uses IF NOT EXISTS)

-- Enable pgvector extension for vector operations
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify extension is installed
SELECT
    extname as extension_name,
    extversion as version
FROM pg_extension
WHERE extname = 'vector';

-- Expected output:
-- extension_name | version
-- ---------------+---------
-- vector         | 0.5.x (or later)
