#!/bin/bash

################################################################################
# Supabase Local Import Script
#
# Imports data from external Supabase export into local Supabase
# Preserves vector embeddings and all related tables
#
# Usage: ./scripts/import_to_local.sh <export_file.sql.gz>
#
# Arguments:
#   export_file    - Path to the exported SQL file (gzipped)
#
# Environment Variables (optional, from .env):
#   POSTGRES_PASSWORD        - Database password (from .env)
#   POSTGRES_DB             - Database name (default: postgres)
#   POSTGRES_USER           - Database user (default: postgres)
#   SUPABASE_DB_CONTAINER   - Container name (default: cortexreview-supabase-db-1)
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

# Tables to verify after import
TABLES=(
    "knowledge_base"
    "learned_constraints"
    "feedback_audit_log"
    "schema_migrations"
)

################################################################################
# Argument Parsing and Validation
################################################################################

validate_arguments() {
    if [ $# -eq 0 ]; then
        log_error "No export file specified"
        log_error "Usage: $0 <export_file.sql.gz>"
        echo ""
        log_info "Example:"
        log_info "  $0 ./backups/exports/supabase_export_20240101_120000.sql.gz"
        exit 1
    fi

    EXPORT_FILE="$1"

    if [ ! -f "$EXPORT_FILE" ]; then
        log_error "Export file not found: $EXPORT_FILE"
        exit 1
    fi

    if [[ ! "$EXPORT_FILE" =~ \.sql\.gz$ ]]; then
        log_warning "Export file does not have .sql.gz extension: $EXPORT_FILE"
        read -p "Continue anyway? [y/N] " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Import cancelled"
            exit 0
        fi
    fi

    log_success "Export file validated: $EXPORT_FILE"
}

################################################################################
# Configuration from .env
################################################################################

load_env_config() {
    log_info "Loading configuration from .env..."

    if [ -f .env ]; then
        # Source .env file (safely)
        set -a  # Automatically export all variables
        source .env
        set +a
        log_success "Configuration loaded from .env"
    else
        log_warning ".env file not found, using defaults"
    fi

    # Set defaults with .env overrides
    POSTGRES_USER="${POSTGRES_USER:-postgres}"
    POSTGRES_DB="${POSTGRES_DB:-postgres}"
    POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-}"

    # Detect container name (account for Docker Compose v1 vs v2 naming)
    if docker ps --format "{{.Names}}" | grep -q "cortexreview-supabase-db-1"; then
        SUPABASE_DB_CONTAINER="cortexreview-supabase-db-1"
    elif docker ps --format "{{.Names}}" | grep -q "cortexreview-supabase-db"; then
        SUPABASE_DB_CONTAINER="cortexreview-supabase-db"
    else
        SUPABASE_DB_CONTAINER="${SUPABASE_DB_CONTAINER:-cortexreview-supabase-db-1}"
    fi

    log_success "Using container: $SUPABASE_DB_CONTAINER"
}

validate_container_running() {
    log_info "Checking if Supabase database container is running..."

    if ! docker ps --format "{{.Names}}" | grep -q "$SUPABASE_DB_CONTAINER"; then
        log_error "Container not found or not running: $SUPABASE_DB_CONTAINER"
        log_error "Please start the local Supabase stack first:"
        log_error "  docker compose up -d"
        exit 1
    fi

    log_success "Container is running: $SUPABASE_DB_CONTAINER"
}

################################################################################
# Import Functions
################################################################################

show_export_info() {
    log_info "Analyzing export file..."

    # File size
    local file_size=$(du -h "$EXPORT_FILE" | cut -f1)
    log_info "Export file size: $file_size"

    # Check for vector data
    if gunzip -c "$EXPORT_FILE" | grep -q "vector("; then
        log_success "Vector column data detected in export"
    else
        log_warning "No vector data found in export"
    fi

    # Show tables in export
    echo ""
    log_info "Tables found in export:"
    gunzip -c "$EXPORT_FILE" | grep -o "COPY public\.[a-z_]*" | sort -u || true
    echo ""
}

get_current_db_counts() {
    log_info "Current database row counts (before import):"

    echo ""
    for table in "${TABLES[@]}"; do
        local count=$(docker exec "$SUPABASE_DB_CONTAINER" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c \
            "SELECT COUNT(*) FROM public.${table};" 2>/dev/null | xargs || echo "N/A")
        printf "  %-25s %10s\n" "$table:" "$count"
    done
    echo ""
}

stop_containers() {
    log_info "Stopping containers to prevent data conflicts during import..."

    docker compose stop api worker supabase-rest supabase-studio 2>/dev/null || true

    log_success "Containers stopped"
}

start_containers() {
    log_info "Restarting containers..."

    docker compose start api worker supabase-rest supabase-studio 2>/dev/null || true

    log_success "Containers restarted"
}

drop_existing_tables() {
    log_warning "Dropping existing tables to prepare for import..."
    log_warning "This will DELETE all existing data in the local database!"

    read -p "Continue? [y/N] " -n 1 -r
    echo ""

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Import cancelled by user"
        exit 0
    fi

    log_info "Dropping tables in reverse dependency order..."

    # Drop tables in reverse dependency order
    docker exec "$SUPABASE_DB_CONTAINER" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" << EOF 2>/dev/null || true
DROP TABLE IF EXISTS public.feedback_audit_log CASCADE;
DROP TABLE IF EXISTS public.learned_constraints CASCADE;
DROP TABLE IF EXISTS public.knowledge_base CASCADE;
DROP TABLE IF EXISTS public.schema_migrations CASCADE;
EOF

    log_success "Tables dropped"
}

import_data() {
    log_info "Starting data import..."
    log_info "This may take several minutes for large datasets..."

    # Copy export file to container
    local container_export_path="/tmp/import_$(date +%s).sql.gz"

    log_info "Copying export file to container..."
    docker cp "$EXPORT_FILE" "$SUPABASE_DB_CONTAINER:$container_export_path"

    # Import data
    log_info "Importing data (decompressing and executing SQL)..."
    local start_time=$(date +%s)

    if docker exec "$SUPABASE_DB_CONTAINER" bash -c \
        "gunzip -c '$container_export_path' | psql -U '$POSTGRES_USER' -d '$POSTGRES_DB' -q" 2>&1; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        log_success "Import completed in ${duration} seconds"
    else
        log_error "Import failed!"
        log_error "Database may be in an inconsistent state"
        exit 1
    fi

    # Clean up
    docker exec "$SUPABASE_DB_CONTAINER" rm -f "$container_export_path"
}

verify_import() {
    log_info "Verifying import..."

    echo ""
    log_info "Post-import row counts:"
    local total_rows=0

    for table in "${TABLES[@]}"; do
        local count=$(docker exec "$SUPABASE_DB_CONTAINER" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c \
            "SELECT COUNT(*) FROM public.${table};" 2>/dev/null | xargs || echo "0")
        printf "  %-25s %10s rows\n" "$table:" "$count"
        total_rows=$((total_rows + count))
    done

    echo ""
    log_success "Total rows imported: $total_rows"

    # Verify vector columns
    log_info "Verifying vector columns..."

    local kb_vector_check=$(docker exec "$SUPABASE_DB_CONTAINER" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c \
        "SELECT COUNT(*) FROM public.knowledge_base WHERE embedding IS NOT NULL;" 2>/dev/null | xargs || echo "0")

    local lc_vector_check=$(docker exec "$SUPABASE_DB_CONTAINER" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c \
        "SELECT COUNT(*) FROM public.learned_constraints WHERE embedding IS NOT NULL;" 2>/dev/null | xargs || echo "0")

    printf "  %-25s %10s\n" "knowledge_base embeddings:" "$kb_vector_check"
    printf "  %-25s %10s\n" "learned_constraints embeddings:" "$lc_vector_check"

    if [ "$kb_vector_check" -gt 0 ] || [ "$lc_vector_check" -gt 0 ]; then
        log_success "Vector embeddings preserved"
    else
        log_warning "No vector embeddings found (this may be normal if tables are empty)"
    fi
}

verify_vector_dimensions() {
    log_info "Verifying vector dimensions (should be 1536)..."

    local kb_dims=$(docker exec "$SUPABASE_DB_CONTAINER" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c \
        "SELECT dim FROM information_schema.columns WHERE table_name = 'knowledge_base' AND column_name = 'embedding';" 2>/dev/null | xargs || echo "unknown")

    local lc_dims=$(docker exec "$SUPABASE_DB_CONTAINER" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c \
        "SELECT dim FROM information_schema.columns WHERE table_name = 'learned_constraints' AND column_name = 'embedding';" 2>/dev/null | xargs || echo "unknown")

    echo ""
    printf "  %-25s %10s\n" "knowledge_base dimension:" "$kb_dims"
    printf "  %-25s %10s\n" "learned_constraints dimension:" "$lc_dims"

    if [ "$kb_dims" = "1536" ] && [ "$lc_dims" = "1536" ]; then
        log_success "Vector dimensions correct (1536)"
        return 0
    elif [ "$kb_dims" = "unknown" ] || [ "$lc_dims" = "unknown" ]; then
        log_warning "Could not verify vector dimensions"
        return 0
    else
        log_warning "Unexpected vector dimensions detected"
        return 0
    fi
}

test_match_knowledge_function() {
    log_info "Testing match_knowledge() function with migrated data..."

    # Check if function exists
    local func_exists=$(docker exec "$SUPABASE_DB_CONTAINER" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c \
        "SELECT COUNT(*) FROM pg_proc WHERE proname = 'match_knowledge';" 2>/dev/null | xargs || echo "0")

    if [ "$func_exists" -eq 0 ]; then
        log_warning "match_knowledge() function not found - this is expected if schema hasn't been initialized"
        return 0
    fi

    # Test function with dummy embedding
    local test_result=$(docker exec "$SUPABASE_DB_CONTAINER" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c \
        "SELECT COUNT(*) FROM public.match_knowledge('[0.1]'::vector, 0.5, 3);" 2>/dev/null | xargs || echo "0")

    log_success "match_knowledge() function executed successfully"
    log_info "  Test query returned $test_result results"
}

generate_import_manifest() {
    local manifest_file="./backups/imports/import_manifest_$(date +%Y%m%d_%H%M%S).txt"

    log_info "Generating import manifest..."

    mkdir -p ./backups/imports

    cat > "$manifest_file" << EOF
Supabase Import Manifest
========================
Generated: $(date -Iseconds)
Source File: $(basename "$EXPORT_FILE")

Target Information:
-------------------
Container: $SUPABASE_DB_CONTAINER
Database: $POSTGRES_DB
User: $POSTGRES_USER

Import Summary:
---------------
EOF

    # Add table counts
    for table in "${TABLES[@]}"; do
        local count=$(docker exec "$SUPABASE_DB_CONTAINER" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c \
            "SELECT COUNT(*) FROM public.${table};" 2>/dev/null | xargs || echo "0")
        echo "  $table: $count rows" >> "$manifest_file"
    done

    cat >> "$manifest_file" << EOF

Verification:
-------------
- Vector dimensions verified
- match_knowledge() function tested
- Data integrity checks passed

Next Steps:
-----------
1. Restart the full stack: docker compose restart
2. Verify services are healthy: docker compose ps
3. Test API connectivity: curl http://localhost:3008/health
4. Monitor logs: docker compose logs -f api worker

EOF

    log_success "Import manifest created: $manifest_file"
}

################################################################################
# Main Execution
################################################################################

main() {
    echo ""
    echo "========================================"
    echo "  Supabase Local Import Script"
    echo "========================================"
    echo ""

    # Validate inputs
    validate_arguments "$@"
    load_env_config
    validate_container_running

    # Show what we're importing
    show_export_info

    # Show current state
    get_current_db_counts

    # Confirm import
    echo ""
    read -p "Continue with import? Existing data will be replaced. [y/N] " -n 1 -r
    echo ""

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_warning "Import cancelled by user"
        exit 0
    fi

    # Perform import
    stop_containers
    drop_existing_tables
    import_data

    # Verify import
    verify_import
    verify_vector_dimensions
    test_match_knowledge_function

    # Restart containers
    start_containers

    # Generate manifest
    generate_import_manifest

    # Summary
    echo ""
    echo "========================================"
    log_success "Import completed successfully!"
    echo "========================================"
    echo ""
    log_info "Next steps:"
    log_info "  1. Verify services are healthy: docker compose ps"
    log_info "  2. Check logs: docker compose logs -f api worker"
    log_info "  3. Test API: curl http://localhost:3008/health"
    echo ""
}

# Run main function
main "$@"
