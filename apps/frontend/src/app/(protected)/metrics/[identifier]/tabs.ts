// Kept apart from MetricDetailPageTabs so the route's loading view can draw
// the same tabs without pulling the page in.

export const TAB_KEYS = ['basic', 'linked-requirements', 'tuning'] as const;

export const NAV_LABELS: Record<(typeof TAB_KEYS)[number], string> = {
  basic: 'Basic Information',
  'linked-requirements': 'Requirements',
  tuning: 'Tuning',
};
