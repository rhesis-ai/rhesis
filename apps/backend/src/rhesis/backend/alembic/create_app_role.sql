-- Runtime role for the app: NOSUPERUSER NOBYPASSRLS, DML only, so RLS applies to it.
-- migrate.sh runs this as ADMIN_DB_USER in one transaction, only when the role is missing,
-- before `alembic upgrade`. Same grants as the CNPG bootstrap (kubernetes/base/cnpg-cluster)
-- and tests/backend/testcontainers_setup.py.
-- Variables: app_user, app_pass, admin_user (the role that runs migrations and owns the tables).

SELECT format('CREATE ROLE %I LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE PASSWORD %L',
              :'app_user', :'app_pass') \gexec

SELECT format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), :'app_user') \gexec
SELECT format('GRANT USAGE ON SCHEMA public TO %I', :'app_user') \gexec

-- Existing tables (an install that ran the app as ADMIN_DB_USER until now).
SELECT format('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO %I',
              :'app_user') \gexec
SELECT format('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO %I', :'app_user') \gexec

-- Tables that later migrations create.
SELECT format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public '
              'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO %I',
              :'admin_user', :'app_user') \gexec
SELECT format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public '
              'GRANT USAGE, SELECT ON SEQUENCES TO %I',
              :'admin_user', :'app_user') \gexec

-- The blanket grant above undoes the REVOKE an append-only table's migration made.
SELECT DISTINCT format('REVOKE UPDATE, DELETE, TRUNCATE ON %s FROM %I', c.oid::regclass, :'app_user')
FROM pg_trigger t
JOIN pg_class c ON c.oid = t.tgrelid
JOIN pg_proc p ON p.oid = t.tgfoid
WHERE p.proname = 'reject_append_only_change' \gexec

-- The audit retention purge; its migration grants it to every role that can insert.
SELECT format('GRANT EXECUTE ON FUNCTION %s TO %I', p.oid::regprocedure, :'app_user')
FROM pg_proc p
WHERE p.proname = 'audit_event_purge' AND p.pronamespace = 'public'::regnamespace \gexec
