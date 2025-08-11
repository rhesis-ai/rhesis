-- Create the user with a placeholder password (ignore if already exists)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'myuser') THEN
        CREATE USER myuser WITH PASSWORD 'mypassword';
    END IF;
END
$$;

-- Grant necessary privileges on the table in the public schema
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO myuser;

-- Grant the same privileges on any future tables in the public schema
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO myuser;

-- Grant CONNECT privilege to the user for the rhesis_local_second_test database
GRANT CONNECT ON DATABASE rhesis_local_second_test TO myuser;