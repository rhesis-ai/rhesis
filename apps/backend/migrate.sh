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

is_local_env() {
    [ "${BACKEND_ENV:-}" = "local" ]
}

# In Docker, alembic is in .venv/bin (PATH). Locally, use `uv run alembic`.
run_alembic() {
    if command -v alembic &>/dev/null; then
        alembic "$@"
    elif command -v uv &>/dev/null; then
        uv run alembic "$@"
    else
        alembic "$@"
    fi
}

# Function to wait for database
wait_for_database() {
    local max_attempts=30
    local attempt=1
    
    log "${YELLOW}⏳ Waiting for PostgreSQL to be ready (max ${max_attempts} attempts)...${NC}"
    
    while [ $attempt -le $max_attempts ]; do
        if pg_isready -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$ADMIN_USER" -d "$DB_NAME" >/dev/null 2>&1; then
            log "${GREEN}✅ PostgreSQL is ready! (attempt $attempt)${NC}"
            return 0
        fi
        
        log "PostgreSQL not ready yet. Attempt $attempt/$max_attempts. Waiting 2 seconds..."
        sleep 2
        ((attempt++))
    done
    
    handle_error "PostgreSQL did not become ready after $max_attempts attempts"
}

maybe_wait_for_database() {
    if is_local_env; then
        log "${BLUE}ℹ️  Skipping database wait (local environment)${NC}"
        return 0
    fi

    wait_for_database
}

# Function to run migrations
#
# Concurrent replicas are serialized by a Postgres advisory lock acquired in
# alembic's env.py (see MIGRATION_ADVISORY_LOCK_KEY there), so simultaneous
# Cloud Run Job instances wait for each other instead of racing through the
# upgrade. The wait is logged by Alembic; tune it with ALEMBIC_LOCK_TIMEOUT.
#
# We use `psql` (not `alembic current`) to read the revision before and after
# the upgrade. Each `alembic` invocation costs ~5-6s of Python cold-start +
# SDK/model imports inside the Cloud Run Job, so two diagnostic calls used to
# add ~10-12s. A `psql` query on `alembic_version` returns in <100 ms and gives
# us the same information. Verbose Alembic diagnostics still run, but only on
# failure, where the extra latency does not matter.
run_migrations() {
    local backend_root
    backend_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    cd "$backend_root/src/rhesis/backend" || handle_error "Could not navigate to backend directory"

    local before after
    before=$(PGPASSWORD="$ADMIN_PASS" psql -h "$DB_HOST" -U "$ADMIN_USER" -d "$DB_NAME" \
        -tAc "SELECT version_num FROM alembic_version;" 2>/dev/null | tr -d '[:space:]' || echo "")

    log "${YELLOW}📦 Running migrations (from: ${before:-'fresh DB'})...${NC}"

    if ! run_alembic upgrade head; then
        log "${RED}❌ alembic upgrade head failed — gathering diagnostics:${NC}"
        run_alembic current || true
        run_alembic history --verbose | tail -30 || true
        handle_error "alembic upgrade head command failed"
    fi

    after=$(PGPASSWORD="$ADMIN_PASS" psql -h "$DB_HOST" -U "$ADMIN_USER" -d "$DB_NAME" \
        -tAc "SELECT version_num FROM alembic_version;" 2>/dev/null | tr -d '[:space:]' || echo "")

    if [ "$before" = "$after" ]; then
        log "${GREEN}ℹ️  Already at head: ${after:-'(unknown)'} (no migrations applied)${NC}"
    else
        log "${GREEN}✅ Migrations applied: ${before:-'(none)'} → ${after}${NC}"
    fi
}

set_db_ownership() {
    if is_local_env; then
        log "${BLUE}ℹ️  Skipping database ownership (local environment)${NC}"
        return 0
    fi

    log "${YELLOW}🔧 Setting database ownership...${NC}"
    if PGPASSWORD="$ADMIN_PASS" psql -h "$DB_HOST" -U "$ADMIN_USER" -d "$DB_NAME" \
        -c "ALTER DATABASE \"$DB_NAME\" OWNER TO \"$ADMIN_USER\";" 2>/dev/null; then
        log "${GREEN}✅ Database ownership set successfully${NC}"
    else
        log "${YELLOW}⚠️  Database ownership already set or could not be changed${NC}"
    fi
}

# Create the app's runtime role when the app and migrations use different roles
# and it does not exist yet (docker-compose: ADMIN_DB_USER is the Postgres
# superuser). Runs before alembic so the default privileges cover new tables.
# A no-op where the role is provisioned elsewhere (CNPG, external databases).
ensure_app_role() {
    if [ -z "${ADMIN_DB_USER:-}" ] || [ -z "${APP_DB_USER:-}" ] || [ "$ADMIN_DB_USER" = "$APP_DB_USER" ]; then
        return 0
    fi

    local psql_admin=(psql -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$ADMIN_USER" -d "$DB_NAME")
    # A failed lookup only warns: alembic below uses the same credentials and
    # fails loudly if they are wrong, and stg/prd must not depend on this step.
    local exists
    if ! exists=$(echo "SELECT 1 FROM pg_roles WHERE rolname = :'app_user';" \
        | PGPASSWORD="$ADMIN_PASS" "${psql_admin[@]}" -tA -v app_user="$APP_DB_USER" 2>&1); then
        log "${YELLOW}⚠️  Could not look up database role $APP_DB_USER, skipping role setup: ${exists}${NC}"
        return 0
    fi
    if [ "$exists" = "1" ]; then
        log "${BLUE}ℹ️  App database role $APP_DB_USER exists${NC}"
        return 0
    fi

    log "${YELLOW}🔧 Creating app database role $APP_DB_USER...${NC}"
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PGPASSWORD="$ADMIN_PASS" "${psql_admin[@]}" -q --single-transaction -v ON_ERROR_STOP=1 \
        -v app_user="$APP_DB_USER" -v app_pass="$APP_DB_PASS" -v admin_user="$ADMIN_USER" \
        -f "$script_dir/src/rhesis/backend/alembic/create_app_role.sql" \
        || handle_error "Could not create database role $APP_DB_USER (ADMIN_DB_USER needs CREATEROLE)"
    log "${GREEN}✅ App database role $APP_DB_USER created${NC}"
}

# Main execution
main() {
    log "${BLUE}🔄 Starting database migration process...${NC}"

    ADMIN_USER="${ADMIN_DB_USER:-$APP_DB_USER}"
    ADMIN_PASS="${ADMIN_DB_PASS:-$APP_DB_PASS}"

    log "${BLUE}📋 Database Configuration:${NC}"
    log "  Host: $DB_HOST"
    log "  Port: ${DB_PORT:-5432}"
    log "  Admin user: $ADMIN_USER"
    log "  Database: $DB_NAME"
    
    # Wait for database to be ready (skipped in local — Postgres started separately)
    maybe_wait_for_database

    set_db_ownership

    ensure_app_role

    # Run migrations
    run_migrations
    
    log "${GREEN}🎉 Database migration process complete!${NC}"
}

# Execute main function
main "$@" 