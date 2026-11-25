// Kept apart from ProjectDetailTabs so the route's loading view can draw the
// same tabs without pulling the page in.

export const TAB_KEYS = [
  'overview',
  'members',
  'endpoints',
  'experiments',
  'traces',
] as const;
export type ProjectTabKey = (typeof TAB_KEYS)[number];

export const TAB_LABELS: Record<ProjectTabKey, string> = {
  overview: 'Overview',
  members: 'Members',
  endpoints: 'Endpoints',
  experiments: 'Experiments',
  traces: 'Traces',
};

export const LEGACY_TAB_MAP: Record<string, ProjectTabKey> = {
  endpoints: 'endpoints',
  traceMetrics: 'traces',
  parameters: 'experiments',
  environments: 'experiments',
  configuration: 'experiments',
  members: 'members',
};

export function normalizeTabParam(param: string | null): ProjectTabKey {
  if (param && param in LEGACY_TAB_MAP) {
    return LEGACY_TAB_MAP[param];
  }
  if (param && TAB_KEYS.includes(param as ProjectTabKey)) {
    return param as ProjectTabKey;
  }
  return 'overview';
}
