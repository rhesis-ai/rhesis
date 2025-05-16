WITH orgs AS (
    SELECT id AS organization_id
    FROM public.organization
),
entity_types AS (
    SELECT tl.organization_id, tl.id AS entity_type_id
    FROM public.type_lookup tl
    WHERE tl.type_name = 'EntityType' AND tl.type_value = 'TestSet'
),
org_entity_mapping AS (
    SELECT o.organization_id, et.entity_type_id
    FROM orgs o
    JOIN entity_types et ON o.organization_id = et.organization_id
),
to_insert AS (
    SELECT 
        status_info.name,
        status_info.description,
        oem.entity_type_id,
        oem.organization_id,
        substring(md5(random()::text), 1, 10) AS nano_id
    FROM 
        org_entity_mapping oem,
        (VALUES
            ('New', 'Describes a new test set'),
            ('Review', 'Describes a test set in review'),
            ('Approved', 'Describes an approved test set')
        ) AS status_info(name, description)
)
INSERT INTO public.status (name, description, entity_type_id, organization_id, nano_id)
SELECT 
    t.name,
    t.description,
    t.entity_type_id,
    t.organization_id,
    t.nano_id
FROM to_insert t
WHERE NOT EXISTS (
    SELECT 1
    FROM public.status s
    WHERE s.name = t.name
      AND s.organization_id = t.organization_id
      AND s.entity_type_id = t.entity_type_id
);