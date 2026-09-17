'use client';

import { GridBadge } from '@/components/common/GridBadge';

/**
 * How many rows a detail tab holds, rendered beside its label in
 * {@link DetailTabNav}'s `badge` slot.
 *
 * Nothing at zero: an empty tab already says so in its own empty state, and a
 * `0` pill beside every unused tab is noise.
 */
export function TabCountBadge({ count }: { count: number }) {
  if (count <= 0) return null;
  return <GridBadge label={count} size="detail" />;
}

export default TabCountBadge;
