-- Create the user with a placeholder password
CREATE USER rhesis_user WITH PASSWORD 'xxxxx';

-- Grant necessary privileges on the table in the public schema
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO rhesis_user;

-- Grant the same privileges on any future tables in the public schema
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO rhesis_user;

-- Grant CONNECT privilege to the user for the rhesis-test database
GRANT CONNECT ON DATABASE "rhesis-test" TO rhesis_user;