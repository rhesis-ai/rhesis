'use client';

import React from 'react';
import PageLoadingState from './PageLoadingState';

interface GridStateGateProps {
  /**
   * Set to false to bypass all gating and always render `children` — for
   * grids embedded in another page (e.g. a project's Endpoints tab) that
   * never owned a full-page loading/empty presentation to begin with.
   */
  active?: boolean;
  /** The query's data object — gates on `data`, not `isLoading`, so a query
   *  that hasn't started yet (e.g. still waiting on session auth) is treated
   *  the same as one that's actively fetching. */
  data: unknown;
  error?: string | null;
  isEmpty: boolean;
  emptyState: React.ReactNode;
  children: React.ReactNode;
}

/**
 * Centralizes the loading → empty-state → content decision every grid page
 * makes: show a spinner until the first fetch settles, show a dedicated
 * empty-state card if that fetch came back with nothing, otherwise render
 * the grid. An error always falls through to `children` so the caller's own
 * error `Alert` (rendered alongside the grid) gets a chance to show —
 * fetch failures leave `data` undefined forever, so without this the error
 * would be masked by a permanent loading spinner.
 */
export default function GridStateGate({
  active = true,
  data,
  error = null,
  isEmpty,
  emptyState,
  children,
}: GridStateGateProps) {
  if (!active) return <>{children}</>;
  if (!data && !error) return <PageLoadingState />;
  if (isEmpty && !error) return <>{emptyState}</>;
  return <>{children}</>;
}
