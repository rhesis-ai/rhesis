// Kept apart from TaskDetailTabs so the route's loading view can draw the same
// tabs without pulling the page in.

export const TAB_KEYS = ['basic', 'linked', 'comments'] as const;

export const TAB_LABELS: Record<(typeof TAB_KEYS)[number], string> = {
  basic: 'Basic Information',
  linked: 'Linked entities',
  comments: 'Comments',
};
