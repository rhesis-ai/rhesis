-- Grant necessary privileges on the table in the public schema
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "rhesis_user";

-- Grant the same privileges on any future tables in the public schema
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "rhesis_user";

-- Grant CONNECT privilege to the user for the rhesis-db database
GRANT CONNECT ON DATABASE "rhesis_db" TO "rhesis_user";

-- Grant USAGE privilege on the public schema
GRANT USAGE ON SCHEMA public TO "rhesis_user";

-- Grant CREATE privilege on the public schema (for migrations)
GRANT CREATE ON SCHEMA public TO "rhesis_user";