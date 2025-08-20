#!/bin/bash

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔄 Starting database migration...${NC}"

# Get database configuration from environment variables
DB_USER=${SQLALCHEMY_DB_USER:-rhesis-user}
DB_PASS=${SQLALCHEMY_DB_PASS:-rhesis-password}
DB_HOST=${SQLALCHEMY_DB_HOST:-postgres}
DB_NAME=${SQLALCHEMY_DB_NAME:-rhesis-db}

# Wait for PostgreSQL to be ready
echo -e "${YELLOW}⏳ Waiting for PostgreSQL to be ready...${NC}"
until pg_isready -h $DB_HOST -p 5432 -U $DB_USER -d $DB_NAME; do
    echo "PostgreSQL is not ready yet. Waiting..."
    sleep 2
done

echo -e "${GREEN}✅ PostgreSQL is ready!${NC}"

# Set database ownership
echo -e "${YELLOW}🔧 Setting database ownership...${NC}"
PGPASSWORD=$DB_PASS psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "ALTER DATABASE $DB_NAME OWNER TO $DB_USER;" 2>/dev/null || echo "Database ownership already set"

# Navigate to the backend directory
cd /app/src/rhesis/backend

# Set environment variables for Alembic (these should already be set by Docker)
export SQLALCHEMY_DB_DRIVER=${SQLALCHEMY_DB_DRIVER:-postgresql}
export SQLALCHEMY_DB_USER=$DB_USER
export SQLALCHEMY_DB_PASS=$DB_PASS
export SQLALCHEMY_DB_HOST=$DB_HOST
export SQLALCHEMY_DB_NAME=$DB_NAME

# Check if migrations need to be run
echo -e "${YELLOW}🔍 Checking current migration status...${NC}"
CURRENT_REVISION=$(alembic current 2>/dev/null | awk '{print $1}' || echo "None")

if [ "$CURRENT_REVISION" = "None" ] || [ -z "$CURRENT_REVISION" ]; then
    echo -e "${YELLOW}📦 Running database migrations...${NC}"
    
    # Run migrations
    if alembic upgrade head; then
        echo -e "${GREEN}✅ Database migrations completed successfully!${NC}"
        
        # Show migration status
        echo -e "${BLUE}📊 Migration Status:${NC}"
        alembic current
        
        # Show tables created
        echo -e "${BLUE}📋 Database Tables:${NC}"
        PGPASSWORD=$DB_PASS psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "\dt" | head -20
        
    else
        echo -e "${RED}❌ Database migrations failed!${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✅ Database is already up to date (revision: $CURRENT_REVISION)${NC}"
fi

echo -e "${GREEN}🎉 Database setup complete!${NC}" 