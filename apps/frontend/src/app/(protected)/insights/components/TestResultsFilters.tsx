'use client';

import React, { useMemo, useState } from 'react';
import { Box, Button } from '@mui/material';
import GridToolbar, {
  directoryToolbarProps,
  ToolbarPillTabs,
} from '@/components/common/GridToolbar';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { writeInsightsEndpointId } from '@/utils/insights-endpoint';
import {
  DEFAULT_INSIGHTS_FILTERS,
  INSIGHTS_GROUP_BY_OPTIONS,
  InsightsFilters,
  InsightsGroupBy,
} from '../types';
import InsightsFilterDrawer, {
  countActiveInsightsDrawerFilters,
  hasActiveInsightsDrawerFilters,
  type InsightsDrawerFilters,
} from './InsightsFilterDrawer';
import { InsightsRequirementOption } from '../utils/insights-filter-utils';

interface TestResultsFiltersProps {
  filters: InsightsFilters;
  onFiltersChange: (filters: InsightsFilters) => void;
  projectEndpoints: Endpoint[];
  endpointsLoading: boolean;
  requirementOptions: InsightsRequirementOption[];
  searchQuery: string;
  onSearchChange: (value: string) => void;
  showExpandToggle?: boolean;
  allExpanded?: boolean;
  onToggleAll?: () => void;
  /**
   * `compact` keeps endpoint/test-run controls (filter drawer) but hides
   * requirement search — used on the no-test-results empty state.
   */
  variant?: 'full' | 'compact';
  /** Controls the filter drawer from outside; uncontrolled when omitted. */
  filterDrawerOpen?: boolean;
  onFilterDrawerOpenChange?: (open: boolean) => void;
}

export default function TestResultsFilters({
  filters,
  onFiltersChange,
  projectEndpoints,
  endpointsLoading,
  requirementOptions,
  searchQuery,
  onSearchChange,
  showExpandToggle = false,
  allExpanded = false,
  onToggleAll,
  variant = 'full',
  filterDrawerOpen: controlledDrawerOpen,
  onFilterDrawerOpenChange,
}: TestResultsFiltersProps) {
  const isCompact = variant === 'compact';
  const [uncontrolledDrawerOpen, setUncontrolledDrawerOpen] = useState(false);
  const filterDrawerOpen = controlledDrawerOpen ?? uncontrolledDrawerOpen;
  const setFilterDrawerOpen = (open: boolean) => {
    setUncontrolledDrawerOpen(open);
    onFilterDrawerOpenChange?.(open);
  };

  const drawerFilters = useMemo<InsightsDrawerFilters>(
    () => ({
      endpointId: filters.endpointId,
      requirementIds: filters.requirementIds,
      impactIds: filters.impactIds,
      statusIds: filters.statusIds,
      timeRange: filters.timeRange,
      testRunIds: filters.testRunIds,
    }),
    [
      filters.endpointId,
      filters.requirementIds,
      filters.impactIds,
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
      requirementIds: next.requirementIds,
      impactIds: next.impactIds,
      statusIds: next.statusIds,
      timeRange: next.timeRange,
      testRunIds: next.testRunIds,
    });
  };

  const hasActiveFilters = hasActiveInsightsDrawerFilters(drawerFilters);

  // Group-by is a view choice, not a filter, so a reset leaves it alone.
  const handleResetAllFilters = () => {
    onFiltersChange({ ...DEFAULT_INSIGHTS_FILTERS, groupBy: filters.groupBy });
  };

  const handleGroupByChange = (value: string) => {
    onFiltersChange({ ...filters, groupBy: value as InsightsGroupBy });
  };

  return (
    <>
      <GridToolbar
        searchQuery={searchQuery}
        onSearchChange={onSearchChange}
        searchPlaceholder="Search requirements…"
        showSearch={!isCompact}
        onFilterClick={() => setFilterDrawerOpen(true)}
        hasActiveFilters={hasActiveFilters}
        activeFilterCount={countActiveInsightsDrawerFilters(drawerFilters)}
        {...directoryToolbarProps}
        middleContent={
          <Box
            sx={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              flexWrap: 'wrap',
            }}
          >
            <Box role="group" aria-label="Group by">
              <ToolbarPillTabs
                tabs={INSIGHTS_GROUP_BY_OPTIONS}
                activeValue={filters.groupBy}
                onChange={handleGroupByChange}
              />
            </Box>
            {!isCompact && showExpandToggle && onToggleAll ? (
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
        }
      />

      <InsightsFilterDrawer
        open={filterDrawerOpen}
        onClose={() => setFilterDrawerOpen(false)}
        filters={drawerFilters}
        projectEndpoints={projectEndpoints}
        endpointsLoading={endpointsLoading}
        requirementOptions={requirementOptions}
        onApply={handleDrawerApply}
      />
    </>
  );
}
