// Kept apart from RequirementDetailTabs so the route's loading view can draw
// the same tabs without pulling the page in.

export const REQUIREMENT_TAB_KEYS = [
  'basic',
  'examples',
  'linked-metrics',
  'linked-tests',
  'linked-requirements',
] as const;

export type RequirementTabKey = (typeof REQUIREMENT_TAB_KEYS)[number];

export const NAV_LABELS: Record<RequirementTabKey, string> = {
  basic: 'Basic Information',
  examples: 'Examples',
  'linked-metrics': 'Metrics',
  'linked-tests': 'Tests',
  'linked-requirements': 'Requirements',
};
