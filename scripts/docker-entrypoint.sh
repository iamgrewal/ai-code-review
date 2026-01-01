#!/bin/bash
###############################################################################
# Docker Entrypoint Wrapper for Supabase PostgreSQL Container
#
# Purpose: Execute pre-flight checks and automated database initialization
# - Validates environment variables (POSTGRES_PASSWORD, JWT_SECRET, etc.)
# - Checks system resources (RAM, CPU, disk space)
# - Runs SQL migrations on first startup automatically
# - Tracks migration history to prevent re-initialization
# - Fails fast with clear error messages if validation fails
#
# Usage: Called from docker-compose.yml as entrypoint for supabase-db service
###############################################################################

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo_green() { echo -e "${GREEN}$*${NC}"; }
echo_yellow() { echo -e "${YELLOW}$*${NC}"; }
echo_red() { echo -e "${RED}$*${NC}"; }
echo_blue() { echo -e "${BLUE}$*${NC}"; }

# Path to pre-flight check scripts
PREFLIGHT_CHECK="/app/scripts/preflight_check.py"
RESOURCE_CHECK="/app/scripts/resource_check.py"
SQL_MIGRATIONS_DIR="/app/scripts/sql"
MIGRATION_LOCKFILE="/var/lib/postgresql/data/.migrations-applied"

###############################################################################
# Phase 1: Pre-flight Validation
###############################################################################

echo_blue "=========================================="
echo_blue "Supabase PostgreSQL - Container Startup"
echo_blue "=========================================="
echo_green "=== Phase 1: Pre-flight Validation ==="

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo_red "ERROR: Python 3 not found. Cannot run pre-flight checks."
    echo_red "Please ensure Python 3 is installed in the container image."
    exit 1
fi

# Run environment variable validation
if [ -f "$PREFLIGHT_CHECK" ]; then
    echo_yellow "Running environment variable validation..."
    if python3 "$PREFLIGHT_CHECK"; then
        echo_green "✓ Environment variable validation passed"
    else
        echo_red "✗ Environment variable validation failed"
        echo_red "Please check your environment variables and try again."
        exit 1
    fi
else
    echo_yellow "Warning: preflight_check.py not found, skipping environment validation"
fi

# Run system resource validation
if [ -f "$RESOURCE_CHECK" ]; then
    echo_yellow "Running system resource validation..."
    if python3 "$RESOURCE_CHECK"; then
        echo_green "✓ System resource validation passed"
    else
        echo_red "✗ System resource validation failed"
        echo_red "Please ensure minimum resources are available (4GB RAM, 2 CPU cores, 20GB disk)."
        exit 1
    fi
else
    echo_yellow "Warning: resource_check.py not found, skipping resource validation"
fi

###############################################################################
# Helper function to wait for PostgreSQL to be ready
###############################################################################

wait_for_postgres() {
    local max_attempts=30
    local attempt=0

    echo_yellow "Waiting for PostgreSQL to be ready..."

    while [ $attempt -lt $max_attempts ]; do
        if pg_isready -U postgres -d "${POSTGRES_DB:-supabase}" > /dev/null 2>&1; then
            echo_green "✓ PostgreSQL is ready"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 2
    done

    echo_red "ERROR: PostgreSQL did not become ready after ${max_attempts} attempts"
    return 1
}

###############################################################################
# Helper function to run SQL migrations
###############################################################################

run_migrations() {
    echo_yellow "Running database schema migrations..."

    if [ ! -d "$SQL_MIGRATIONS_DIR" ]; then
        echo_yellow "Warning: SQL migrations directory not found at $SQL_MIGRATIONS_DIR"
        return 0
    fi

    # Apply migrations in sorted order
    local migration_count=0
    for migration in $(ls -1 "$SQL_MIGRATIONS_DIR"/*.sql 2>/dev/null | sort); do
        if [ -f "$migration" ]; then
            migration_name=$(basename "$migration")
            echo_yellow "Applying migration: $migration_name"

            # Execute migration with error handling (use postgres superuser or configured POSTGRES_USER)
            # Capture stderr for debugging on failure, suppress stdout (psql noise)
            if psql -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-supabase}" -f "$migration" > /dev/null 2>"/tmp/migration_error_$$.log"; then
                echo_green "✓ Applied: $migration_name"
                migration_count=$((migration_count + 1))
                # Clean up error log on success
                rm -f "/tmp/migration_error_$$.log"
            else
                echo_red "✗ Failed to apply migration: $migration_name"
                echo_red "The migration file may have syntax errors or dependencies not met."
                echo_red "Error details:"
                cat "/tmp/migration_error_$$.log" | head -20 || echo_red "  (Unable to read error log)"
                rm -f "/tmp/migration_error_$$.log"
                return 1
            fi
        fi
    done

    echo_green "✓ Applied $migration_count migrations successfully"

    # Create lockfile to prevent re-initialization
    touch "$MIGRATION_LOCKFILE"

    return 0
}

###############################################################################
# Helper function to check if migrations already applied
###############################################################################

migrations_already_applied() {
    if [ -f "$MIGRATION_LOCKFILE" ]; then
        return 0  # Lockfile exists, migrations already applied
    fi

    # Also check if schema_migrations table exists and has records
    if PGPASSWORD="${POSTGRES_PASSWORD}" psql -U postgres -d "${POSTGRES_DB:-supabase}" -tAc \
        "SELECT 1 FROM information_schema.tables WHERE table_name = 'schema_migrations' LIMIT 1;" 2>/dev/null | grep -q 1; then
        # Table exists, check if it has records
        local count=$(PGPASSWORD="${POSTGRES_PASSWORD}" psql -U postgres -d "${POSTGRES_DB:-supabase}" -tAc \
            "SELECT COUNT(*) FROM schema_migrations;" 2>/dev/null || echo "0")
        if [ "$count" -gt 0 ]; then
            touch "$MIGRATION_LOCKFILE"
            return 0
        fi
    fi

    return 1  # Migrations not applied yet
}

###############################################################################
# Phase 2: Start PostgreSQL with initialization hook
###############################################################################

echo_green "=== Phase 2: Starting PostgreSQL ==="

# Check if this is a fresh database (no data in PGDATA)
FRESH_DATABASE=false
if [ ! -f "/var/lib/postgresql/data/PG_VERSION" ]; then
    FRESH_DATABASE=true
    echo_yellow "Fresh database detected - initialization will be required"
fi

# Start PostgreSQL in the background and capture its PID
echo_yellow "Starting PostgreSQL server..."
/usr/local/bin/docker-entrypoint.sh "$@" &
POSTGRES_PID=$!

# Trap signals to forward to PostgreSQL
trap 'kill -TERM $POSTGRES_PID 2>/dev/null; wait $POSTGRES_PID; exit $?' TERM INT

# Wait for PostgreSQL to be ready
if ! wait_for_postgres; then
    echo_red "ERROR: PostgreSQL failed to start properly"
    kill $POSTGRES_PID 2>/dev/null || true
    wait $POSTGRES_PID 2>/dev/null || true
    exit 1
fi

###############################################################################
# Phase 3: Database Initialization (only on fresh start)
###############################################################################

if [ "$FRESH_DATABASE" = true ] || ! migrations_already_applied; then
    echo_green "=== Phase 3: Database Initialization ==="

    # Wait a bit more for PostgreSQL to be fully ready
    sleep 3

    # Run migrations
    if run_migrations; then
        echo_green "✓ Database initialization completed successfully"
    else
        echo_red "ERROR: Database initialization failed"
        kill $POSTGRES_PID 2>/dev/null || true
        wait $POSTGRES_PID 2>/dev/null || true
        exit 1
    fi
else
    echo_green "=== Phase 3: Skipping Initialization (Already Applied) ==="
    echo_yellow "Database schema already initialized - skipping migrations"
    echo_yellow "To re-initialize, delete the volume: docker volume rm cortexreview-supabase-db-data"
fi

###############################################################################
# Phase 4: Handoff to PostgreSQL
###############################################################################

echo_green "=== Phase 4: PostgreSQL Running ==="
echo_blue "=========================================="
echo_green "✓ Supabase PostgreSQL is ready"
echo_blue "=========================================="

# Wait for PostgreSQL process to complete
# This keeps the container running
wait $POSTGRES_PID
EXIT_CODE=$?

echo_yellow "PostgreSQL stopped with exit code: $EXIT_CODE"
exit $EXIT_CODE
