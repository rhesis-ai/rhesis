'use client';

import React, { useMemo, useState } from 'react';
import { Box, Button } from '@mui/material';
import GridToolbar, {
  directoryToolbarProps,
} from '@/components/common/GridToolbar';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { writeInsightsEndpointId } from '@/utils/insights-endpoint';
import { DEFAULT_INSIGHTS_FILTERS, InsightsFilters } from '../types';
import InsightsFilterDrawer, {
  countActiveInsightsDrawerFilters,
  hasActiveInsightsDrawerFilters,
  type InsightsDrawerFilters,
} from './InsightsFilterDrawer';
import { InsightsBehaviorOption } from '../utils/insights-filter-utils';

interface TestResultsFiltersProps {
  filters: InsightsFilters;
  onFiltersChange: (filters: InsightsFilters) => void;
  projectEndpoints: Endpoint[];
  endpointsLoading: boolean;
  behaviorOptions: InsightsBehaviorOption[];
  searchQuery: string;
  onSearchChange: (value: string) => void;
  showExpandToggle?: boolean;
  allExpanded?: boolean;
  onToggleAll?: () => void;
  /**
   * `compact` keeps endpoint/test-run controls (filter drawer) but hides
   * behavior search — used on the no-test-results empty state.
   */
  variant?: 'full' | 'compact';
}

export default function TestResultsFilters({
  filters,
  onFiltersChange,
  projectEndpoints,
  endpointsLoading,
  behaviorOptions,
  searchQuery,
  onSearchChange,
  showExpandToggle = false,
  allExpanded = false,
  onToggleAll,
  variant = 'full',
}: TestResultsFiltersProps) {
  const isCompact = variant === 'compact';
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);

  const drawerFilters = useMemo<InsightsDrawerFilters>(
    () => ({
      endpointId: filters.endpointId,
      behaviorIds: filters.behaviorIds,
      statusIds: filters.statusIds,
      timeRange: filters.timeRange,
      testRunIds: filters.testRunIds,
    }),
    [
      filters.endpointId,
      filters.behaviorIds,
      filters.statusIds,
      filters.timeRange,
      filters.testRunIds,
    ]
  );

  const handleDrawerApply = (next: InsightsDrawerFilters) => {
    if (next.endpointId) {
      writeInsightsEndpointId(next.endpointId);
    }
    onFiltersChange({
      ...filters,
      endpointId: next.endpointId,
      behaviorIds: next.behaviorIds,
      statusIds: next.statusIds,
      timeRange: next.timeRange,
      testRunIds: next.testRunIds,
    });
  };

  const hasActiveFilters = hasActiveInsightsDrawerFilters(drawerFilters);

  const handleResetAllFilters = () => {
    onFiltersChange(DEFAULT_INSIGHTS_FILTERS);
  };

  return (
    <>
      <GridToolbar
        searchQuery={searchQuery}
        onSearchChange={onSearchChange}
        searchPlaceholder="Search behaviors…"
        showSearch={!isCompact}
        onFilterClick={() => setFilterDrawerOpen(true)}
        hasActiveFilters={hasActiveFilters}
        activeFilterCount={countActiveInsightsDrawerFilters(drawerFilters)}
        {...directoryToolbarProps}
        middleContent={
          (showExpandToggle && onToggleAll) || hasActiveFilters ? (
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                flexWrap: 'wrap',
              }}
            >
              {showExpandToggle && onToggleAll ? (
                <Button size="small" variant="text" onClick={onToggleAll}>
                  {allExpanded ? 'Collapse all' : 'Expand all'}
                </Button>
              ) : null}
              {hasActiveFilters ? (
                <Button
                  size="small"
                  variant="text"
                  onClick={handleResetAllFilters}
                >
                  Reset filters
                </Button>
              ) : null}
            </Box>
          ) : undefined
        }
      />

      <InsightsFilterDrawer
        open={filterDrawerOpen}
        onClose={() => setFilterDrawerOpen(false)}
        filters={drawerFilters}
        projectEndpoints={projectEndpoints}
        endpointsLoading={endpointsLoading}
        behaviorOptions={behaviorOptions}
        onApply={handleDrawerApply}
      />
    </>
  );
}
