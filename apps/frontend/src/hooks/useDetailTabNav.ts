'use client';

import { useCallback, useState } from 'react';

/**
 * Shared hook for tab navigation on entity detail pages.
 *
 * Tab state is local to the client and doesn't sync to the URL, so switching
 * tabs never triggers a server round-trip -- the detail page's data is
 * server-fetched once on load and already sits in props for every tab.
 *
 * @example
 * const TAB_KEYS = ['basic', 'linked', 'tasks'] as const;
 * const { activeTab, handleTabChange } = useDetailTabNav(TAB_KEYS);
 */
export function useDetailTabNav<T extends string>(
  tabKeys: readonly T[]
): {
  activeTab: number;
  handleTabChange: (newIndex: number) => void;
} {
  const [activeTab, setActiveTab] = useState(0);

  const handleTabChange = useCallback(
    (newIndex: number) => {
      if (newIndex >= 0 && newIndex < tabKeys.length) {
        setActiveTab(newIndex);
      }
    },
    [tabKeys.length]
  );

  return { activeTab, handleTabChange };
}
