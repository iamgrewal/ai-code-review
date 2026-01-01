#!/bin/bash

################################################################################
# Supabase External Export Script
#
# Exports data from an external Supabase instance for migration to local
# Preserves vector embeddings and all related tables
#
# Usage: ./scripts/export_from_external.sh
#
# Environment Variables (set in .env or export before running):
#   EXTERNAL_SUPABASE_DB_URL      - Full PostgreSQL connection URL for external Supabase
#   EXTERNAL_SUPABASE_HOST        - External Supabase host (alternative to URL)
#   EXTERNAL_SUPABASE_PORT        - External Supabase port (default: 5432)
#   EXTERNAL_SUPABASE_DB          - External database name (default: postgres)
#   EXTERNAL_SUPABASE_USER        - Database user (default: postgres)
#   EXTERNAL_SUPABASE_PASSWORD    - Database password
#   EXPORT_DIR                    - Directory for exports (default: ./backups/exports)
################################################################################

set -e  # Exit on error
set -u  # Exit on undefined variable

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Configuration
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
EXPORT_DIR="${EXPORT_DIR:-./backups/exports}"
EXPORT_FILE="${EXPORT_DIR}/supabase_export_${TIMESTAMP}.sql.gz"

# Tables to export (in dependency order)
TABLES=(
    "knowledge_base"
    "learned_constraints"
    "feedback_audit_log"
    "schema_migrations"
)

################################################################################
# Validation Functions
################################################################################

validate_environment() {
    log_info "Validating environment configuration..."

    # Check for either full URL or individual components
    if [ -z "${EXTERNAL_SUPABASE_DB_URL:-}" ]; then
        # Build connection string from components
        LOCAL_HOST="${EXTERNAL_SUPABASE_HOST:-}"
        LOCAL_PORT="${EXTERNAL_SUPABASE_PORT:-5432}"
        LOCAL_DB="${EXTERNAL_SUPABASE_DB:-postgres}"
        LOCAL_USER="${EXTERNAL_SUPABASE_USER:-postgres}"
        LOCAL_PASSWORD="${EXTERNAL_SUPABASE_PASSWORD:-}"

        if [ -z "$LOCAL_HOST" ] || [ -z "$LOCAL_USER" ] || [ -z "$LOCAL_PASSWORD" ]; then
            log_error "Missing required environment variables."
            log_error "Either set EXTERNAL_SUPABASE_DB_URL or set all of:"
            log_error "  - EXTERNAL_SUPABASE_HOST"
            log_error "  - EXTERNAL_SUPABASE_USER"
            log_error "  - EXTERNAL_SUPABASE_PASSWORD"
            log_error ""
            log_error "Example:"
            log_error "  export EXTERNAL_SUPABASE_HOST=db.xyz.supabase.co"
            log_error "  export EXTERNAL_SUPABASE_USER=postgres"
            log_error "  export EXTERNAL_SUPABASE_PASSWORD=your_password"
            log_error "  export EXTERNAL_SUPABASE_DB=postgres"
            exit 1
        fi

        # Build PostgreSQL connection URL
        EXTERNAL_SUPABASE_DB_URL="postgresql://${LOCAL_USER}:${LOCAL_PASSWORD}@${LOCAL_HOST}:${LOCAL_PORT}/${LOCAL_DB}"
    fi

    log_success "Environment validation passed"
}

validate_pg_dump() {
    log_info "Checking for pg_dump command..."

    if ! command -v pg_dump &> /dev/null; then
        log_error "pg_dump not found. Please install PostgreSQL client tools:"
        log_error "  Ubuntu/Debian: sudo apt-get install postgresql-client"
        log_error "  macOS: brew install postgresql"
        log_error "  Or use the Docker container: docker exec -it cortexreview-supabase-db pg_dump ..."
        exit 1
    fi

    local pg_dump_version=$(pg_dump --version | head -n1)
    log_success "Found: $pg_dump_version"
}

validate_connectivity() {
    log_info "Testing connectivity to external Supabase..."

    if ! psql "$EXTERNAL_SUPABASE_DB_URL" -c "SELECT 1;" &> /dev/null; then
        log_error "Cannot connect to external Supabase at:"
        log_error "  $EXTERNAL_SUPABASE_DB_URL"
        log_error ""
        log_error "Please check:"
        log_error "  1. Network connectivity"
        log_error "  2. Host and port are correct"
        log_error "  3. Credentials are valid"
        log_error "  4. Database exists"
        exit 1
    fi

    log_success "Connectivity test passed"
}

validate_export_dir() {
    log_info "Validating export directory..."

    if [ ! -d "$EXPORT_DIR" ]; then
        log_info "Creating export directory: $EXPORT_DIR"
        mkdir -p "$EXPORT_DIR"
    fi

    if [ ! -w "$EXPORT_DIR" ]; then
        log_error "Export directory is not writable: $EXPORT_DIR"
        exit 1
    fi

    log_success "Export directory ready: $EXPORT_DIR"
}

################################################################################
# Export Functions
################################################################################

get_table_counts() {
    log_info "Counting rows in tables to export..."

    echo ""
    echo "Table Row Counts:"
    echo "------------------"

    for table in "${TABLES[@]}"; do
        local count=$(psql "$EXTERNAL_SUPABASE_DB_URL" -t -c \
            "SELECT COUNT(*) FROM public.${table};" 2>/dev/null | xargs || echo "0")
        printf "  %-25s %10s rows\n" "$table:" "$count"
    done

    echo ""
}

export_tables() {
    log_info "Starting export of Supabase tables..."
    log_info "Export file: $EXPORT_FILE"

    # Build pg_dump command with vector column preservation
    local pg_dump_cmd="pg_dump \"$EXTERNAL_SUPABASE_DB_URL\" \
        --format=plain \
        --no-owner \
        --no-acl \
        --table=public.knowledge_base \
        --table=public.learned_constraints \
        --table=public.feedback_audit_log \
        --table=public.schema_migrations"

    # Execute export with compression
    log_info "Running pg_dump (this may take several minutes for large datasets)..."

    if eval "$pg_dump_cmd" | gzip > "$EXPORT_FILE"; then
        local file_size=$(du -h "$EXPORT_FILE" | cut -f1)
        log_success "Export completed successfully!"
        log_success "Export file: $EXPORT_FILE"
        log_success "File size: $file_size"
    else
        log_error "Export failed!"
        log_error "Partial export may exist at: $EXPORT_FILE"
        exit 1
    fi
}

verify_export() {
    log_info "Verifying export integrity..."

    # Check if file exists and is not empty
    if [ ! -s "$EXPORT_FILE" ]; then
        log_error "Export file is empty or missing: $EXPORT_FILE"
        exit 1
    fi

    # Decompress and check for expected SQL statements
    local sql_checks=(
        "COPY public.knowledge_base"
        "COPY public.learned_constraints"
        "COPY public.feedback_audit_log"
        "vector("
    )

    log_info "Validating SQL structure in export file..."

    for check in "${sql_checks[@]}"; do
        if ! gunzip -c "$EXPORT_FILE" | grep -q "$check"; then
            log_warning "Expected SQL pattern not found: $check"
        fi
    done

    # Count exported rows in the dump file
    log_info "Counting exported rows in dump file..."

    for table in "${TABLES[@]}"; do
        # Count COPY statements for this table
        local rows=$(gunzip -c "$EXPORT_FILE" | grep -c "^COPY public.${table}" || echo "0")
        if [ "$rows" -gt 0 ]; then
            log_success "  $table: Exported"
        else
            log_warning "  $table: No data exported (table may be empty)"
        fi
    done

    log_success "Export verification completed"
}

generate_manifest() {
    local manifest_file="${EXPORT_DIR}/export_manifest_${TIMESTAMP}.txt"

    log_info "Generating export manifest..."

    cat > "$manifest_file" << EOF
Supabase Export Manifest
========================
Generated: $(date -Iseconds)
Export File: $(basename "$EXPORT_FILE")

Source Information:
-------------------
Connection: $(echo "$EXTERNAL_SUPABASE_DB_URL" | sed 's/:[^:@]*@/:****@/')

Table Information:
------------------
EOF

    # Add table counts
    for table in "${TABLES[@]}"; do
        local count=$(psql "$EXTERNAL_SUPABASE_DB_URL" -t -c \
            "SELECT COUNT(*) FROM public.${table};" 2>/dev/null | xargs || echo "0")
        echo "  $table: $count rows" >> "$manifest_file"
    done

    cat >> "$manifest_file" << EOF

Export File Information:
-----------------------
Size: $(du -h "$EXPORT_FILE" | cut -f1)
Compressed: Yes (gzip)
Format: Plain SQL (PostgreSQL pg_dump)

Vector Columns:
---------------
- knowledge_base.embedding (vector(1536))
- learned_constraints.embedding (vector(1536))

Next Steps:
-----------
1. Transfer export file to target server
2. Run: ./scripts/import_to_local.sh "$EXPORT_FILE"
3. Verify migration: ./scripts/verify_migration.sh

EOF

    log_success "Manifest created: $manifest_file"
}

################################################################################
# Main Execution
################################################################################

main() {
    echo ""
    echo "========================================"
    echo "  Supabase External Export Script"
    echo "========================================"
    echo ""

    # Validate prerequisites
    validate_environment
    validate_pg_dump
    validate_export_dir
    validate_connectivity

    # Show current data
    get_table_counts

    # Confirm export
    echo ""
    read -p "Continue with export? [y/N] " -n 1 -r
    echo ""

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_warning "Export cancelled by user"
        exit 0
    fi

    # Perform export
    export_tables
    verify_export
    generate_manifest

    # Summary
    echo ""
    echo "========================================"
    log_success "Export completed successfully!"
    echo "========================================"
    echo ""
    echo "Export file: $EXPORT_FILE"
    echo ""
    echo "To transfer to another server:"
    echo "  scp $EXPORT_FILE user@target-server:/path/to/backups/"
    echo ""
    echo "To import on local Supabase:"
    echo "  ./scripts/import_to_local.sh $EXPORT_FILE"
    echo ""
}

# Run main function
main "$@"
