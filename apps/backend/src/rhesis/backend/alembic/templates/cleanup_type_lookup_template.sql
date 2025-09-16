-- Template for cleaning up type_lookup entries
-- Usage: Call this template with TYPE_NAME and TYPE_VALUES_PLACEHOLDER replaced
-- Example: TYPE_NAME = 'TaskPriority', TYPE_VALUES_PLACEHOLDER = 'Low', 'Medium', 'High'

DELETE FROM type_lookup 
WHERE type_name = '{{TYPE_NAME}}' 
  AND type_value IN ({{TYPE_VALUES_PLACEHOLDER}});
