    DO $$ 
    DECLARE target_user_id UUID;
    DECLARE org_ids UUID[];
    BEGIN
        -- Step 1: Get the user ID
        SELECT id INTO target_user_id FROM "user" WHERE email = 'harrycruz@gmail.com';

        -- If no user was found, exit early
        IF target_user_id IS NULL THEN
            RAISE NOTICE 'User not found, exiting.';
            RETURN;
        END IF;

        -- Step 2: Collect organization IDs linked to this user
        SELECT ARRAY_AGG(id) INTO org_ids 
        FROM organization 
        WHERE user_id = target_user_id OR owner_id = target_user_id;

        -- Guard clause to exit early if no orgs are found
        IF org_ids IS NULL OR array_length(org_ids, 1) IS NULL THEN
            RAISE NOTICE 'No organizations found for user %, exiting.', target_user_id;
            RETURN;
        END IF;
        
        -- Step 3: Delete test_results linked to test_configurations of these organizations
        DELETE FROM test_result 
        WHERE test_configuration_id IN (
            SELECT id FROM test_configuration 
            WHERE organization_id = ANY(org_ids)
        );

        -- Step 4: Delete test_runs linked to test_configurations of these organizations
        DELETE FROM test_run 
        WHERE test_configuration_id IN (
            SELECT id FROM test_configuration 
            WHERE organization_id = ANY(org_ids)
        );

        -- Step 5: Delete test_configurations linked to test_sets of these organizations
        DELETE FROM test_configuration 
        WHERE organization_id = ANY(org_ids);

        -- Step 6: Delete test_test_set associations
        DELETE FROM test_test_set 
        WHERE test_set_id IN (
            SELECT id FROM test_set 
            WHERE organization_id = ANY(org_ids)
        );

        -- Step 7: Delete test_contexts for tests in these organizations
        DELETE FROM test_context 
        WHERE test_id IN (
            SELECT id FROM test 
            WHERE organization_id = ANY(org_ids)
        );

        -- Step 8: Delete tests linked to these organizations
        DELETE FROM test 
        WHERE organization_id = ANY(org_ids);

        -- Step 9: Delete test_sets linked to these organizations
        DELETE FROM test_set 
        WHERE organization_id = ANY(org_ids);

        -- Step 10: Delete endpoints linked to projects
        DELETE FROM endpoint 
        WHERE project_id IN (
            SELECT id FROM project 
            WHERE organization_id = ANY(org_ids)
        );

        -- Step 11: Delete endpoints directly linked to organizations
        DELETE FROM endpoint 
        WHERE organization_id = ANY(org_ids);

        -- Step 12: Delete projects linked to these organizations
        DELETE FROM project 
        WHERE organization_id = ANY(org_ids);

        -- Step 13: Delete response_patterns
        DELETE FROM response_pattern 
        WHERE organization_id = ANY(org_ids);

        -- Step 14: Delete prompt_use_case associations
        DELETE FROM prompt_use_case 
        WHERE organization_id = ANY(org_ids);

        -- Step 15: Delete prompts and prompt_templates
        DELETE FROM prompt 
        WHERE organization_id = ANY(org_ids);
        DELETE FROM prompt_template 
        WHERE organization_id = ANY(org_ids);

        -- Step 16: Delete risk_use_case associations
        DELETE FROM risk_use_case 
        WHERE organization_id = ANY(org_ids);

        -- Step 17: Delete risks
        DELETE FROM risk 
        WHERE organization_id = ANY(org_ids);

        -- Step 18: Delete use_cases
        DELETE FROM use_case 
        WHERE organization_id = ANY(org_ids);

        -- Step 19: Delete behaviors
        DELETE FROM behavior 
        WHERE organization_id = ANY(org_ids);

        -- Step 20: Delete categories
        DELETE FROM category 
        WHERE organization_id = ANY(org_ids);

        -- Step 21: Delete demographics
        DELETE FROM demographic 
        WHERE organization_id = ANY(org_ids);

        -- Step 22: Delete dimensions
        DELETE FROM dimension 
        WHERE organization_id = ANY(org_ids);

        -- Step 23: Delete topics
        DELETE FROM topic 
        WHERE organization_id = ANY(org_ids);

        -- Step 24: Delete subscriptions
        DELETE FROM subscription 
        WHERE organization_id = ANY(org_ids);

        -- Step 25: Delete statuses
        DELETE FROM status 
        WHERE organization_id = ANY(org_ids);

        -- Step 26: Delete tokens
        DELETE FROM token 
        WHERE organization_id = ANY(org_ids);

        -- Step 27: Delete type_lookups
        DELETE FROM type_lookup 
        WHERE organization_id = ANY(org_ids);

        -- Step 27a: Delete tagged_items for these organizations
        DELETE FROM tagged_item 
        WHERE organization_id = ANY(org_ids);

        -- Step 27b: Delete tags for these organizations
        DELETE FROM tag 
        WHERE organization_id = ANY(org_ids);

        -- Step 28: Update organizations to remove user references
        UPDATE organization 
        SET user_id = NULL, owner_id = NULL 
        WHERE id = ANY(org_ids);
        
        -- Step 29: Update user to remove organization reference
        UPDATE "user" 
        SET organization_id = NULL 
        WHERE id = target_user_id;

        -- Step 30: Delete organizations that were linked to this user
        DELETE FROM organization WHERE id = ANY(org_ids);

        -- Step 31: Delete the user
        DELETE FROM "user" WHERE id = target_user_id;
    END $$;