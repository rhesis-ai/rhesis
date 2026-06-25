'use client';

import React, { useMemo, useState } from 'react';
import { Box, Button } from '@mui/material';
import GridToolbar, {
  ToolbarPillTabs,
  directoryToolbarProps,
} from '@/components/common/GridToolbar';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { writeInsightsEndpointId } from '@/utils/insights-endpoint';
import {
  INSIGHTS_TIME_RANGE_OPTIONS,
  InsightsFilters,
  InsightsTimeRange,
  resolveInsightsTimeRange,
} from '../types';
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
}: TestResultsFiltersProps) {
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);

  const drawerFilters = useMemo<InsightsDrawerFilters>(
    () => ({
      endpointId: filters.endpointId,
      behaviorIds: filters.behaviorIds,
    }),
    [filters.endpointId, filters.behaviorIds]
  );

  const handleTimeRangeChange = (value: string) => {
    onFiltersChange({
      ...filters,
      timeRange: value as InsightsTimeRange,
    });
  };

  const handleDrawerApply = (next: InsightsDrawerFilters) => {
    if (next.endpointId) {
      writeInsightsEndpointId(next.endpointId);
    }
    onFiltersChange({
      ...filters,
      endpointId: next.endpointId,
      behaviorIds: next.behaviorIds,
    });
  };

  return (
    <>
      <GridToolbar
        searchQuery={searchQuery}
        onSearchChange={onSearchChange}
        searchPlaceholder="Search behaviors…"
        onFilterClick={() => setFilterDrawerOpen(true)}
        hasActiveFilters={hasActiveInsightsDrawerFilters(drawerFilters)}
        activeFilterCount={countActiveInsightsDrawerFilters(drawerFilters)}
        {...directoryToolbarProps}
        middleContent={
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              flexWrap: 'wrap',
            }}
          >
            <ToolbarPillTabs
              tabs={INSIGHTS_TIME_RANGE_OPTIONS}
              activeValue={resolveInsightsTimeRange(filters.timeRange)}
              onChange={handleTimeRangeChange}
            />
            {showExpandToggle && onToggleAll && (
              <Button size="small" variant="text" onClick={onToggleAll}>
                {allExpanded ? 'Collapse all' : 'Expand all'}
              </Button>
            )}
          </Box>
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
