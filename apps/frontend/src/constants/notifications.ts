/**
 * Notification sidebar sections. Mirrors the backend `NotificationSection`
 * enum in `apps/backend/src/rhesis/backend/app/models/enums.py`. Values must
 * equal the `NavigationPageItem.segment` of the page they badge (see
 * `src/app/layout.tsx`) -- keep in sync when adding a new section, same as
 * `FeatureName`/`Capability`.
 */
export const NotificationSection = {
  TEST_SETS: 'test-sets',
  TEST_RUNS: 'test-runs',
  TASKS: 'tasks',
  // Badge only -- the architect page is a chat/session UI, not a grid, so
  // there are no rows for HIGHLIGHTED_ROW_CLASS to apply to.
  ARCHITECT: 'architect',
} as const;

export type NotificationSection =
  (typeof NotificationSection)[keyof typeof NotificationSection];

/** CSS class applied to a grid row whose entity has an unseen notification. */
export const HIGHLIGHTED_ROW_CLASS = 'rhesis-row-notified';
