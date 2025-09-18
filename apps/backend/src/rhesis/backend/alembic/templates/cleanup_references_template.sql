-- Template for cleaning up entity references before deleting statuses/priorities
-- Usage: Call this template with TABLE_NAME, REFERENCE_TYPE, TYPE_NAME, ENTITY_TYPE and VALUES_PLACEHOLDER replaced
-- Example: TABLE_NAME = 'task', REFERENCE_TYPE = 'status', TYPE_NAME = 'EntityType', ENTITY_TYPE = 'Task', VALUES_PLACEHOLDER = 'Open', 'In Progress', 'Completed', 'Cancelled'

UPDATE public.{{TABLE_NAME}} 
SET {{REFERENCE_TYPE}}_id = (
    SELECT s.id 
    FROM public.status s 
    WHERE s.organization_id = {{TABLE_NAME}}.organization_id 
      AND s.name NOT IN ({{VALUES_PLACEHOLDER}})
    LIMIT 1
)
WHERE {{REFERENCE_TYPE}}_id IN (
    SELECT s.id 
    FROM public.status s
    JOIN public.type_lookup tl ON s.entity_type_id = tl.id
    WHERE s.name IN ({{VALUES_PLACEHOLDER}})
      AND tl.type_name = '{{TYPE_NAME}}' 
      AND tl.type_value = '{{ENTITY_TYPE}}'
);
