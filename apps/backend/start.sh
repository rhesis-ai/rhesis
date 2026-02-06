#!/bin/bash

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# Function to log with timestamp
log() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Function to handle errors
handle_error() {
    log "${RED}❌ Startup failed: $1${NC}"
    exit 1
}

# Function to check if we're in production mode
is_production() {
    [ "${ENVIRONMENT}" = "production" ] || [ "${BACKEND_ENV}" = "production" ]
}

is_local() {
    [ "${ENVIRONMENT}" = "local" ] || [ "${BACKEND_ENV}" = "local" ]
}

is_development() {
    [ "${ENVIRONMENT}" = "development" ] || [ "${BACKEND_ENV}" = "development" ]
}

# Function to display banner
show_banner() {
    echo -e "${CYAN}"
    echo "  ____  _   _ _____ ____ ___ ____  "
    echo " |  _ \| | | | ____/ ___|_ _/ ___| "
    echo " | |_) | |_| |  _| \___ \| |\___ \ "
    echo " |  _ <|  _  | |___ ___) | | ___) |"
    echo " |_| \_\_| |_|_____|____/___|____/ "
    echo -e "${NC}"

    echo -e "${PURPLE}════════════════════════════════════════════════${NC}"
    echo -e "${WHITE}🚀 Starting Rhesis Backend Server${NC}"
    echo -e "${PURPLE}════════════════════════════════════════════════${NC}"
    echo ""
}

# Function to run database migrations
run_migrations() {
    log "${BLUE}🔄 Running database migrations...${NC}"

    # Determine command prefix (uv run for local, direct for Docker)
    local CMD_PREFIX=""
    if use_uv_run; then
        CMD_PREFIX="uv run "
    fi

    # Docker: use migrate.sh, Local: run alembic directly
    if [ -d "/app/src/rhesis/backend" ]; then
        # Docker environment - use migrate.sh
        log "${BLUE}📍 Running migrations via migrate.sh (Docker)${NC}"
        if ./migrate.sh; then
            log "${GREEN}✅ Database migrations completed successfully${NC}"
        else
            handle_error "Database migrations failed"
        fi
    else
        # Local environment - run alembic directly
        log "${BLUE}📍 Running migrations via alembic (local)${NC}"
        cd src/rhesis/backend || handle_error "Could not navigate to backend directory"
        
        if ${CMD_PREFIX}alembic upgrade head; then
            log "${GREEN}✅ Database migrations completed successfully${NC}"
        else
            handle_error "Database migrations failed"
        fi
        
        # Return to original directory
        cd - > /dev/null
    fi
}

# Function to load environment from .env file (local development only)
load_env_file() {
    # Skip if already in production (env vars set by Docker/K8s)
    if [ "${ENVIRONMENT}" = "production" ] || [ "${BACKEND_ENV}" = "production" ]; then
        log "${BLUE}📦 Production environment detected, using system env vars${NC}"
        return
    fi

    # Load .env file for local development
    if [ -f ".env" ]; then
        log "${BLUE}📁 Loading environment from .env file (local mode)...${NC}"
        # Export variables from .env file
        set -a
        source .env
        set +a
        log "${GREEN}✅ Environment loaded${NC}"
    fi
}

# Function to validate environment
validate_environment() {
    log "${BLUE}🔍 Validating environment...${NC}"

    BACKEND_SRC="src/rhesis/backend"
    # Check if the main application exists
    if [ ! -f "$BACKEND_SRC/app/main.py" ]; then
        handle_error "Main application file not found"
    fi

    log "${GREEN}✅ Environment validation passed${NC}"
}

# Function to check if we need to use 'uv run' or direct execution
# In Docker, dependencies are in .venv/bin which is in PATH
# Locally (via rh CLI), we use 'uv run' to manage the environment
use_uv_run() {
    # If uvicorn is directly in PATH (Docker), don't use uv run
    # If uv is available but uvicorn isn't in PATH (local), use uv run
    if command -v uvicorn &> /dev/null; then
        return 1  # Don't use uv run
    elif command -v uv &> /dev/null; then
        return 0  # Use uv run
    else
        return 1  # Fallback to direct execution
    fi
}

# Function to start the server
start_server() {
    local host="${HOST:-0.0.0.0}"
    local port="${PORT:-8080}"
    local workers="${WORKERS:-4}"
    local timeout="${TIMEOUT:-60}"

    log "${BLUE}📋 Server Configuration:${NC}"
    log "  Host: $host"
    log "  Port: $port"
    log "  Workers: $workers"
    log "  Timeout: ${timeout}s"
    log "  Environment: $(is_production && echo "production" || echo "development")"
    echo ""

    # Determine command prefix
    local CMD_PREFIX=""
    if use_uv_run; then
        CMD_PREFIX="uv run "
        log "${BLUE}🔧 Using 'uv run' for local execution${NC}"
    else
        log "${BLUE}🐳 Using direct execution (Docker/venv in PATH)${NC}"
    fi

    if is_production; then
        log "${BLUE}🏭 Starting production server with Gunicorn...${NC}"
        exec ${CMD_PREFIX}gunicorn \
            --workers "$workers" \
            --worker-class uvicorn.workers.UvicornWorker \
            --bind "$host:$port" \
            --timeout "$timeout" \
            --access-logfile - \
            --error-logfile - \
            --log-level info \
            rhesis.backend.app.main:app
    elif is_local; then
        log "${BLUE}🛠️  Starting local production server with Uvicorn...${NC}"
        exec ${CMD_PREFIX}uvicorn \
            rhesis.backend.app.main:app \
            --host "$host" \
            --port "$port"
    elif is_development; then
        log "${BLUE}🛠️  Starting development server with Uvicorn (hot reload)...${NC}"
        exec ${CMD_PREFIX}uvicorn \
            rhesis.backend.app.main:app \
            --host "$host" \
            --port "$port" \
            --log-level debug \
            --reload
    else
        # Default: no ENVIRONMENT/BACKEND_ENV (e.g. docker-compose for integration tests)
        log "${BLUE}🛠️  Starting server with Uvicorn (default)...${NC}"
        exec ${CMD_PREFIX}uvicorn \
            rhesis.backend.app.main:app \
            --host "$host" \
            --port "$port" \
            --log-level debug
    fi
}

# Function to handle shutdown gracefully
cleanup() {
    log "${YELLOW}🛑 Received shutdown signal, cleaning up...${NC}"
    # Kill any background processes
    jobs -p | xargs -r kill
    log "${GREEN}✅ Cleanup completed${NC}"
    exit 0
}

# Main execution
main() {
    # Set up signal handlers
    trap cleanup SIGTERM SIGINT

    # Show banner
    show_banner

    # Log startup information
    log "${BLUE}🚀 Starting Rhesis Backend startup sequence...${NC}"
    log "${BLUE}📅 Startup time: $(date)${NC}"
    log "${BLUE}👤 Running as user: $(whoami)${NC}"
    log "${BLUE}📁 Working directory: $(pwd)${NC}"

    # Load environment from .env file if in local mode
    load_env_file

    # Validate environment
    validate_environment

    # Run database migrations (only if database is configured and not skipped)
    if [ "${SKIP_MIGRATIONS:-false}" = "true" ]; then
        log "${YELLOW}⚠️  SKIP_MIGRATIONS is set, skipping migrations (handled by deployment pipeline)${NC}"
    elif [ -n "${SQLALCHEMY_DB_HOST:-}" ]; then
        run_migrations
    else
        log "${YELLOW}⚠️  No database configuration found, skipping migrations${NC}"
    fi

    # Start the server
    log "${BLUE}▶️  Launching server...${NC}"
    echo ""
    start_server
}

# Execute main function
main "$@"
