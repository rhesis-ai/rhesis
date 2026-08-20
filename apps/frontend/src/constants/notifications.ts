/**
 * Notification sidebar sections. Mirrors the backend `NotificationSection`
 * enum in `apps/backend/src/rhesis/backend/app/models/enums.py`. A value
 * equals the `NavigationPageItem.segment` of the page it badges (see
 * `src/app/layout.tsx`) when it badges one at all -- keep in sync when
 * adding a new section, same as `FeatureName`/`Capability`.
 */
export const NotificationSection = {
  TEST_SETS: 'test-sets',
  TEST_RUNS: 'test-runs',
  TASKS: 'tasks',
  // Badge only -- the architect page is a chat/session UI, not a grid, so
  // there are no rows for HIGHLIGHTED_ROW_CLASS to apply to.
  ARCHITECT: 'architect',
  // Badges no nav item -- there is no "/usage" nav segment -- but a quota
  // notification still needs a section to group and display under in the
  // notification drawer (`NotificationsDrawer.tsx`).
  USAGE: 'usage',
} as const;

export type NotificationSection =
  (typeof NotificationSection)[keyof typeof NotificationSection];

const NOTIFICATION_SECTION_VALUES: string[] =
  Object.values(NotificationSection);

/**
 * Narrows a wire value (a `Notification.section` string, or a URL segment)
 * to `NotificationSection`. Lives here rather than in each consumer: the
 * badge context, `NavItem` and the notifications drawer all need it, and
 * three copies drift the moment a section is added.
 */
export function isNotificationSection(
  value: string
): value is NotificationSection {
  return NOTIFICATION_SECTION_VALUES.includes(value);
}

/** CSS class applied to a grid row whose entity has an unseen notification. */
export const HIGHLIGHTED_ROW_CLASS = 'rhesis-row-notified';
