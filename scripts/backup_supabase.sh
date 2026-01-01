#!/bin/bash
###############################################################################
# Supabase Database Backup Script
#
# Purpose: Create compressed SQL dump of local Supabase PostgreSQL database
# - Uses pg_dump with custom format for reliable restore
# - Includes all tables, indexes, functions, and vector data
# - Creates timestamped backup files in ./backups directory
# - Compresses output with gzip to reduce storage requirements
#
# Usage: ./scripts/backup_supabase.sh [backup_name]
#
# Arguments:
#   backup_name - Optional custom name for backup file (default: auto-timestamp)
#
# Environment Variables Required:
#   POSTGRES_PASSWORD - PostgreSQL password from .env
#   POSTGRES_DB - Database name (default: supabase)
#
# Output:
#   Creates ./backups/supabase_backup_YYYYMMDD_HHMMSS.sql.gz
#
# Example:
#   ./scripts/backup_supabase.sh
#   ./scripts/backup_supabase.sh my_backup
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
POSTGRES_USER="${POSTGRES_USER:-supabase_admin}"

# Container name (override if using custom name)
CONTAINER_NAME="${CONTAINER_NAME:-cortexreview-supabase-db}"

# Backup name (timestamp or custom)
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="${1:-supabase_backup_${TIMESTAMP}}"

###############################################################################
# Validation
###############################################################################

echo_blue "=========================================="
echo_blue "Supabase Database Backup"
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

# Create backup directory if it doesn't exist
if [ ! -d "$BACKUP_DIR" ]; then
    echo_yellow "Creating backup directory: $BACKUP_DIR"
    mkdir -p "$BACKUP_DIR"
fi

###############################################################################
# Backup Process
###############################################################################

echo_green "=== Starting Backup Process ==="
echo_yellow "Container: ${CONTAINER_NAME}"
echo_yellow "Database: ${POSTGRES_DB}"
echo_yellow "Backup file: ${BACKUP_DIR}/${BACKUP_NAME}.sql.gz"

# Generate temporary file path
TEMP_DUMP="${BACKUP_DIR}/.temp_dump_${TIMESTAMP}.sql"

# Run pg_dump inside the container
echo_yellow "Running pg_dump (this may take a while for large databases)..."

if docker exec "${CONTAINER_NAME}" pg_dump \
    -h "${POSTGRES_HOST}" \
    -p "${POSTGRES_PORT}" \
    -U "${POSTGRES_USER}" \
    -d "${POSTGRES_DB}" \
    --verbose \
    --no-owner \
    --no-acl \
    --format=plain \
    --encoding=UTF8 \
    > "${TEMP_DUMP}" 2>&1; then

    # Compress the dump
    echo_yellow "Compressing backup with gzip..."
    gzip -c "${TEMP_DUMP}" > "${BACKUP_DIR}/${BACKUP_NAME}.sql.gz"

    # Calculate file sizes
    UNCOMPRESSED_SIZE=$(du -h "${TEMP_DUMP}" | cut -f1)
    COMPRESSED_SIZE=$(du -h "${BACKUP_DIR}/${BACKUP_NAME}.sql.gz" | cut -f1)

    # Clean up temp file
    rm -f "${TEMP_DUMP}"

    # Set appropriate permissions
    chmod 640 "${BACKUP_DIR}/${BACKUP_NAME}.sql.gz"

    echo_green "=== Backup Complete ==="
    echo_green "✓ Backup created: ${BACKUP_DIR}/${BACKUP_NAME}.sql.gz"
    echo_yellow "  Uncompressed size: ${UNCOMPRESSED_SIZE}"
    echo_yellow "  Compressed size: ${COMPRESSED_SIZE}"

    # Display summary
    echo_yellow "\nTo restore this backup, run:"
    echo_yellow "  ./scripts/restore_supabase.sh ${BACKUP_NAME}.sql.gz"

    # Optional: List other backups
    BACKUP_COUNT=$(ls -1 "${BACKUP_DIR}"/*.sql.gz 2>/dev/null | wc -l)
    echo_yellow "\nTotal backups in ${BACKUP_DIR}: ${BACKUP_COUNT}"

    exit 0

else
    echo_red "ERROR: pg_dump failed"
    echo_red "Please check the error messages above"
    rm -f "${TEMP_DUMP}"
    exit 1
fi
