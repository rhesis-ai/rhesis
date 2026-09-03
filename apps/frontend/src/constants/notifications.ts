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
  // Account-level notifications (e.g. "set a password"). Badges no nav
  // item; the drawer links to the settings page.
  ACCOUNT: 'account',
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

/**
 * The two `Notification.event_type` values a usage threshold crossing can
 * carry. Mirrors `NotificationEventType.Usage` in `models/enums.py` -- kept
 * as plain strings rather than importing the backend enum (Python and
 * TypeScript share no module), the same split every other wire-value mirror
 * in this file uses. `NotificationsDrawer` reads these to color a quota row
 * distinctly from an ordinary success/failure one.
 */
export const UsageNotificationEventType = {
  APPROACHING_LIMIT: 'usage.approaching_limit',
  BLOCKED: 'usage.blocked',
} as const;
