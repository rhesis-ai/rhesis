'use client';

import React, { useContext } from 'react';
import {
  GridToolbarColumnsButton,
  GridToolbarDensitySelector,
  GridToolbarExport,
} from '@mui/x-data-grid';
import GridToolbar, {
  ToolbarPillTabs,
  type ToolbarPillTab,
} from '@/components/common/GridToolbar';
import type { TraceView } from './trace-filter-params';

const VIEW_TABS: ToolbarPillTab[] = [
  { label: 'Traces', value: 'traces' },
  { label: 'Spans', value: 'spans' },
];

const SEARCH_PLACEHOLDER: Record<TraceView, string> = {
  traces: 'Search operations…',
  // The spans endpoint matches name, span ID and trace ID.
  spans: 'Search span name or ID…',
};

export interface TracesToolbarState {
  view: TraceView;
  /** Unset hides the switch. */
  onViewChange?: (view: TraceView) => void;
  searchQuery: string;
  setSearchQuery: (v: string) => void;
  openFilterDrawer: () => void;
  hasActiveDrawerFilters: boolean;
  activeFilterCount: number;
}

/**
 * Both tables render this toolbar through the grid's toolbar slot, which takes a
 * component rather than props, so its state travels in a context.
 */
export const TracesToolbarContext = React.createContext<TracesToolbarState>({
  view: 'traces',
  searchQuery: '',
  setSearchQuery: () => {},
  openFilterDrawer: () => {},
  hasActiveDrawerFilters: false,
  activeFilterCount: 0,
});

export default function TracesToolbar() {
  const {
    view,
    onViewChange,
    searchQuery,
    setSearchQuery,
    openFilterDrawer,
    hasActiveDrawerFilters,
    activeFilterCount,
  } = useContext(TracesToolbarContext);

  return (
    <GridToolbar
      searchQuery={searchQuery}
      onSearchChange={setSearchQuery}
      searchPlaceholder={SEARCH_PLACEHOLDER[view]}
      onFilterClick={openFilterDrawer}
      hasActiveFilters={hasActiveDrawerFilters}
      activeFilterCount={activeFilterCount}
      middleContent={
        onViewChange ? (
          <ToolbarPillTabs
            tabs={VIEW_TABS}
            activeValue={view}
            onChange={value => onViewChange(value as TraceView)}
          />
        ) : undefined
      }
      rightContent={
        <>
          <GridToolbarColumnsButton />
          <GridToolbarDensitySelector />
          <GridToolbarExport />
        </>
      }
    />
  );
}
