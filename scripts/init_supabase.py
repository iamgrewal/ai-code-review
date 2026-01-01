"""
Supabase database initialization script for CortexReview platform.

Creates the necessary tables, indexes, and extensions for:
- RAG (Retrieval-Augmented Generation) with vector embeddings
- RLHF (Learning Loop) with learned constraints
- Feedback audit log for compliance
- Repo-level data isolation per Constitution XIII (Data Governance)

Run this script once during initial setup:
    python scripts/init_supabase.py

Environment Variables Required:
    SUPABASE_DB_URL: PostgreSQL connection string
"""

import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from loguru import logger

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv()

SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL")

if not SUPABASE_DB_URL:
    logger.error("SUPABASE_DB_URL environment variable not set")
    logger.info("Create a .env file with SUPABASE_DB_URL=postgresql://...")
    sys.exit(1)


# ============================================================================
# SQL Statements for Database Initialization
# ============================================================================

SQL_STATEMENTS = [
    # ============================================================================
    # Enable Required Extensions
    # ============================================================================
    """
    -- Enable pgvector for vector similarity search (RAG)
    CREATE EXTENSION IF NOT EXISTS vector;

    -- Enable uuid-ossp for UUID generation
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    """,
    # ============================================================================
    # RAG Knowledge Base Table
    # ============================================================================
    """
    -- Table: knowledge_base
    -- Stores vector embeddings for code pattern retrieval
    CREATE TABLE IF NOT EXISTS knowledge_base (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        repo_id TEXT NOT NULL,
        file_path TEXT NOT NULL,
        commit_sha TEXT NOT NULL,
        branch TEXT DEFAULT 'main',
        code_chunk TEXT NOT NULL,
        embedding vector(1536) NOT NULL,  -- OpenAI text-embedding-3-small dimension
        language TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

        -- Repo-level data isolation (Constitution XIII)
        CONSTRAINT knowledge_base_repo_check CHECK (repo_id IS NOT NULL)
    );

    -- Index for vector similarity search (IVFFlat for performance)
    CREATE INDEX IF NOT EXISTS knowledge_base_embedding_idx
    ON knowledge_base
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

    -- Index for repo-specific queries
    CREATE INDEX IF NOT EXISTS knowledge_base_repo_idx
    ON knowledge_base(repo_id);

    -- Index for commit-based lookups
    CREATE INDEX IF NOT EXISTS knowledge_base_commit_idx
    ON knowledge_base(commit_sha);

    -- Index for file-based lookups
    CREATE INDEX IF NOT EXISTS knowledge_base_file_idx
    ON knowledge_base(file_path);

    -- Updated at trigger
    CREATE OR REPLACE FUNCTION update_knowledge_base_updated_at()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = NOW();
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;

    DROP TRIGGER IF EXISTS update_knowledge_base_updated_at_trigger ON knowledge_base;
    CREATE TRIGGER update_knowledge_base_updated_at_trigger
        BEFORE UPDATE ON knowledge_base
        FOR EACH ROW
        EXECUTE FUNCTION update_knowledge_base_updated_at();
    """,
    # ============================================================================
    # Learned Constraints Table (RLHF)
    # ============================================================================
    """
    -- Table: learned_constraints
    -- Stores negative examples from user feedback for learning loop
    CREATE TABLE IF NOT EXISTS learned_constraints (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        repo_id TEXT NOT NULL,
        violation_reason TEXT NOT NULL,
        code_pattern TEXT NOT NULL,
        user_reason TEXT NOT NULL,
        embedding vector(1536) NOT NULL,  -- For similarity matching
        confidence_score FLOAT DEFAULT 0.5,
        expires_at TIMESTAMP WITH TIME ZONE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        version INT DEFAULT 1,
        feedback_count INT DEFAULT 1,

        -- Repo-level data isolation (Constitution XIII)
        CONSTRAINT learned_constraints_repo_check CHECK (repo_id IS NOT NULL),
        CONSTRAINT learned_constraints_confidence_check CHECK (confidence_score BETWEEN 0 AND 1)
    );

    -- Index for vector similarity search (constraint matching)
    CREATE INDEX IF NOT EXISTS learned_constraints_embedding_idx
    ON learned_constraints
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 50);

    -- Index for repo-specific queries
    CREATE INDEX IF NOT EXISTS learned_constraints_repo_idx
    ON learned_constraints(repo_id);

    -- Index for expiration queries (cleanup job)
    CREATE INDEX IF NOT EXISTS learned_constraints_expires_at_idx
    ON learned_constraints(expires_at)
    WHERE expires_at IS NOT NULL;

    -- Index for active constraints (not expired)
    CREATE INDEX IF NOT EXISTS learned_constraints_active_idx
    ON learned_constraints(repo_id, confidence_score DESC)
    WHERE expires_at IS NULL OR expires_at > NOW();
    """,
    # ============================================================================
    # Feedback Audit Log Table
    # ============================================================================
    """
    -- Table: feedback_audit_log
    -- Stores all user feedback for compliance and analysis
    CREATE TABLE IF NOT EXISTS feedback_audit_log (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        repo_id TEXT NOT NULL,
        comment_id TEXT NOT NULL,
        review_id TEXT NOT NULL,
        user_id TEXT,
        action TEXT NOT NULL,  -- accepted, rejected, modified
        reason TEXT NOT NULL,  -- false_positive, logic_error, etc.
        developer_comment TEXT,
        code_snapshot TEXT,
        trace_id TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

        -- Repo-level data isolation (Constitution XIII)
        CONSTRAINT feedback_audit_log_repo_check CHECK (repo_id IS NOT NULL),
        CONSTRAINT feedback_audit_log_action_check CHECK (action IN ('accepted', 'rejected', 'modified'))
    );

    -- Index for repo-specific audit queries
    CREATE INDEX IF NOT EXISTS feedback_audit_log_repo_idx
    ON feedback_audit_log(repo_id);

    -- Index for comment-based lookups
    CREATE INDEX IF NOT EXISTS feedback_audit_log_comment_idx
    ON feedback_audit_log(comment_id);

    -- Index for time-series analysis
    CREATE INDEX IF NOT EXISTS feedback_audit_log_created_at_idx
    ON feedback_audit_log(created_at DESC);

    -- Index for review correlation
    CREATE INDEX IF NOT EXISTS feedback_audit_log_review_idx
    ON feedback_audit_log(review_id);

    -- Index for user activity analysis
    CREATE INDEX IF NOT EXISTS feedback_audit_log_user_idx
    ON feedback_audit_log(user_id)
    WHERE user_id IS NOT NULL;

    -- Index for action-based filtering
    CREATE INDEX IF NOT EXISTS feedback_audit_log_action_idx
    ON feedback_audit_log(action);
    """,
    # ============================================================================
    # Helper Functions
    # ============================================================================
    """
    -- Function: Cleanup expired constraints
    -- Called by Celery beat task daily
    CREATE OR REPLACE FUNCTION cleanup_expired_constraints()
    RETURNS INT AS $$
    DECLARE
        deleted_count INT;
    BEGIN
        DELETE FROM learned_constraints
        WHERE expires_at IS NOT NULL
        AND expires_at < NOW();

        GET DIAGNOSTICS deleted_count = ROW_COUNT;
        RETURN deleted_count;
    END;
    $$ LANGUAGE plpgsql;

    -- Function: Get active constraints for repository
    CREATE OR REPLACE FUNCTION get_active_constraints(p_repo_id TEXT)
    RETURNS TABLE (
        id UUID,
        code_pattern TEXT,
        embedding vector(1536),
        confidence_score FLOAT
    ) AS $$
    BEGIN
        RETURN QUERY
        SELECT id, code_pattern, embedding, confidence_score
        FROM learned_constraints
        WHERE repo_id = p_repo_id
        AND (expires_at IS NULL OR expires_at > NOW())
        ORDER BY confidence_score DESC;
    END;
    $$ LANGUAGE plpgsql;

    -- Function: Search knowledge base with similarity
    CREATE OR REPLACE FUNCTION search_knowledge_base(
        p_repo_id TEXT,
        p_query_embedding vector(1536),
        p_threshold FLOAT DEFAULT 0.7,
        p_limit INT DEFAULT 10
    )
    RETURNS TABLE (
        id UUID,
        file_path TEXT,
        code_chunk TEXT,
        similarity FLOAT
    ) AS $$
    BEGIN
        RETURN QUERY
        SELECT
            kb.id,
            kb.file_path,
            kb.code_chunk,
            1 - (kb.embedding <=> p_query_embedding) AS similarity
        FROM knowledge_base kb
        WHERE kb.repo_id = p_repo_id
        AND 1 - (kb.embedding <=> p_query_embedding) > p_threshold
        ORDER BY kb.embedding <=> p_query_embedding
        LIMIT p_limit;
    END;
    $$ LANGUAGE plpgsql;
    """,
]


def main():
    """Initialize Supabase database with CortexReview schema."""
    logger.info("Starting Supabase database initialization...")

    try:
        # Connect to Supabase PostgreSQL
        logger.info(
            f"Connecting to Supabase at {SUPABASE_DB_URL.split('@')[1] if '@' in SUPABASE_DB_URL else 'localhost'}"
        )
        conn = psycopg2.connect(SUPABASE_DB_URL)
        conn.autocommit = True
        cursor = conn.cursor()

        # Execute each SQL statement
        for i, statement in enumerate(SQL_STATEMENTS, start=1):
            try:
                logger.info(f"Executing SQL statement {i}/{len(SQL_STATEMENTS)}...")
                cursor.execute(statement)
                logger.info(f"Statement {i} completed successfully")
            except Exception as e:
                logger.error(f"Error executing statement {i}: {e}")
                raise

        # Verify tables created
        logger.info("Verifying table creation...")
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN ('knowledge_base', 'learned_constraints', 'feedback_audit_log')
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        logger.info(f"Created {len(tables)} tables: {[t[0] for t in tables]}")

        # Verify indexes created
        logger.info("Verifying index creation...")
        cursor.execute("""
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname = 'public'
            ORDER BY indexname;
        """)
        indexes = cursor.fetchall()
        logger.info(f"Created {len(indexes)} indexes")

        # Verify extensions enabled
        logger.info("Verifying extension installation...")
        cursor.execute("""
            SELECT extname
            FROM pg_extension
            WHERE extname IN ('vector', 'uuid-ossp')
            ORDER BY extname;
        """)
        extensions = cursor.fetchall()
        logger.info(f"Enabled {len(extensions)} extensions: {[e[0] for e in extensions]}")

        cursor.close()
        conn.close()

        logger.success("Supabase database initialization completed successfully!")
        logger.info("\nNext steps:")
        logger.info("1. Test the connection: python scripts/test_supabase.py")
        logger.info("2. Configure .env with SUPABASE_URL and SUPABASE_SERVICE_KEY")
        logger.info("3. Start the worker: python worker.py")

    except Exception as e:
        logger.error(f"Failed to initialize Supabase database: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
