#!/bin/bash

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to log with timestamp
log() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Function to handle errors
handle_error() {
    log "${RED}❌ Migration failed: $1${NC}"
    exit 1
}

# Function to wait for database
wait_for_database() {
    local max_attempts=30
    local attempt=1
    
    log "${YELLOW}⏳ Waiting for PostgreSQL to be ready (max ${max_attempts} attempts)...${NC}"
    
    while [ $attempt -le $max_attempts ]; do
        if pg_isready -h "$DB_HOST" -p 5432 -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; then
            log "${GREEN}✅ PostgreSQL is ready! (attempt $attempt)${NC}"
            return 0
        fi
        
        log "PostgreSQL not ready yet. Attempt $attempt/$max_attempts. Waiting 2 seconds..."
        sleep 2
        ((attempt++))
    done
    
    handle_error "PostgreSQL did not become ready after $max_attempts attempts"
}

# Function to run migrations
#
# We use `psql` (not `alembic current`) to read the revision before and after
# the upgrade. Each `alembic` invocation costs ~5-6s of Python cold-start +
# SDK/model imports inside the Cloud Run Job, so two diagnostic calls used to
# add ~10-12s. A `psql` query on `alembic_version` returns in <100 ms and gives
# us the same information. Verbose Alembic diagnostics still run, but only on
# failure, where the extra latency does not matter.
run_migrations() {
    cd /app/src/rhesis/backend || handle_error "Could not navigate to backend directory"

    local before after
    before=$(PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" \
        -tAc "SELECT version_num FROM alembic_version;" 2>/dev/null | tr -d '[:space:]' || echo "")

    log "${YELLOW}📦 Running migrations (from: ${before:-'fresh DB'})...${NC}"

    if ! alembic upgrade head; then
        log "${RED}❌ alembic upgrade head failed — gathering diagnostics:${NC}"
        alembic current || true
        alembic history --verbose | tail -30 || true
        handle_error "alembic upgrade head command failed"
    fi

    after=$(PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" \
        -tAc "SELECT version_num FROM alembic_version;" 2>/dev/null | tr -d '[:space:]' || echo "")

    if [ "$before" = "$after" ]; then
        log "${GREEN}ℹ️  Already at head: ${after:-'(unknown)'} (no migrations applied)${NC}"
    else
        log "${GREEN}✅ Migrations applied: ${before:-'(none)'} → ${after}${NC}"
    fi
}

# Main execution
main() {
    log "${BLUE}🔄 Starting database migration process...${NC}"
    
    # Get database configuration from environment variables
    DB_USER=${SQLALCHEMY_DB_USER:-rhesis-user}
    DB_PASS=${SQLALCHEMY_DB_PASS:-your-secured-password}
    DB_HOST=${SQLALCHEMY_DB_HOST:-postgres}
    DB_NAME=${SQLALCHEMY_DB_NAME:-rhesis-db}
    
    # Validate required environment variables
    if [ -z "$DB_USER" ] || [ -z "$DB_PASS" ] || [ -z "$DB_HOST" ] || [ -z "$DB_NAME" ]; then
        handle_error "Required database environment variables are not set"
    fi
    
    log "${BLUE}📋 Database Configuration:${NC}"
    log "  Host: $DB_HOST"
    log "  User: $DB_USER"
    log "  Database: $DB_NAME"
    
    # Set environment variables for Alembic
    export SQLALCHEMY_DB_DRIVER=${SQLALCHEMY_DB_DRIVER:-postgresql}
    export SQLALCHEMY_DB_USER="$DB_USER"
    export SQLALCHEMY_DB_PASS="$DB_PASS"
    export SQLALCHEMY_DB_HOST="$DB_HOST"
    export SQLALCHEMY_DB_NAME="$DB_NAME"
    
    # Wait for database to be ready
    wait_for_database
    
    # Set database ownership (optional, ignore failures)
    log "${YELLOW}🔧 Setting database ownership...${NC}"
    if PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "ALTER DATABASE $DB_NAME OWNER TO $DB_USER;" 2>/dev/null; then
        log "${GREEN}✅ Database ownership set successfully${NC}"
    else
        log "${YELLOW}⚠️  Database ownership already set or could not be changed${NC}"
    fi
    
    # Run migrations
    run_migrations
    
    log "${GREEN}🎉 Database migration process complete!${NC}"
}

# Execute main function
main "$@" 