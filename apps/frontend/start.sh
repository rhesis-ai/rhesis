#!/bin/bash

# Local development entrypoint only.
# Production and staging use apps/frontend/Dockerfile (node apps/frontend/server.js).
# Invoked via: ./rh dev frontend  or  cd apps/frontend && ./start.sh

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
    echo -e "${WHITE}🌐 Starting Rhesis Frontend (development)${NC}"
    echo -e "${PURPLE}════════════════════════════════════════════════${NC}"
    echo ""
}

# Function to ensure dependencies are installed
ensure_dependencies() {
    if [ ! -d "node_modules" ]; then
        log "${YELLOW}📦 node_modules not found, installing dependencies...${NC}"
        if npm install; then
            log "${GREEN}✅ Dependencies installed successfully${NC}"
        else
            handle_error "Failed to install dependencies"
        fi
        echo ""
    fi
}

# Function to start the development server
start_server() {
    local port="${PORT:-3000}"

    log "${BLUE}📋 Server Configuration:${NC}"
    log "  Host: 0.0.0.0 (from npm run dev:turbo)"
    log "  Port: $port"
    log "  Environment: development"
    echo ""

    log "${BLUE}🛠️  Starting development server...${NC}"
    log "${YELLOW}📦 Framework:${NC} ${GREEN}Next.js${NC}"
    log "${YELLOW}🔧 Command:${NC} ${GREEN}npm run dev:turbo${NC}"
    log "${YELLOW}🔄 Hot Reload:${NC} ${GREEN}enabled${NC}"
    log "${YELLOW}🎨 Turbo Mode:${NC} ${GREEN}active${NC}"
    echo ""

    log "${BLUE}▶️  Launching development server...${NC}"
    echo ""

    NODE_ENV=development exec npm run dev:turbo
}

# Function to handle shutdown gracefully
cleanup() {
    log "${YELLOW}🛑 Received shutdown signal, cleaning up...${NC}"
    # Kill any background processes
    jobs -p | xargs -r kill 2>/dev/null
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
    log "${BLUE}🚀 Starting Rhesis Frontend startup sequence...${NC}"
    log "${BLUE}📅 Startup time: $(date)${NC}"
    log "${BLUE}👤 Running as user: $(whoami)${NC}"
    log "${BLUE}📁 Working directory: $(pwd)${NC}"
    echo ""

    # Ensure dependencies are installed
    ensure_dependencies

    # Start the server
    start_server
}

# Execute main function
main "$@"
