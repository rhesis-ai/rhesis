ALTER TABLE public.behavior ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.category ENABLE ROW LEVEL SECURITY;


CREATE POLICY tenant_isolation ON public.behavior
    USING (organization_id = current_setting('app.current_organization')::uuid);


CREATE POLICY tenant_isolation ON public.category
    USING (organization_id = current_setting('app.current_organization')::uuid);


SET app.current_organization = 'b2b20496-b388-4454-a864-2440a5afe13b';
SELECT * FROM public.behavior;

ALTER TABLE public.behavior DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.behavior ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.behavior NO FORCE ROW LEVEL SECURITY;

SELECT relname, relrowsecurity, relforcerowsecurity
FROM pg_class
WHERE relname = 'behavior';

SELECT 
    relname AS table_name, 
    relrowsecurity AS rls_enabled 
FROM 
    pg_class 
WHERE 
    relnamespace = 'public'::regnamespace 
    AND relrowsecurity = true
	
ALTER POLICY tenant_isolation
ON public.behavior
USING (organization_id = current_setting('app.current_organization')::uuid)
TO public;

ALTER POLICY tenant_isolation
ON public.behavior
USING (organization_id = current_setting('app.current_organization')::uuid);

SELECT rolname, rolbypassrls 
FROM pg_roles 
WHERE rolname = 'nocodb-user';

SELECT proname, prosecdef FROM pg_proc WHERE prosecdef;

SELECT current_user, session_user;