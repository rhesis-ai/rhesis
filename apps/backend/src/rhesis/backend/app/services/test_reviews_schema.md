# Human Reviews Schema for Test Results

## Overview

Human reviews complement automated metrics by allowing human evaluators to review, adjust, or override automated test outcomes.  
Each test result can include one or more **reviews**, representing human judgments with structured metadata.

This schema separates **automated metrics** (`test_metrics`) from **human-provided evaluations** (`test_reviews`), enabling clearer data management, traceability, and aggregation.

**Status**: ✅ **Fully Implemented and Tested**

---

## Design Goals

- **Separation of concerns:** Keep human feedback separate from machine metrics.
- **Support multiple reviewers and rounds:** Allow several humans to evaluate the same test.
- **Granular scope:** Reviews can target specific metrics or the overall test.
- **Traceability:** Include timestamps, reviewer identity, and status references.
- **Efficient access:** Include top-level metadata for quick lookups and summaries.
- **Full CRUD operations:** Create, read, update, and delete reviews via REST API.
- **Automatic metadata management:** Metadata updates automatically on all operations.

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

## Implementation Details

### Database

**Column**: `test_reviews` (JSONB, nullable)  
**Table**: `test_result`  
**Migration**: `f8b3c9d4e5a6_add_test_reviews_column.py`

### Backend Models

**File**: `apps/backend/src/rhesis/backend/app/models/test_result.py`

```python
class TestResult(Base, ...):
    test_reviews = Column(JSONB)
    
    @property
    def last_review(self) -> Optional[Dict[str, Any]]:
        """Returns the most recent review based on updated_at timestamp"""
        # Returns latest review or None
    
    @property
    def matches_review(self) -> bool:
        """Check if test result status_id matches latest review status_id"""
        # Returns True/False
```

### Pydantic Schemas

**File**: `apps/backend/src/rhesis/backend/app/schemas/test_result.py`

```python
# Review schemas
class ReviewTargetCreate(Base):
    type: str  # "test" or "metric"
    reference: Optional[str] = None  # metric name or null

class ReviewCreate(Base):
    status_id: UUID4
    comments: str
    target: ReviewTargetCreate

class ReviewUpdate(Base):
    status_id: Optional[UUID4] = None
    comments: Optional[str] = None
    target: Optional[ReviewTargetCreate] = None

class ReviewResponse(Base):
    review_id: str
    status: Dict[str, Any]
    user: Dict[str, Any]
    comments: str
    created_at: str
    updated_at: str
    target: Dict[str, Any]
```

---

## API Endpoints

All endpoints follow REST conventions and automatically manage metadata.

### 1. Create Review

**Endpoint**: `POST /test_results/{test_result_id}/reviews`

**Request Body**:
```json
{
  "status_id": "735acfa0-cca2-48a1-bb90-ba10b16f1cdb",
  "comments": "Test review - looks good after manual inspection",
  "target": {
    "type": "test",
    "reference": null
  }
}
```

**Response** (201 Created):
```json
{
  "review_id": "c370e2d7-f526-41c4-94f0-a6f25735a9b9",
  "status": {
    "status_id": "735acfa0-cca2-48a1-bb90-ba10b16f1cdb",
    "name": "Pass"
  },
  "user": {
    "user_id": "d7834188-a9aa-410c-a63d-89d6f487aed8",
    "name": "Harry Cruz"
  },
  "comments": "Test review - looks good after manual inspection",
  "created_at": "2025-10-10T13:18:16.310822",
  "updated_at": "2025-10-10T13:18:16.310822",
  "target": {
    "type": "test",
    "reference": null
  }
}
```

**Features**:
- Auto-generates unique `review_id`
- Sets both `created_at` and `updated_at` to current time
- Auto-populates user info from authenticated user
- Fetches and embeds status details from Status model
- Updates test_reviews metadata automatically

### 2. Update Review

**Endpoint**: `PUT /test_results/{test_result_id}/reviews/{review_id}`

**Request Body** (all fields optional):
```json
{
  "comments": "UPDATED: After further review, this test passes all criteria"
}
```

**Response** (200 OK):
```json
{
  "review_id": "c370e2d7-f526-41c4-94f0-a6f25735a9b9",
  "status": {
    "status_id": "735acfa0-cca2-48a1-bb90-ba10b16f1cdb",
    "name": "Pass"
  },
  "user": {
    "user_id": "d7834188-a9aa-410c-a63d-89d6f487aed8",
    "name": "Harry Cruz"
  },
  "comments": "UPDATED: After further review, this test passes all criteria",
  "created_at": "2025-10-10T13:18:16.310822",
  "updated_at": "2025-10-10T13:18:41.168149",
  "target": {
    "type": "test",
    "reference": null
  }
}
```

**Features**:
- Preserves `created_at` timestamp
- Updates `updated_at` to current time
- Updates only provided fields
- Updates metadata automatically

### 3. Delete Review

**Endpoint**: `DELETE /test_results/{test_result_id}/reviews/{review_id}`

**Response** (200 OK):
```json
{
  "message": "Review deleted successfully",
  "review_id": "c370e2d7-f526-41c4-94f0-a6f25735a9b9",
  "deleted_review": {
    "review_id": "c370e2d7-f526-41c4-94f0-a6f25735a9b9",
    "status": {...},
    "user": {...},
    "comments": "UPDATED: After further review, this test passes all criteria",
    "created_at": "2025-10-10T13:18:16.310822",
    "updated_at": "2025-10-10T13:18:41.168149",
    "target": {...}
  }
}
```

**Features**:
- Removes review from reviews array
- Updates metadata automatically
- Handles empty state (when last review deleted, sets `latest_status: null`)
- Returns deleted review data

### 4. Get Test Result with Reviews

**Endpoint**: `GET /test_results/{test_result_id}`

**Response** includes:
```json
{
  "id": "fe647ace-5364-4158-b634-9bc7c53d7905",
  "status_id": "735acfa0-cca2-48a1-bb90-ba10b16f1cdb",
  "test_reviews": {
    "metadata": {
      "last_updated_at": "2025-10-10T13:18:16.310860",
      "last_updated_by": {
        "user_id": "d7834188-a9aa-410c-a63d-89d6f487aed8",
        "name": "Harry Cruz"
      },
      "total_reviews": 1,
      "latest_status": {
        "status_id": "735acfa0-cca2-48a1-bb90-ba10b16f1cdb",
        "name": "Pass"
      },
      "summary": "Last updated by Harry Cruz"
    },
    "reviews": [
      {
        "review_id": "c370e2d7-f526-41c4-94f0-a6f25735a9b9",
        "status": {...},
        "user": {...},
        "comments": "...",
        "created_at": "2025-10-10T13:18:16.310822",
        "updated_at": "2025-10-10T13:18:16.310822",
        "target": {...}
      }
    ]
  },
  "last_review": {
    "review_id": "c370e2d7-f526-41c4-94f0-a6f25735a9b9",
    "status": {...},
    "user": {...},
    "comments": "...",
    "created_at": "2025-10-10T13:18:16.310822",
    "updated_at": "2025-10-10T13:18:16.310822",
    "target": {...}
  },
  "matches_review": true
}
```

**Derived Properties**:
- `last_review`: Most recent review by `updated_at` timestamp
- `matches_review`: Boolean indicating if test result status matches latest review status

---

## Frontend TypeScript Interfaces

**File**: `apps/frontend/src/utils/api-client/interfaces/test-results.ts`

```typescript
// Review interfaces
export interface ReviewUser {
  user_id: UUID;
  name: string;
}

export interface ReviewStatus {
  status_id: UUID;
  name: string;
}

export interface ReviewTarget {
  type: 'test' | 'metric';
  reference: string | null;
}

export interface Review {
  review_id: UUID;
  status: ReviewStatus;
  user: ReviewUser;
  comments: string;
  created_at: string;
  updated_at: string;
  target: ReviewTarget;
}

export interface TestReviewsMetadata {
  last_updated_at: string;
  last_updated_by: ReviewUser;
  total_reviews: number;
  latest_status: ReviewStatus;
  summary?: string;
}

export interface TestReviews {
  metadata: TestReviewsMetadata;
  reviews: Review[];
}

// Test Result interface includes:
export interface TestResult extends TestResultBase {
  id: UUID;
  created_at: string;
  updated_at: string;
  test_reviews?: TestReviews;
  last_review?: Review;
  matches_review: boolean;
}
```

---

## Frontend Implementation Guide

### 1. Display Reviews

```typescript
import { TestResult } from '@/utils/api-client/interfaces/test-results';

function ReviewsList({ testResult }: { testResult: TestResult }) {
  if (!testResult.test_reviews?.reviews.length) {
    return <div>No reviews yet</div>;
  }

  return (
    <div>
      <h3>Reviews ({testResult.test_reviews.metadata.total_reviews})</h3>
      {testResult.test_reviews.reviews.map(review => (
        <ReviewCard key={review.review_id} review={review} />
      ))}
    </div>
  );
}
```

### 2. Create Review

```typescript
async function createReview(testResultId: string, statusId: string, comments: string) {
  const response = await fetch(
    `${API_BASE_URL}/test_results/${testResultId}/reviews`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        status_id: statusId,
        comments: comments,
        target: {
          type: 'test',
          reference: null
        }
      })
    }
  );
  
  return await response.json();
}
```

### 3. Update Review

```typescript
async function updateReview(
  testResultId: string, 
  reviewId: string, 
  updates: { comments?: string; status_id?: string }
) {
  const response = await fetch(
    `${API_BASE_URL}/test_results/${testResultId}/reviews/${reviewId}`,
    {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(updates)
    }
  );
  
  return await response.json();
}
```

### 4. Delete Review

```typescript
async function deleteReview(testResultId: string, reviewId: string) {
  const response = await fetch(
    `${API_BASE_URL}/test_results/${testResultId}/reviews/${reviewId}`,
    {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${token}`,
      }
    }
  );
  
  return await response.json();
}
```

### 5. Display Latest Review Badge

```typescript
function LatestReviewBadge({ testResult }: { testResult: TestResult }) {
  if (!testResult.last_review) return null;

  return (
    <div className="badge">
      <span>Latest Review: {testResult.last_review.status.name}</span>
      <span>By: {testResult.last_review.user.name}</span>
      {!testResult.matches_review && (
        <span className="warning">Status mismatch!</span>
      )}
    </div>
  );
}
```

### 6. Status Conflict Detection

```typescript
function StatusConflictAlert({ testResult }: { testResult: TestResult }) {
  if (!testResult.last_review || testResult.matches_review) {
    return null;
  }

  return (
    <Alert severity="warning">
      Test result status does not match the latest review status.
      Test: {testResult.status?.name} | Review: {testResult.last_review.status.name}
    </Alert>
  );
}
```

---

## Use Cases

### 1. **Override Automated Metrics**
A human reviewer disagrees with an automated pass/fail and adds a review with a different status.

### 2. **Multi-Reviewer Workflow**
Multiple team members review the same test result, each adding their perspective.

### 3. **Metric-Specific Reviews**
Review specific metrics (e.g., "Answer Relevancy") separately from overall test.

### 4. **Audit Trail**
Track who reviewed what and when, with full edit history via timestamps.

### 5. **Status Conflict Detection**
Use `matches_review` to identify cases where human review disagrees with automated result.

---

## Testing

All functionality has been tested and verified:

✅ Create review with auto-generated ID and timestamps  
✅ Update review with preserved `created_at`  
✅ Delete review with metadata updates  
✅ Multiple reviews support  
✅ Both "test" and "metric" target types  
✅ Empty state handling  
✅ Derived properties (`last_review`, `matches_review`)  
✅ Automatic metadata synchronization  

---

## Future Extensions

Potential enhancements:
- `confidence`: Reviewer confidence score (0–1)
- `attachments`: File attachments for evidence
- `review_type`: Categorize reviews (approval, rejection, follow-up)
- `tags`: Categorize reviews with tags
- Review workflows and approval chains

---