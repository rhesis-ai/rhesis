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
    [ "${ENVIRONMENT}" = "production" ] || [ "${FRONTEND_ENV}" = "production" ]
}

# Function to check if we're in staging mode
is_staging() {
    [ "${ENVIRONMENT}" = "staging" ] || [ "${FRONTEND_ENV}" = "staging" ]
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
    echo -e "${WHITE}🌐 Starting Rhesis Frontend Server${NC}"
    echo -e "${PURPLE}════════════════════════════════════════════════${NC}"
    echo ""
}

# Function to start the server
start_server() {
    local port="${PORT:-3000}"
    local host="${HOST:-0.0.0.0}"
    
    log "${BLUE}📋 Server Configuration:${NC}"
    log "  Host: $host"
    log "  Port: $port"
    log "  Environment: $(is_production && echo "production" || (is_staging && echo "staging" || echo "development"))"
    echo ""
    
    if is_production || is_staging; then
        log "${BLUE}🏭 Starting production server...${NC}"
        log "${BLUE}🔨 Building Next.js application...${NC}"
        
        # Build the application first
        if NODE_ENV=production npm run build; then
            log "${GREEN}✅ Build completed successfully${NC}"
        else
            handle_error "Build failed"
        fi
        
        echo ""
        log "${BLUE}▶️  Launching production server...${NC}"
        echo ""
        
        # Start the production server
        exec NODE_ENV=production npm run start -- --hostname 0.0.0.0
    else
        log "${BLUE}🛠️  Starting development server...${NC}"
        log "${YELLOW}📦 Framework:${NC} ${GREEN}Next.js${NC}"
        log "${YELLOW}🔧 Command:${NC} ${GREEN}npm run dev --host${NC}"
        log "${YELLOW}🔄 Hot Reload:${NC} ${GREEN}enabled${NC}"
        log "${YELLOW}🎨 Turbo Mode:${NC} ${GREEN}active${NC}"
        echo ""
        
        log "${BLUE}▶️  Launching development server...${NC}"
        echo ""
        
        # Start the development server
        exec npm run dev --host
    fi
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
    
    # Start the server
    start_server
}

# Execute main function
main "$@"
