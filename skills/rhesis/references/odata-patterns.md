# OData Query Patterns for Rhesis

The Rhesis API uses OData conventions for filtering, selecting fields, and paginating results. All `list_*` tools accept these query parameters.

---

## Field selection (`$select`)

Request only the fields you need to keep payloads small and avoid truncation.

```
$select=name,id,description
```

- `id` is always returned, even if not listed.
- For `list_test_results`, always omit `response` and `evaluation_prompt` unless you specifically need the full text — these are large fields that cause truncation.

**Common patterns by entity:**

| Tool | Recommended `$select` |
|------|----------------------|
| `list_endpoints` | `name,id,url,description` |
| `list_behaviors` | `name,id,description` |
| `list_metrics` | `name,id,score_type,threshold` |
| `list_test_sets` | `name,id,description` |
| `list_test_runs` | `id,status,test_set,created_at` |
| `list_test_results` | `id,status,prompt,behavior,metric_scores` |

---

## Filtering (`$filter`)

### Case-insensitive name lookup (exact)

```
$filter=tolower(name) eq 'file chatbot'
```

Always use `tolower()` and pass the search value in lowercase. The API performs case-insensitive comparisons only when you wrap both sides in `tolower()`.

### Case-insensitive name lookup (partial)

```
$filter=contains(tolower(name), 'chatbot')
```

Use this when the user gives an approximate or shortened name. More permissive — if it returns multiple matches, present them and ask the user to clarify.

### Exact match on a related field (navigation property)

Use slash notation to filter by a related entity's field:

```
$filter=status/name eq 'Failed'
$filter=status/name eq 'Completed'
```

Do **not** filter by `status_id` with a string value — `status_id` is a UUID and can't be compared with a readable name.

**Common navigation filters:**
- Test results by status: `$filter=test_run_id eq '<uuid>' and status/name eq 'Failed'`
- Test runs by status: `$filter=status/name eq 'Completed'`

### Filter by related entity UUID

```
$filter=test_run_id eq '<uuid>'
```

Always use this when listing test results for a specific run.

### Batched OR lookup (resolve multiple names in one call)

Instead of making one call per entity, batch them with OR:

```
$filter=tolower(name) eq 'refuses harmful requests' or tolower(name) eq 'provides accurate information' or tolower(name) eq 'handles errors gracefully'
```

Use this after creating behaviors to resolve all their IDs in a single call.

### Combining filter and select

```
$filter=contains(tolower(name), 'safety')&$select=name,id,description
```

OData separates multiple query parameters with `&`. Combine freely.

---

## Pagination (`$top`, `$skip`)

```
$top=50
$skip=0
```

- `$top` limits the number of results returned. Default varies by endpoint.
- `$skip` skips the first N results, enabling page-through.
- For most planning operations, the default page size is sufficient. Use `$top=100` if you expect many results.

---

## Worked examples

### Resolve a behavior by approximate name

```
list_behaviors
  $filter=contains(tolower(name), 'safety')
  $select=name,id,description
```

### Find all test results that failed for a specific run

```
list_test_results
  $filter=test_run_id eq '6a01639e-...' and status/name eq 'Failed'
  $select=id,status,prompt,behavior,metric_scores
```

### Find a test run that completed for a specific test set

```
list_test_runs
  $filter=status/name eq 'Completed'
  $select=id,status,test_set,created_at
```

### Resolve three behavior IDs in one call

```
list_behaviors
  $filter=tolower(name) eq 'refuses harmful requests' or tolower(name) eq 'provides accurate information' or tolower(name) eq 'responds within domain'
  $select=name,id
```

### Browse metrics without loading evaluation prompts

```
list_metrics
  $select=name,id,score_type,threshold,metric_scope
```
