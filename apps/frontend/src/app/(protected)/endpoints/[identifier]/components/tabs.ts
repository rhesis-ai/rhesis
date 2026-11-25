// Kept apart from the tab components so the route's loading view can draw
// the same tabs without pulling the page in.

export const TAB_KEYS = ['overview', 'connection', 'mapping', 'test'] as const;
export type EndpointTabKey = (typeof TAB_KEYS)[number];

export const TAB_LABELS: Record<EndpointTabKey, string> = {
  overview: 'Basics',
  connection: 'Connection',
  mapping: 'Mapping',
  test: 'Test',
};

export function normalizeTabParam(param: string | null): EndpointTabKey {
  if (param && TAB_KEYS.includes(param as EndpointTabKey)) {
    return param as EndpointTabKey;
  }
  return 'overview';
}
