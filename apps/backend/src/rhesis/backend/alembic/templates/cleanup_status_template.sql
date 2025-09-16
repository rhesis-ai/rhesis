-- Template for cleaning up status entries
-- Usage: Call this template with TYPE_NAME, ENTITY_TYPE and STATUS_NAMES_PLACEHOLDER replaced
-- Example: TYPE_NAME = 'EntityType', ENTITY_TYPE = 'Task', STATUS_NAMES_PLACEHOLDER = 'Open', 'In Progress', 'Completed', 'Cancelled'

DELETE FROM public.status 
WHERE name IN ({{STATUS_NAMES_PLACEHOLDER}})
  AND entity_type_id IN (
      SELECT tl.id 
      FROM public.type_lookup tl 
      WHERE tl.type_name = '{{TYPE_NAME}}' AND tl.type_value = '{{ENTITY_TYPE}}'
  );
