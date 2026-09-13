/**
 * Which detail tab a `?tab=` value (plus legacy aliases) refers to.
 *
 * Shared between `page.tsx` (a Server Component, to decide which tab's data to
 * prefetch) and `TestRunMainViewClient` (to pick the initially active tab) --
 * they must resolve the same value the same way, or the server prefetches one
 * tab's data while the client opens a different one.
 */

// Order defines the tab indices, so append rather than insert: anything else
// shifts every TabPanel index and the legacy key aliases below.
export const TAB_KEYS = [
  'summary',
  'linked_entities',
  'configuration',
  'traces',
  'reviews',
] as const;

export type TabKey = (typeof TAB_KEYS)[number];

export function tabIndexFromKey(
  key: string | null,
  preferLinkedEntities: boolean
): number {
  if (key === 'results') {
    return TAB_KEYS.indexOf('linked_entities');
  }
  if (key === 'stats') {
    return TAB_KEYS.indexOf('summary');
  }
  if (key === 'logs') {
    return TAB_KEYS.indexOf('traces');
  }
  const idx = TAB_KEYS.indexOf(key as TabKey);
  if (idx >= 0) return idx;
  return preferLinkedEntities ? TAB_KEYS.indexOf('linked_entities') : 0;
}
