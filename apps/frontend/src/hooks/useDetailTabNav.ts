'use client';

import { useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

/**
 * Shared hook for URL-based tab navigation on entity detail pages.
 *
 * Reads `?tab=<key>` from the URL and returns the active tab index.
 * `handleTabChange` updates the URL param without scrolling.
 *
 * @example
 * const TAB_KEYS = ['basic', 'linked', 'tasks'] as const;
 * const { activeTab, handleTabChange } = useDetailTabNav(TAB_KEYS);
 */
export function useDetailTabNav<T extends string>(
  tabKeys: readonly T[],
  paramName = 'tab'
): {
  activeTab: number;
  handleTabChange: (newIndex: number) => void;
} {
  const router = useRouter();
  const searchParams = useSearchParams();

  const activeTab = (() => {
    const idx = tabKeys.indexOf(searchParams.get(paramName) as T);
    return idx >= 0 ? idx : 0;
  })();

  const handleTabChange = useCallback(
    (newIndex: number) => {
      const key = tabKeys[newIndex];
      const params = new URLSearchParams(searchParams.toString());
      params.set(paramName, key);
      router.push(`?${params.toString()}`, { scroll: false });
    },
    [router, searchParams, tabKeys, paramName]
  );

  return { activeTab, handleTabChange };
}
