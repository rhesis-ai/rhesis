// Kept apart from UsageDetailTabs so the route's loading view can draw the
// same tabs without pulling the page in.

export const USAGE_TITLE = 'Usage';
export const USAGE_DESCRIPTION =
  "Track your organization's metered resource consumption against its plan limits.";

/** The trail after the organization's own crumb. */
export const USAGE_CRUMB = { label: USAGE_TITLE, href: '/organizations/usage' };

export const TAB_KEYS = ['resources', 'timeline'] as const;
type UsageTabKey = (typeof TAB_KEYS)[number];

export const TAB_LABELS: Record<UsageTabKey, string> = {
  resources: 'Resources',
  timeline: 'Timeline',
};

export function normalizeTabParam(param: string | null): UsageTabKey {
  if (param && TAB_KEYS.includes(param as UsageTabKey)) {
    return param as UsageTabKey;
  }
  return 'resources';
}
