// Kept apart from ExperimentDetailClient so the route's loading view can draw
// the same tabs without pulling the page in.

export const TAB_KEYS = ['overview', 'parameters', 'versions', 'runs'] as const;

export const TAB_LABELS: Record<(typeof TAB_KEYS)[number], string> = {
  overview: 'Overview',
  parameters: 'Parameters',
  versions: 'Versions',
  runs: 'Experiment Runs',
};
