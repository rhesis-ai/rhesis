// Kept apart from TestDetailTabs so the route's loading view can draw the
// same tabs without pulling the page in.

export const TAB_KEYS = ['basic', 'linked', 'history', 'tasks'] as const;

export const TAB_LABELS: Record<(typeof TAB_KEYS)[number], string> = {
  basic: 'Overview',
  linked: 'Test Sets',
  history: 'Execution History',
  tasks: 'Tasks',
};
