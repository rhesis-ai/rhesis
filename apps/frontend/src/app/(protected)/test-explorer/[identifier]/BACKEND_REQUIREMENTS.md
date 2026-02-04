# Backend API Requirements for Topic CRUD Operations

This document outlines the backend endpoints needed to handle topic operations more efficiently. Currently, these operations are handled on the frontend, which is inefficient and error-prone.

## Current Frontend Implementation (Inefficient)

The frontend currently handles these operations by:
1. Fetching all tests
2. Filtering/updating tests in memory
3. Making individual API calls for each test update
4. Managing topic path strings manually

This approach has several problems:
- Multiple API calls for a single operation (N+1 problem)
- Race conditions possible
- No transaction support (partial failures leave inconsistent state)
- Topic paths stored as strings in tests, making renames expensive

---

## Proposed Backend Endpoints

### 1. Rename Topic

**Endpoint:** `PUT /topics/{id}/rename` or `POST /topics/rename`

**Request Body:**
```json
{
  "old_path": "Safety/Harmful Content",
  "new_name": "Dangerous Content",
  "entity_type": "Test"
}
```

**Backend Responsibilities:**
- [ ] Find all topics matching the old path prefix
- [ ] Update topic names in the topics table
- [ ] Update all tests that reference these topics (by topic_id)
- [ ] Handle nested topics (e.g., "Safety/Harmful Content/Violence" becomes "Safety/Dangerous Content/Violence")
- [ ] Perform all updates in a single transaction
- [ ] Return updated topic and count of affected tests

**Response:**
```json
{
  "success": true,
  "topic": { "id": "...", "name": "Safety/Dangerous Content" },
  "affected_tests_count": 42,
  "affected_child_topics_count": 3
}
```

---

### 2. Delete Topic (with cascade to parent)

**Endpoint:** `DELETE /topics/{id}` with query params or `POST /topics/{id}/delete`

**Request Body/Params:**
```json
{
  "move_tests_to_parent": true,
  "move_children_to_parent": true
}
```

**Backend Responsibilities:**
- [ ] Find all tests under this topic
- [ ] Move tests to parent topic (update their topic_id)
- [ ] Find all child topics
- [ ] Reparent child topics to the parent of deleted topic
- [ ] Delete the topic record
- [ ] Perform all updates in a single transaction
- [ ] Return count of affected items

**Response:**
```json
{
  "success": true,
  "deleted_topic": "Safety/Harmful Content",
  "tests_moved": 15,
  "child_topics_reparented": 2,
  "new_parent": "Safety"
}
```

---

### 3. Move Topic (change parent)

**Endpoint:** `PUT /topics/{id}/move` or `POST /topics/move`

**Request Body:**
```json
{
  "topic_id": "uuid-of-topic",
  "new_parent_id": "uuid-of-new-parent",  // null for root
  "entity_type": "Test"
}
```

**Backend Responsibilities:**
- [ ] Update topic's parent reference
- [ ] Update all test topic paths that include this topic
- [ ] Update all child topic paths
- [ ] Perform in single transaction

---

### 4. Bulk Move Tests Between Topics

**Endpoint:** `POST /tests/bulk-move`

**Request Body:**
```json
{
  "test_ids": ["uuid1", "uuid2", "uuid3"],
  "target_topic_id": "uuid-of-target-topic"
}
```

**Backend Responsibilities:**
- [ ] Validate all test IDs exist
- [ ] Validate target topic exists
- [ ] Update all tests in single transaction
- [ ] Return success/failure count

---

### 5. Get Topic Tree (optimized)

**Endpoint:** `GET /topics/tree`

**Query Params:**
- `entity_type`: Filter by entity type (e.g., "Test")
- `include_counts`: Include test counts per topic
- `include_scores`: Include average scores per topic

**Backend Responsibilities:**
- [ ] Build topic tree from flat topic list
- [ ] Aggregate test counts at each level
- [ ] Aggregate scores at each level
- [ ] Return nested structure

**Response:**
```json
{
  "topics": [
    {
      "id": "uuid",
      "name": "Safety",
      "path": "Safety",
      "test_count": 100,
      "avg_score": 0.45,
      "children": [
        {
          "id": "uuid2",
          "name": "Harmful Content",
          "path": "Safety/Harmful Content",
          "test_count": 50,
          "avg_score": 0.52,
          "children": []
        }
      ]
    }
  ]
}
```

---

### 6. Create Topic (with parent support)

**Endpoint:** `POST /topics`

**Request Body:**
```json
{
  "name": "New Topic",
  "parent_id": "uuid-of-parent",  // optional, null for root
  "entity_type": "Test"
}
```

**Backend Responsibilities:**
- [ ] Validate parent exists (if provided)
- [ ] Create topic with proper path
- [ ] Return created topic with full path

---

## Database Schema Considerations

Currently topics appear to be stored as path strings. Consider:

1. **Hierarchical Topic Table:**
   ```sql
   CREATE TABLE topics (
     id UUID PRIMARY KEY,
     name VARCHAR(255) NOT NULL,
     parent_id UUID REFERENCES topics(id),
     path VARCHAR(1000) GENERATED ALWAYS AS (compute_path(id)),
     entity_type VARCHAR(50),
     ...
   );
   ```

2. **Materialized Path Pattern:**
   - Store full path for quick lookups
   - Use triggers to update child paths on rename

3. **Nested Set or Closure Table:**
   - Better for complex hierarchical queries
   - More efficient for "get all descendants" operations

---

## Migration Path

1. Add new endpoints alongside existing ones
2. Frontend can gradually migrate to new endpoints
3. Deprecate old patterns once migration complete

---

## Benefits of Backend Implementation

| Operation | Current (Frontend) | Proposed (Backend) |
|-----------|-------------------|-------------------|
| Rename topic with 100 tests | 101 API calls | 1 API call |
| Delete topic with 50 tests | 51 API calls | 1 API call |
| Data consistency | No guarantee | Transaction-based |
| Error handling | Complex | Simple |
| Performance | O(n) roundtrips | O(1) roundtrip |
