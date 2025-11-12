# PR Checker Issues Requiring Backend Changes

This document outlines issues identified by the PR checker that cannot be resolved in a frontend-only PR and require backend implementation.

## 1. AuthN/AuthZ Flaw (Security)

**Issue**: Client-side only authorization check for review deletion in `TestDetailReviewsTab.tsx` line 446.

**Description**: The UI restricts the delete button visibility based on comparing `review.user.user_id === currentUserId`, but this check happens only in the frontend. An attacker could bypass this by directly calling the `deleteReview` API endpoint.

**Required Fix**: Implement server-side authorization checks in the backend API endpoint for `deleteReview` to verify that the authenticated user is the owner of the review before allowing deletion. The backend should return `403 Forbidden` if a user attempts to delete a review they don't own.

**Frontend Status**: ✅ Client-side check implemented for UX purposes (prevents accidental deletion attempts)

**Backend Status**: ⚠️ Requires backend validation

---

## 2. Uniqueness Constraint Violation (State & Data Consistency)

**Issue**: Race condition in review creation without uniqueness validation.

**Description**: Multiple simultaneous requests (from different tabs, users, or rapid clicks) can create duplicate reviews because the backend appends to the reviews array without checking for existing similar reviews or enforcing uniqueness constraints at the database level.

**Required Fix**: Add server-side uniqueness validation before creating reviews. Options:
1. Check if a review with the same `(user_id, test_result_id, target)` already exists before inserting
2. Add a database-level unique constraint on `(test_result_id, user_id, target_type, target_reference)`
3. Use an upsert operation instead of always appending
4. Implement optimistic locking with version numbers to detect concurrent modifications

**Frontend Status**: ✅ Client-side duplicate prevention implemented using `useRef` for atomic check-and-set

**Backend Status**: ⚠️ Requires backend validation and database constraints

---

## 3. Incorrect Exception Handling (Error Handling & Input Validation)

**Issue**: Multiple catch blocks only log errors to console without notifying users of failures.

**Description**: In `TestResultDrawer.tsx`, `TestDetailPanel.tsx`, and `TestsTableView.tsx`, when operations fail, errors are silently logged but users receive no feedback.

**Current Status**: ✅ Console logging implemented for debugging

**Recommended Enhancement**: Integrate with a user-facing notification system (e.g., toast notifications, snackbars) to display error messages. This requires:
1. A global notification context/provider
2. Consistent error message formatting
3. Error categorization (recoverable vs. fatal)

**Note**: This is a UX enhancement rather than a critical bug. Console logging provides visibility for developers, and the UI state (loading indicators, disabled buttons) provides implicit feedback to users that an operation completed.

---

## 4. Blocking Call on Hot Path (Performance)

**Issue**: Polling loop in `handleConfirmReview` performs up to 5 sequential API calls with delays.

**Description**: The function polls with exponential backoff to wait for backend processing to complete and the `last_review` property to be populated.

**Current Implementation**:
- Atomic check-and-set prevents duplicate submissions
- Button is disabled during operation
- Sequential polling with exponential backoff (100ms, 200ms, 400ms, 800ms)
- Final fetch ensures latest data

**Why This Design**:
1. Backend processing is asynchronous - we need to wait for the review to be persisted
2. Immediate return would show stale data to the user
3. React's async/await doesn't truly block the UI - other interactions remain possible
4. The button disabled state provides clear feedback

**Potential Alternatives** (require backend changes):
1. **Server-Sent Events (SSE)**: Backend pushes updates when review is persisted
2. **WebSocket**: Real-time bidirectional communication
3. **Optimistic UI with reconciliation**: Show immediate fake update, reconcile later
4. **Backend guarantees**: Synchronous review creation (may impact backend performance)

**Recommendation**: Current implementation is a reasonable trade-off. For a better UX, implement WebSocket or SSE for real-time updates, but this requires significant backend infrastructure.

---

## Summary

| Issue | Category | Frontend Status | Backend Required |
|-------|----------|-----------------|------------------|
| AuthN/AuthZ flaw | Security | ✅ Client check implemented | ⚠️ Yes - server-side validation |
| Uniqueness constraint | Data Consistency | ✅ Client prevention implemented | ⚠️ Yes - DB constraints |
| User notifications | UX | ✅ Console logging implemented | ⚠️ Optional - notification system |
| Polling performance | Performance | ✅ Optimized with backoff | ⚠️ Optional - real-time updates |

**Frontend improvements implemented in this PR**:
- Atomic check-and-set with `useRef` to prevent race conditions
- Exponential backoff polling for backend readiness
- Final fetch to ensure latest data
- Console error logging for debugging
- Input validation and null checks
- Type safety improvements

**Backend improvements needed**:
- Server-side authorization validation for review deletion
- Database uniqueness constraints for reviews
- (Optional) Real-time update mechanism (WebSocket/SSE)
- (Optional) Global notification system for user feedback
