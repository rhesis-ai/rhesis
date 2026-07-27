# Direct requests

Skip the full workflow when intent is a single action:

| Request | Action |
|---|---|
| List test sets / metrics / behaviors | `list_*` with `$select` |
| Update / improve metric X | `list_metrics` → `improve_metric` or `update_metric` |
| Update behavior Y | `list_behaviors` → `update_behavior` |
| Link metric A to behavior B | resolve both → `add_behavior_to_metric` |
| Unlink | `get_metric_behaviors` → `remove_behavior_from_metric` |
| Ground tests in doc | `create_source` → `generate_test_set` with source id |
| Show test set contents | `list_test_set_tests` |
| Compare two runs | `get_test_result_stats` `mode=test_runs` |

Always resolve entities by name — never ask for raw IDs.

Tool reference: `tool-catalog.md`. OData: `odata-patterns.md`.
