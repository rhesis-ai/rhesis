// Kept apart from TestSetDetailTabs so the route's loading view can draw the
// same tabs without pulling the page in.

export const TAB_KEYS = ['basic', 'linked', 'runs', 'tasks'] as const;
export type TestSetTabKey = (typeof TAB_KEYS)[number];

export const TAB_LABELS: Record<TestSetTabKey, string> = {
  basic: 'Basic Information',
  linked: 'Tests',
  runs: 'Test Runs',
  tasks: 'Tasks',
};
