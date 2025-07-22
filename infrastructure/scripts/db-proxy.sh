#!/bin/bash

# Define color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

SOCKET_FILE="/cloudsql/playground-437609:us-central1/nocodb-db/.s.PGSQL.5432"
INSTANCE_CONNECTION_NAME="playground-437609:us-central1:nocodb-db"

# Find and kill any existing Cloud SQL Proxy processes
EXISTING_PID=$(pgrep -f "cloud-sql-proxy")
if [ -n "$EXISTING_PID" ]; then
    echo -e "${RED}🛑 Stopping existing Cloud SQL Proxy process: $EXISTING_PID${NC}"
    kill "$EXISTING_PID"
    sleep 2  # Give it time to stop
fi

# Clean up all connections under /cloudsql
echo -e "${PURPLE}🧹 Cleaning up /cloudsql directory...${NC}"
if [ -d "/cloudsql" ]; then
    rm -rf /cloudsql/*
    sleep 1  # Give the system a moment to release the files
fi

# Ensure the directory exists
echo -e "${CYAN}📁 Creating directory structure...${NC}"
mkdir -p "$(dirname "$SOCKET_FILE")"

# Double-check if the socket file still exists, then remove it
if [ -e "$SOCKET_FILE" ]; then
    echo -e "${PURPLE}🧹 Removing stale socket file...${NC}"
    rm -f "$SOCKET_FILE"
    sleep 1  # Give the system a moment to release the file
fi

# Start Cloud SQL Proxy
echo -e "${GREEN}🚀 Starting Cloud SQL Proxy...${NC}"
./cloud-sql-proxy --credentials-file ./sql-proxy-key.json --unix-socket=/cloudsql "$INSTANCE_CONNECTION_NAME"


echo -e "${YELLOW}💫 Done!${NC}"
