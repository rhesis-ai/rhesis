-- Create the rhesis-user if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'rhesis-user') THEN
        CREATE USER "rhesis-user" WITH PASSWORD 'rhesis-password';
    END IF;
END
$$;

-- Create the rhesis-db database if it doesn't exist
SELECT 'CREATE DATABASE "rhesis-db" OWNER "rhesis-user"'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'rhesis-db')\gexec

-- Grant necessary privileges on the table in the public schema
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "rhesis-user";

-- Grant the same privileges on any future tables in the public schema
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "rhesis-user";

-- Grant CONNECT privilege to the user for the rhesis-db database
GRANT CONNECT ON DATABASE "rhesis-db" TO "rhesis-user";

-- Grant USAGE privilege on the public schema
GRANT USAGE ON SCHEMA public TO "rhesis-user";

-- Grant CREATE privilege on the public schema (for migrations)
GRANT CREATE ON SCHEMA public TO "rhesis-user";
