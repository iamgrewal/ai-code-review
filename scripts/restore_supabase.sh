#!/bin/bash
###############################################################################
# Supabase Database Restore Script
#
# Purpose: Restore database from compressed SQL dump created by backup_supabase.sh
# - Decompresses gzip backup file
# - Drops and recreates the target database
# - Restores all tables, indexes, functions, and vector data
# - Validates restore integrity by checking table counts
#
# Usage: ./scripts/restore_supabase.sh <backup_file.sql.gz>
#
# Arguments:
#   backup_file - Path to backup file (relative or absolute)
#
# Environment Variables Required:
#   POSTGRES_PASSWORD - PostgreSQL password from .env
#   POSTGRES_DB - Database name (default: supabase)
#
# Safety:
#   - Prompts for confirmation before dropping existing database
#   - Creates timestamped pre-restore backup automatically
#   - Validates backup file exists before proceeding
#   - Shows progress indicators during restore
#
# Example:
#   ./scripts/restore_supabase.sh backups/supabase_backup_20260101_120000.sql.gz
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

###############################################################################
# Configuration
###############################################################################

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Backup directory
BACKUP_DIR="${PROJECT_ROOT}/backups"

# Database configuration (load from .env if available)
if [ -f "${PROJECT_ROOT}/.env" ]; then
    source "${PROJECT_ROOT}/.env"
fi

POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-your_secure_password_here_min_16_chars}"
POSTGRES_DB="${POSTGRES_DB:-supabase}"
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
TEMPLATE_DB="template1"

# Container name (override if using custom name)
CONTAINER_NAME="${CONTAINER_NAME:-cortexreview-supabase-db}"

###############################################################################
# Argument Parsing
###############################################################################

if [ -z "$1" ]; then
    echo_red "ERROR: No backup file specified"
    echo_yellow "Usage: $0 <backup_file.sql.gz>"
    echo_yellow "\nAvailable backups in ${BACKUP_DIR}:"
    ls -lh "${BACKUP_DIR}"/*.sql.gz 2>/dev/null || echo_yellow "  No backups found"
    exit 1
fi

# Resolve backup file path
BACKUP_FILE="$1"
if [ ! -f "$BACKUP_FILE" ]; then
    # Try relative to backup directory
    if [ -f "${BACKUP_DIR}/$BACKUP_FILE" ]; then
        BACKUP_FILE="${BACKUP_DIR}/$BACKUP_FILE"
    else
        echo_red "ERROR: Backup file not found: $BACKUP_FILE"
        exit 1
    fi
fi

###############################################################################
# Validation
###############################################################################

echo_blue "=========================================="
echo_blue "Supabase Database Restore"
echo_blue "=========================================="

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo_red "ERROR: Docker is not installed or not in PATH"
    exit 1
fi

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo_red "ERROR: Container ${CONTAINER_NAME} is not running"
    echo_yellow "Please start the container with: docker compose up -d supabase-db"
    exit 1
fi

# Validate backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    echo_red "ERROR: Backup file not found: $BACKUP_FILE"
    exit 1
fi

# Show backup file info
BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo_yellow "Backup file: ${BACKUP_FILE}"
echo_yellow "Backup size: ${BACKUP_SIZE}"

# Prompt for confirmation
echo_red "\n⚠️  WARNING: This will DROP and recreate the database '${POSTGRES_DB}'"
echo_red "    All existing data will be replaced with the backup contents."
echo_yellow "\nA pre-restore backup will be created automatically."
echo
read -p "Are you sure you want to proceed? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo_yellow "Restore cancelled by user"
    exit 0
fi

###############################################################################
# Pre-Restore Backup
###############################################################################

echo_green "\n=== Creating Pre-Restore Backup ==="

# Create automatic pre-restore backup
PRE_RESTORE_BACKUP="${BACKUP_DIR}/.pre_restore_$(date +%Y%m%d_%H%M%S).sql.gz"

echo_yellow "Backing up current database to: ${PRE_RESTORE_BACKUP}"

if docker exec "${CONTAINER_NAME}" pg_dump \
    -h "${POSTGRES_HOST}" \
    -p "${POSTGRES_PORT}" \
    -U "${POSTGRES_USER}" \
    -d "${POSTGRES_DB}" \
    --no-owner \
    --no-acl \
    --format=plain \
    2>/dev/null | gzip > "${PRE_RESTORE_BACKUP}"; then
    echo_green "✓ Pre-restore backup created"
else
    echo_yellow "⚠️  Warning: Pre-restore backup failed, continuing anyway"
fi

###############################################################################
# Restore Process
###############################################################################

echo_green "\n=== Starting Restore Process ==="

# Generate temp file for decompressed SQL
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
TEMP_SQL="/tmp/restore_temp_${TIMESTAMP}.sql"

# Decompress backup file
echo_yellow "Decompressing backup file..."
if ! gunzip -c "$BACKUP_FILE" > "${TEMP_SQL}"; then
    echo_red "ERROR: Failed to decompress backup file"
    rm -f "${TEMP_SQL}"
    exit 1
fi

# Drop existing database
echo_yellow "Terminating existing connections and dropping database..."
docker exec "${CONTAINER_NAME}" psql \
    -h "${POSTGRES_HOST}" \
    -p "${POSTGRES_PORT}" \
    -U "${POSTGRES_USER}" \
    -d "${TEMPLATE_DB}" \
    -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${POSTGRES_DB}' AND pid <> pg_backend_pid();" \
    > /dev/null 2>&1 || true

docker exec "${CONTAINER_NAME}" psql \
    -h "${POSTGRES_HOST}" \
    -p "${POSTGRES_PORT}" \
    -U "${POSTGRES_USER}" \
    -d "${TEMPLATE_DB}" \
    -c "DROP DATABASE IF EXISTS ${POSTGRES_DB};" \
    > /dev/null 2>&1 || true

# Create new database
echo_yellow "Creating new database..."
docker exec "${CONTAINER_NAME}" psql \
    -h "${POSTGRES_HOST}" \
    -p "${POSTGRES_PORT}" \
    -U "${POSTGRES_USER}" \
    -d "${TEMPLATE_DB}" \
    -c "CREATE DATABASE ${POSTGRES_DB} ENCODING 'UTF8';" \
    > /dev/null 2>&1

# Copy SQL file into container and restore
echo_yellow "Restoring database (this may take a while)..."

if docker cp "${TEMP_SQL}" "${CONTAINER_NAME}:/tmp/restore_temp.sql"; then
    if docker exec "${CONTAINER_NAME}" psql \
        -h "${POSTGRES_HOST}" \
        -p "${POSTGRES_PORT}" \
        -U "${POSTGRES_USER}" \
        -d "${POSTGRES_DB}" \
        -f "/tmp/restore_temp.sql" \
        > /dev/null 2>&1; then

        echo_green "✓ Database restored successfully"
    else
        echo_red "ERROR: psql restore failed"
        echo_red "Pre-restore backup available at: ${PRE_RESTORE_BACKUP}"
        docker exec "${CONTAINER_NAME}" rm -f "/tmp/restore_temp.sql"
        rm -f "${TEMP_SQL}"
        exit 1
    fi

    # Clean up temp files
    docker exec "${CONTAINER_NAME}" rm -f "/tmp/restore_temp.sql"
else
    echo_red "ERROR: Failed to copy SQL file into container"
    echo_red "Pre-restore backup available at: ${PRE_RESTORE_BACKUP}"
    rm -f "${TEMP_SQL}"
    exit 1
fi

# Clean up temp file
rm -f "${TEMP_SQL}"

###############################################################################
# Validation
###############################################################################

echo_green "\n=== Validating Restore ==="

# Check if critical tables exist
TABLE_COUNT=$(docker exec "${CONTAINER_NAME}" psql \
    -h "${POSTGRES_HOST}" \
    -p "${POSTGRES_PORT}" \
    -U "${POSTGRES_USER}" \
    -d "${POSTGRES_DB}" \
    -tAc \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';" 2>/dev/null || echo "0")

if [ "$TABLE_COUNT" -gt 0 ]; then
    echo_green "✓ Database contains ${TABLE_COUNT} tables"

    # Check specific critical tables
    CRITICAL_TABLES=("knowledge_base" "learned_constraints" "feedback_audit_log" "schema_migrations")
    for table in "${CRITICAL_TABLES[@]}"; do
        if docker exec "${CONTAINER_NAME}" psql \
            -h "${POSTGRES_HOST}" \
            -p "${POSTGRES_PORT}" \
            -U "${POSTGRES_USER}" \
            -d "${POSTGRES_DB}" \
            -c "\dt ${table}" \
            > /dev/null 2>&1; then
            echo_green "✓ Table '${table}' exists"
        else
            echo_yellow "⚠️  Table '${table}' not found"
        fi
    done

    echo_green "\n=== Restore Complete ==="
    echo_green "Database restored from: ${BACKUP_FILE}"

    # Show row counts
    echo_yellow "\nRow counts:"
    docker exec "${CONTAINER_NAME}" psql \
        -h "${POSTGRES_HOST}" \
        -p "${POSTGRES_PORT}" \
        -U "${POSTGRES_USER}" \
        -d "${POSTGRES_DB}" \
        -c "
        SELECT
            schemaname,
            tablename,
            n_live_tup AS row_count
        FROM pg_stat_user_tables
        WHERE schemaname = 'public'
        ORDER BY tablename;
        " 2>/dev/null || echo_yellow "  Unable to retrieve row counts"

    exit 0

else
    echo_red "ERROR: No tables found in database after restore"
    echo_red "Pre-restore backup available at: ${PRE_RESTORE_BACKUP}"
    exit 1
fi
