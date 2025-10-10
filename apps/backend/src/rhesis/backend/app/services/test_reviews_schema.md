# Human Reviews Schema for Test Results

## Overview

Human reviews complement automated metrics by allowing human evaluators to review, adjust, or override automated test outcomes.  
Each test result can include one or more **reviews**, representing human judgments with structured metadata.

This schema separates **automated metrics** (`test_metrics`) from **human-provided evaluations** (`test_reviews`), enabling clearer data management, traceability, and aggregation.

---

## Design Goals

- **Separation of concerns:** Keep human feedback separate from machine metrics.
- **Support multiple reviewers and rounds:** Allow several humans to evaluate the same test.
- **Granular scope:** Reviews can target specific metrics or the overall test.
- **Traceability:** Include timestamps, reviewer identity, and status references.
- **Efficient access:** Include top-level metadata for quick lookups and summaries.

---

## Top-Level Structure

The `test_reviews` field is stored as a JSON object with two parts:

- `metadata`: Summary information about the reviews collection.
- `reviews`: List of individual review objects.

---

## ✅ Final JSON Schema

```json
{
  "metadata": {
    "last_updated_at": "2025-10-10T14:15:00Z",
    "last_updated_by": {
      "user_id": "a1e2d3c4-5678-90ab-cdef-1234567890ab",
      "name": "Alice"
    },
    "total_reviews": 3,
    "latest_status": {
      "status_id": "b6f1a2e3-9c4d-4f12-8b3f-123456789abc",
      "name": "success"
    },
    "summary": "The latest review marks the test as successful after human validation."
  },
  "reviews": [
    {
      "review_id": "e9b5a2c7-13f2-4a91-94d0-4df8c1c5f0a1",
      "status": {
        "status_id": "b6f1a2e3-9c4d-4f12-8b3f-123456789abc",
        "name": "success"
      },
      "user": {
        "user_id": "a1e2d3c4-5678-90ab-cdef-1234567890ab",
        "name": "Alice"
      },
      "comments": "LLM refusal was appropriate for this case. Marking as successful.",
      "created_at": "2025-10-10T14:10:00Z",
      "updated_at": "2025-10-10T14:15:00Z",
      "target": {
        "type": "metric",
        "reference": "Refusal Detection"
      }
    }
  ]
}
```

---

## Field Reference

### **metadata**
| Field | Type | Description |
|--------|------|-------------|
| `last_updated_at` | string (ISO 8601) | Timestamp when any review was last modified. |
| `last_updated_by` | object | Contains the user ID and name of the last editor. |
| `total_reviews` | integer | Total number of reviews in the list. |
| `latest_status` | object | Status of the most recent review (for quick summaries). |
| `summary` | string | Optional short description or aggregated summary. |

### **reviews[]**
| Field | Type | Description |
|--------|------|-------------|
| `review_id` | UUID | Unique ID for this review entry. |
| `status` | object | Contains a `status_id` (UUID) and `name` (string). |
| `user` | object | Contains a `user_id` (UUID) and `name` (string). |
| `comments` | string | Free-text explanation from the reviewer. |
| `created_at` | string (ISO 8601) | Timestamp when the review was first created. |
| `updated_at` | string (ISO 8601) | Timestamp when the review was last modified. |
| `target` | object | Defines whether the review applies to a metric or the whole test. |

#### Example `target` values
```json
{ "type": "test", "reference": null }
{ "type": "metric", "reference": "Refusal Detection" }
```

---

## Implementation Notes

- Store this JSON in a dedicated column (e.g., `test_reviews JSONB`) in the `test_results` table.
- Update `metadata` automatically when any review is added or edited.

---

## Future Extensions

Potential fields to add later:
- `confidence`: reviewer confidence score (0–1)

---

