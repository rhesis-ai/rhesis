-- PROCEDURE: public.delete_user_and_organization_data(text)

DROP PROCEDURE IF EXISTS public.delete_user_and_organization_data(text);

CREATE OR REPLACE PROCEDURE public.delete_user_and_organization_data(
    target_email text
)
LANGUAGE plpgsql
AS $BODY$
DECLARE
    target_user_id UUID;
    org_ids UUID[];
    project_ids UUID[];
    endpoint_ids UUID[];
    test_config_ids UUID[];
    test_ids UUID[];
    test_run_ids UUID[];
    test_set_ids UUID[];
    
    -- Configuration: tables with status_id that need to be NULLed
    status_ref_tables TEXT[] := ARRAY[
        'behavior', 'category', 'endpoint', 'metric', 'model', 'prompt', 
        'prompt_template', 'project', 'risk', 'source', 'subscription', 
        'task', 'test', 'test_configuration', 'test_result', 'test_run', 
        'test_set', 'topic', 'use_case'
    ];
    
    -- Configuration: lookup references to NULL out (table, column, lookup_table)
    type_lookup_refs TEXT[][] := ARRAY[
        ARRAY['category', 'entity_type_id', 'type_lookup'],
        ARRAY['topic', 'entity_type_id', 'type_lookup'],
        ARRAY['status', 'entity_type_id', 'type_lookup'],
        ARRAY['model', 'provider_type_id', 'type_lookup'],
        ARRAY['metric', 'metric_type_id', 'type_lookup'],
        ARRAY['metric', 'backend_type_id', 'type_lookup'],
        ARRAY['response_pattern', 'response_pattern_type_id', 'type_lookup'],
        ARRAY['source', 'source_type_id', 'type_lookup'],
        ARRAY['test_set', 'license_type_id', 'type_lookup'],
        ARRAY['test', 'test_type_id', 'type_lookup']
    ];
    
    -- Configuration: tables with owner_id/assignee_id to NULL out
    ownership_tables TEXT[][] := ARRAY[
        ARRAY['metric', 'owner_id'],
        ARRAY['metric', 'assignee_id'],
        ARRAY['model', 'owner_id'],
        ARRAY['model', 'assignee_id'],
        ARRAY['project', 'owner_id'],
        ARRAY['test', 'owner_id'],
        ARRAY['test', 'assignee_id'],
        ARRAY['test_run', 'owner_id'],
        ARRAY['test_run', 'assignee_id'],
        ARRAY['test_set', 'owner_id'],
        ARRAY['test_set', 'assignee_id'],
        ARRAY['task', 'assignee_id']
    ];
    
    table_name TEXT;
    ref_info TEXT[];
    sql_stmt TEXT;
BEGIN
    -- ========================================================================
    -- STEP 1: Get the user ID
    -- ========================================================================
    SELECT id INTO target_user_id
    FROM "user"
    WHERE email = target_email;

    IF target_user_id IS NULL THEN
        RAISE NOTICE 'User not found, exiting.';
        RETURN;
    END IF;

    -- ========================================================================
    -- STEP 2: Collect all related IDs
    -- ========================================================================
    SELECT COALESCE(ARRAY_AGG(id), '{}') INTO org_ids
    FROM organization
    WHERE user_id = target_user_id OR owner_id = target_user_id;

    SELECT COALESCE(ARRAY_AGG(id), '{}') INTO project_ids
    FROM project
    WHERE organization_id = ANY(org_ids) 
       OR user_id = target_user_id 
       OR owner_id = target_user_id;

    SELECT COALESCE(ARRAY_AGG(id), '{}') INTO endpoint_ids
    FROM endpoint
    WHERE organization_id = ANY(org_ids)
       OR project_id = ANY(project_ids)
       OR user_id = target_user_id;

    SELECT COALESCE(ARRAY_AGG(id), '{}') INTO test_config_ids
    FROM test_configuration
    WHERE endpoint_id = ANY(endpoint_ids)
       OR organization_id = ANY(org_ids)
       OR user_id = target_user_id;

    SELECT COALESCE(ARRAY_AGG(DISTINCT id), '{}') INTO test_ids
    FROM test
    WHERE organization_id = ANY(org_ids)
       OR user_id = target_user_id
       OR owner_id = target_user_id
       OR assignee_id = target_user_id
       OR prompt_id IN (SELECT id FROM prompt WHERE organization_id = ANY(org_ids) OR user_id = target_user_id)
       OR topic_id IN (SELECT id FROM topic WHERE organization_id = ANY(org_ids) OR user_id = target_user_id)
       OR behavior_id IN (SELECT id FROM behavior WHERE organization_id = ANY(org_ids) OR user_id = target_user_id)
       OR category_id IN (SELECT id FROM category WHERE organization_id = ANY(org_ids) OR user_id = target_user_id)
       OR status_id IN (SELECT id FROM status WHERE organization_id = ANY(org_ids) OR user_id = target_user_id)
       OR source_id IN (SELECT id FROM source WHERE organization_id = ANY(org_ids) OR user_id = target_user_id);

    SELECT COALESCE(ARRAY_AGG(DISTINCT id), '{}') INTO test_run_ids
    FROM test_run
    WHERE test_configuration_id = ANY(test_config_ids)
       OR organization_id = ANY(org_ids)
       OR user_id = target_user_id
       OR owner_id = target_user_id
       OR assignee_id = target_user_id;

    SELECT COALESCE(ARRAY_AGG(DISTINCT id), '{}') INTO test_set_ids
    FROM test_set
    WHERE organization_id = ANY(org_ids)
       OR user_id = target_user_id
       OR owner_id = target_user_id
       OR assignee_id = target_user_id;

    RAISE NOTICE 'Deleting data for user: %', target_email;
    RAISE NOTICE 'Organizations: %, Projects: %, Endpoints: %, Test Configs: %', 
        array_length(org_ids, 1), array_length(project_ids, 1), 
        array_length(endpoint_ids, 1), array_length(test_config_ids, 1);
    RAISE NOTICE 'Tests: %, Test Runs: %, Test Sets: %',
        array_length(test_ids, 1), array_length(test_run_ids, 1), array_length(test_set_ids, 1);

    -- ========================================================================
    -- PHASE 1: NULL OUT lookup table references in OTHER orgs' data
    -- ========================================================================
    
    -- NULL out status_id references
    FOREACH table_name IN ARRAY status_ref_tables
    LOOP
        sql_stmt := format(
            'UPDATE %I SET status_id = NULL 
             WHERE status_id IN (SELECT id FROM status WHERE organization_id = ANY($1) OR user_id = $2)
               AND (organization_id IS NULL OR organization_id <> ALL($1))',
            table_name
        );
        EXECUTE sql_stmt USING org_ids, target_user_id;
    END LOOP;

    -- NULL out type_lookup references
    FOREACH ref_info SLICE 1 IN ARRAY type_lookup_refs
    LOOP
        sql_stmt := format(
            'UPDATE %I SET %I = NULL 
             WHERE %I IN (SELECT id FROM %I WHERE organization_id = ANY($1) OR user_id = $2)',
            ref_info[1], ref_info[2], ref_info[2], ref_info[3]
        );
        EXECUTE sql_stmt USING org_ids, target_user_id;
    END LOOP;

    -- ========================================================================
    -- PHASE 2: Delete user/org-owned data (in correct FK order)
    -- ========================================================================

    -- Delete test_result
    DELETE FROM test_result 
    WHERE test_configuration_id = ANY(test_config_ids)
       OR test_run_id = ANY(test_run_ids)
       OR test_id = ANY(test_ids)
       OR organization_id = ANY(org_ids)
       OR user_id = target_user_id;

    -- Delete test_run
    DELETE FROM test_run WHERE id = ANY(test_run_ids);

    -- Delete test_configuration
    DELETE FROM test_configuration WHERE id = ANY(test_config_ids);

    -- Delete test_test_set and test_context
    DELETE FROM test_test_set 
    WHERE test_set_id = ANY(test_set_ids) OR test_id = ANY(test_ids);
    
    DELETE FROM test_context 
    WHERE test_id = ANY(test_ids) OR organization_id = ANY(org_ids) OR user_id = target_user_id;

    -- Delete test and test_set
    DELETE FROM test WHERE id = ANY(test_ids);
    DELETE FROM test_set WHERE id = ANY(test_set_ids);

    -- Delete prompt_test_set
    DELETE FROM prompt_test_set 
    WHERE prompt_id IN (SELECT id FROM prompt WHERE organization_id = ANY(org_ids) OR user_id = target_user_id)
       OR user_id = target_user_id OR organization_id = ANY(org_ids);

    -- Delete endpoints
    DELETE FROM endpoint WHERE id = ANY(endpoint_ids);

    -- Delete projects
    DELETE FROM project WHERE id = ANY(project_ids);

    -- Delete model
    DELETE FROM model 
    WHERE organization_id = ANY(org_ids) OR user_id = target_user_id
       OR owner_id = target_user_id OR assignee_id = target_user_id;

    -- Delete behavior_metric
    DELETE FROM behavior_metric 
    WHERE behavior_id IN (SELECT id FROM behavior WHERE organization_id = ANY(org_ids) OR user_id = target_user_id)
       OR user_id = target_user_id OR organization_id = ANY(org_ids);

    -- Delete metric
    DELETE FROM metric 
    WHERE organization_id = ANY(org_ids) OR user_id = target_user_id
       OR owner_id = target_user_id OR assignee_id = target_user_id;

    -- Delete behavior
    DELETE FROM behavior WHERE organization_id = ANY(org_ids) OR user_id = target_user_id;

    -- Delete prompt dependencies
    DELETE FROM prompt_use_case 
    WHERE prompt_id IN (SELECT id FROM prompt WHERE organization_id = ANY(org_ids) OR user_id = target_user_id)
       OR user_id = target_user_id OR organization_id = ANY(org_ids);
    DELETE FROM prompt WHERE organization_id = ANY(org_ids) OR user_id = target_user_id;
    DELETE FROM prompt_template WHERE organization_id = ANY(org_ids) OR user_id = target_user_id;

    -- Delete risk dependencies
    DELETE FROM risk_use_case 
    WHERE risk_id IN (SELECT id FROM risk WHERE organization_id = ANY(org_ids) OR user_id = target_user_id)
       OR user_id = target_user_id OR organization_id = ANY(org_ids);
    DELETE FROM risk WHERE organization_id = ANY(org_ids) OR user_id = target_user_id;

    -- Delete use_case
    DELETE FROM use_case WHERE organization_id = ANY(org_ids) OR user_id = target_user_id;

    -- Delete response_pattern
    DELETE FROM response_pattern WHERE organization_id = ANY(org_ids) OR user_id = target_user_id;

    -- Delete category, demographic, dimension, topic, source
    DELETE FROM category WHERE organization_id = ANY(org_ids) OR user_id = target_user_id;
    DELETE FROM demographic WHERE organization_id = ANY(org_ids) OR user_id = target_user_id;
    DELETE FROM dimension WHERE organization_id = ANY(org_ids) OR user_id = target_user_id;
    DELETE FROM topic WHERE organization_id = ANY(org_ids) OR user_id = target_user_id;
    DELETE FROM source WHERE organization_id = ANY(org_ids) OR user_id = target_user_id;

    -- Delete tagged_item and tag
    DELETE FROM tagged_item 
    WHERE tag_id IN (SELECT id FROM tag WHERE organization_id = ANY(org_ids) OR user_id = target_user_id)
       OR user_id = target_user_id OR organization_id = ANY(org_ids);
    DELETE FROM tag WHERE organization_id = ANY(org_ids) OR user_id = target_user_id;

    -- Delete lookup tables (all references are now NULL or deleted)
    DELETE FROM status WHERE organization_id = ANY(org_ids) OR user_id = target_user_id;
    DELETE FROM type_lookup WHERE organization_id = ANY(org_ids) OR user_id = target_user_id;

    -- Delete subscription, token, comment, task
    DELETE FROM subscription WHERE organization_id = ANY(org_ids) OR user_id = target_user_id;
    DELETE FROM token WHERE organization_id = ANY(org_ids) OR user_id = target_user_id;
    DELETE FROM comment WHERE organization_id = ANY(org_ids) OR user_id = target_user_id;
    DELETE FROM task 
    WHERE organization_id = ANY(org_ids) OR user_id = target_user_id OR assignee_id = target_user_id;

    -- ========================================================================
    -- PHASE 3: NULL out ownership references in OTHER orgs
    -- ========================================================================
    FOREACH ref_info SLICE 1 IN ARRAY ownership_tables
    LOOP
        sql_stmt := format('UPDATE %I SET %I = NULL WHERE %I = $1', ref_info[1], ref_info[2], ref_info[2]);
        EXECUTE sql_stmt USING target_user_id;
    END LOOP;

    -- ========================================================================
    -- PHASE 4: Delete organizations and user
    -- ========================================================================
    
    -- Delete other users in those organizations
    IF array_length(org_ids, 1) > 0 THEN
        DELETE FROM "user" WHERE organization_id = ANY(org_ids) AND id <> target_user_id;
    END IF;

    -- Detach the target user from organization
    UPDATE "user" SET organization_id = NULL WHERE id = target_user_id;

    -- Reset and delete organizations
    IF array_length(org_ids, 1) > 0 THEN
        UPDATE organization
        SET is_onboarding_complete = false, user_id = NULL, owner_id = NULL
        WHERE id = ANY(org_ids);
        DELETE FROM organization WHERE id = ANY(org_ids);
    END IF;

    -- Delete the user itself
    DELETE FROM "user" WHERE id = target_user_id;

    RAISE NOTICE 'User % and all related data have been deleted successfully', target_email;
END;
$BODY$;

ALTER PROCEDURE public.delete_user_and_organization_data(text)
OWNER TO "rhesis-user";

COMMENT ON PROCEDURE public.delete_user_and_organization_data(text)
IS 'HARD DELETE: Completely removes a user and all their organization data. This is irreversible and should only be used for complete data removal (testing, cleanup, or extreme cases). Use gdpr_anonymize_user() for GDPR compliance instead.';