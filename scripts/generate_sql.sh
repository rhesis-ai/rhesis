#!/bin/bash

# Script to generate create_user.sql from template using environment variables

# Load environment variables from .env file if it exists
if [ -f ".env" ]; then
    echo "Loading environment variables from .env file..."
    export $(cat .env | grep -v '^#' | xargs)
fi

# Set default values if not provided
POSTGRES_USER=${POSTGRES_USER:-rhesis-user}
POSTGRES_DB=${POSTGRES_DB:-rhesis-db}

echo "Generating create_user.sql with:"
echo "  POSTGRES_USER: $POSTGRES_USER"
echo "  POSTGRES_DB: $POSTGRES_DB"

# Create the SQL file from template
cat > apps/backend/src/rhesis/backend/alembic/create_user.sql << EOF
-- Grant necessary privileges on the table in the public schema
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "$POSTGRES_USER";

-- Grant the same privileges on any future tables in the public schema
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "$POSTGRES_USER";

-- Grant CONNECT privilege to the user for the database
GRANT CONNECT ON DATABASE "$POSTGRES_DB" TO "$POSTGRES_USER";

-- Grant USAGE privilege on the public schema
GRANT USAGE ON SCHEMA public TO "$POSTGRES_USER";

-- Grant CREATE privilege on the public schema (for migrations)
GRANT CREATE ON SCHEMA public TO "$POSTGRES_USER";
EOF

echo "✅ create_user.sql generated successfully!" 