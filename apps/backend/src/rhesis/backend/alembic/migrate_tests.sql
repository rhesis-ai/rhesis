DO $$
DECLARE
    rec RECORD;
BEGIN
    FOR rec IN 
        SELECT id, behavior_id, category_id, topic_id
        FROM public.prompt
        ORDER BY created_at
    LOOP
        INSERT INTO public.test (
            id,
            prompt_id,
            test_type_id,
            priority,
            user_id,
            owner_id,
            assignee_id,
            test_configuration,
            parent_id,
            topic_id,
            behavior_id,
            category_id,
            status_id,
            nano_id,
            created_at,
            updated_at,
            organization_id
        ) VALUES (
            gen_random_uuid(),
            rec.id,
            '317a853e-1f1c-4ded-8c2c-b82a6f6a20cd', -- fixed test_type_id
            1, -- priority
            'd7834188-a9aa-410c-a63d-89d6f487aed8', -- fixed user_id
            'd7834188-a9aa-410c-a63d-89d6f487aed8', -- fixed owner_id
            'a68b1eb9-ed8f-4df2-a6c5-fb25225e195b', -- fixed assignee_id
            '{}'::jsonb, -- empty test_configuration
            NULL, -- parent_id
            rec.topic_id,
            rec.behavior_id,
            rec.category_id,
            '63b7bd48-1fc8-48ec-8f3c-3f731ca3207b', -- fixed status_id
            NULL, -- nano_id (can be generated later if needed)
            NOW(),
            NOW(),
            'b2b20496-b388-4454-a864-2440a5afe13b' -- fixed organization_id
        );
    END LOOP;
END;
$$;