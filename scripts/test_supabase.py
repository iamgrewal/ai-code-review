"""
Supabase connection test script for CortexReview platform.

Tests database connectivity, table access, and vector operations.

Run after init_supabase.py to verify setup:
    python scripts/test_supabase.py

Environment Variables Required:
    SUPABASE_URL: Supabase project URL
    SUPABASE_SERVICE_KEY: Supabase service role key (bypasses RLS)
    SUPABASE_DB_URL: PostgreSQL connection string (optional, for direct SQL tests)
"""

import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from loguru import logger
from supabase import Client, create_client

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL")

# Validation
if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    logger.error("SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set")
    logger.info("Create a .env file with:")
    logger.info("  SUPABASE_URL=https://your-project.supabase.co")
    logger.info("  SUPABASE_SERVICE_KEY=your-service-role-key")
    sys.exit(1)


def test_supabase_client():
    """Test Supabase client connection and basic operations."""
    logger.info("Testing Supabase client connection...")

    try:
        # Create Supabase client
        client: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        logger.success(f"Connected to Supabase: {SUPABASE_URL}")

        # Test table access (knowledge_base)
        logger.info("Testing knowledge_base table access...")
        result = client.table("knowledge_base").select("*").limit(1).execute()
        logger.success(f"knowledge_base table accessible (count: {len(result.data)})")

        # Test table access (learned_constraints)
        logger.info("Testing learned_constraints table access...")
        result = client.table("learned_constraints").select("*").limit(1).execute()
        logger.success(f"learned_constraints table accessible (count: {len(result.data)})")

        # Test table access (feedback_audit_log)
        logger.info("Testing feedback_audit_log table access...")
        result = client.table("feedback_audit_log").select("*").limit(1).execute()
        logger.success(f"feedback_audit_log table accessible (count: {len(result.data)})")

        return True

    except Exception as e:
        logger.error(f"Supabase client test failed: {e}")
        return False


def test_postgres_connection():
    """Test direct PostgreSQL connection (if DB_URL provided)."""
    if not SUPABASE_DB_URL:
        logger.info("Skipping PostgreSQL connection test (SUPABASE_DB_URL not set)")
        return True

    logger.info("Testing direct PostgreSQL connection...")

    try:
        conn = psycopg2.connect(SUPABASE_DB_URL)
        cursor = conn.cursor()

        # Test connection
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        logger.success(f"PostgreSQL connection established: {version.split(',')[0]}")

        # Test pgvector extension
        cursor.execute("SELECT extname FROM pg_extension WHERE extname = 'vector';")
        if cursor.fetchone():
            logger.success("pgvector extension installed")
        else:
            logger.error("pgvector extension NOT found - run init_supabase.py first")

        # Test table existence
        logger.info("Checking table existence...")
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN ('knowledge_base', 'learned_constraints', 'feedback_audit_log')
            ORDER BY table_name;
        """)
        tables = [row[0] for row in cursor.fetchall()]
        logger.success(f"Tables found: {tables}")

        # Test vector similarity search function
        logger.info("Testing search_knowledge_base function...")
        cursor.execute("""
            SELECT routine_name
            FROM information_schema.routines
            WHERE routine_schema = 'public'
            AND routine_name = 'search_knowledge_base';
        """)
        if cursor.fetchone():
            logger.success("search_knowledge_base function exists")
        else:
            logger.warning("search_knowledge_base function NOT found - run init_supabase.py first")

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        logger.error(f"PostgreSQL connection test failed: {e}")
        return False


def test_vector_operations():
    """Test vector embedding operations (requires DB_URL)."""
    if not SUPABASE_DB_URL:
        logger.info("Skipping vector operations test (SUPABASE_DB_URL not set)")
        return True

    logger.info("Testing vector embedding operations...")

    try:
        import numpy as np

        conn = psycopg2.connect(SUPABASE_DB_URL)
        cursor = conn.cursor()

        # Create test embedding (1536 dimensions for OpenAI)
        test_embedding = np.random.rand(1536).tolist()
        embedding_str = f"[{','.join(map(str, test_embedding[:5]))}, ...]"  # Truncated for display

        logger.info(f"Test embedding dimension: 1536 (sample: {embedding_str})")

        # Test vector similarity search (even with empty table)
        logger.info("Testing vector similarity query syntax...")
        cursor.execute("""
            SELECT 1 - (embedding <=> '[0]'::vector || array_fill(0, ARRAY[1535])::vector) AS similarity
            FROM knowledge_base
            LIMIT 1;
        """)
        result = cursor.fetchone()
        if result:
            logger.success(
                f"Vector similarity query executed: {result[0] if result[0] else 'no data'}"
            )
        else:
            logger.info("Vector similarity query syntax valid (no data in table)")

        cursor.close()
        conn.close()
        return True

    except ImportError:
        logger.warning("Skipping vector operations test (numpy not installed)")
        return True
    except Exception as e:
        logger.error(f"Vector operations test failed: {e}")
        return False


def main():
    """Run all Supabase connection tests."""
    logger.info("Starting Supabase connection tests...\n")

    results = []

    # Test 1: Supabase client connection
    results.append(("Supabase Client", test_supabase_client()))
    logger.info("")

    # Test 2: PostgreSQL connection
    results.append(("PostgreSQL Connection", test_postgres_connection()))
    logger.info("")

    # Test 3: Vector operations
    results.append(("Vector Operations", test_vector_operations()))
    logger.info("")

    # Summary
    logger.info("=" * 50)
    logger.info("Test Summary:")
    logger.info("=" * 50)

    all_passed = True
    for test_name, passed in results:
        status = "PASSED" if passed else "FAILED"
        symbol = "✓" if passed else "✗"
        logger.info(f"{symbol} {test_name}: {status}")
        if not passed:
            all_passed = False

    logger.info("=" * 50)

    if all_passed:
        logger.success("All tests passed! Supabase is ready for CortexReview.")
        logger.info("\nNext steps:")
        logger.info("1. Update .env with your Supabase credentials")
        logger.info("2. Start the worker: python worker.py")
        logger.info("3. Send a webhook to trigger repository indexing")
        return 0
    else:
        logger.error("Some tests failed. Please check the errors above.")
        logger.info("\nTroubleshooting:")
        logger.info("1. Ensure init_supabase.py was run successfully")
        logger.info("2. Verify SUPABASE_URL and SUPABASE_SERVICE_KEY are correct")
        logger.info("3. Check Supabase project status at https://app.supabase.com")
        return 1


if __name__ == "__main__":
    sys.exit(main())
