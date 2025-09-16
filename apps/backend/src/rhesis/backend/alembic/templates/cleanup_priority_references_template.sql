-- Template for cleaning up entity priority references before deleting priorities
-- Usage: Call this template with TABLE_NAME, PRIORITY_COLUMN, TYPE_NAME, TYPE_VALUES_PLACEHOLDER replaced
-- Example: TABLE_NAME = 'task', PRIORITY_COLUMN = 'priority', TYPE_NAME = 'TaskPriority', TYPE_VALUES_PLACEHOLDER = 'Low', 'Medium', 'High'

UPDATE public.{{TABLE_NAME}} 
SET {{PRIORITY_COLUMN}}_id = NULL
WHERE {{PRIORITY_COLUMN}}_id IN (
    SELECT tl.id 
    FROM public.type_lookup tl 
    WHERE tl.type_name = '{{TYPE_NAME}}' 
      AND tl.type_value IN ({{TYPE_VALUES_PLACEHOLDER}})
);
