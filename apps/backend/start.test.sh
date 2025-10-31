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

# Function to setup test data
setup_test_data() {
    log "${BLUE}🧪 Setting up test data...${NC}"

    # Set token value
    TOKEN_VALUE="rh-test-token"

    # Generate token hash
    log "${BLUE}Generating token hash...${NC}"
    TOKEN_HASH=$(python -c "from rhesis.backend.app.utils.encryption import hash_token; print(hash_token('${TOKEN_VALUE}'))")

    log "${BLUE}Token: $TOKEN_VALUE${NC}"
    log "${BLUE}Hash: $TOKEN_HASH${NC}"

    # Create organization, user, and token in database
    log "${BLUE}Creating organization, user, and token...${NC}"
    PGPASSWORD=your-secured-password psql -h postgres -U rhesis-user -d rhesis-db << SQL
-- Create organization and user
WITH new_org AS (
    INSERT INTO organization (name)
    VALUES ('test_organization')
    RETURNING id
),
new_user AS (
    INSERT INTO "user" (email, organization_id)
    SELECT 'test@example.com', id FROM new_org
    RETURNING id, organization_id
)
-- Create token
INSERT INTO token (
    token,
    token_hash,
    token_type,
    user_id
)
SELECT
    '${TOKEN_VALUE}',
    '${TOKEN_HASH}',
    'bearer',
    new_user.id
FROM new_user;
SQL

    if [ $? -ne 0 ]; then
        log "${RED}❌ Failed to setup test data${NC}"
        return 1
    fi

    # Display the token prominently
    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}✅ Test API Key Generated${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}${TOKEN_VALUE}${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════${NC}"
    echo ""

    log "${GREEN}✅ Test data setup completed${NC}"
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

    log "${BLUE}📋 Server Configuration:${NC}"
    log "  Host: $host"
    log "  Port: $port"
    echo ""

    log "${BLUE}🛠️  Starting development server with Uvicorn...${NC}"
    exec uv run uvicorn \
        rhesis.backend.app.main:app \
        --host "$host" \
        --port "$port" \
        --log-level debug \
        --reload
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
    if [ -n "${SQLALCHEMY_DB_HOST:-}" ]; then
        run_migrations
        # Setup test data after migrations
        log "${BLUE}🧪 Setting up test data...${NC}"
        setup_test_data
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
