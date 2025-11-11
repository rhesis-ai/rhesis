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
    
    # Check for migrate.sh in the same directory as start.sh
    if [ -f "./migrate.sh" ]; then
        log "${BLUE}📍 Found migration script at: $(pwd)/migrate.sh${NC}"
        
        # Run migrations
        if ./migrate.sh; then
            log "${GREEN}✅ Database migrations completed successfully${NC}"
        else
            handle_error "Database migrations failed"
        fi
    else
        log "${YELLOW}⚠️  Migration script not found at $(pwd)/migrate.sh, skipping migrations${NC}"
        log "${YELLOW}   Expected location: $(pwd)/migrate.sh${NC}"
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
    
    if is_production; then
        log "${BLUE}🏭 Starting production server with Gunicorn...${NC}"
        exec gunicorn \
            --workers "$workers" \
            --worker-class uvicorn.workers.UvicornWorker \
            --bind "$host:$port" \
            --timeout "$timeout" \
            --access-logfile - \
            --error-logfile - \
            --log-level info \
            rhesis.backend.app.main:app
    else
        log "${BLUE}🛠️  Starting development server with Uvicorn...${NC}"
        exec uv run uvicorn \
            rhesis.backend.app.main:app \
            --host "$host" \
            --port "$port" \
            --log-level debug \
            --reload
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