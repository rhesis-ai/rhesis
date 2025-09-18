-- Template for inserting type_lookup entries
-- Usage: Call this template with VALUES_PLACEHOLDER replaced with your data
-- Example: VALUES ('EntityType', 'Task', 'Entity type for tasks')

WITH new_entries AS (
    SELECT *
    FROM (
        VALUES
            {{VALUES_PLACEHOLDER}}
    ) AS vals(type_name, type_value, description)
),
orgs AS (
    SELECT DISTINCT organization_id FROM type_lookup
)
INSERT INTO type_lookup (type_name, type_value, description, organization_id, user_id)
SELECT 
    n.type_name,
    n.type_value,
    n.description,
    o.organization_id,
    NULL as user_id
FROM new_entries n
CROSS JOIN orgs o
WHERE NOT EXISTS (
    SELECT 1 FROM type_lookup existing
    WHERE existing.type_name = n.type_name
      AND existing.type_value = n.type_value
      AND existing.organization_id = o.organization_id
);
