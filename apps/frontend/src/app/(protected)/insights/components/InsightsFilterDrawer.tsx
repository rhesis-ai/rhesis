'use client';

import * as React from 'react';
import { useSession } from 'next-auth/react';
import { FormControl, InputLabel, MenuItem, Select } from '@mui/material';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';
import {
  FilterDrawerShell,
  FilterSection,
  filterDrawerSelectSx,
  useFilterDrawerDraft,
} from '@/components/common/FilterDrawer';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { EntityType } from '@/types/entity-type';
import { useStatuses } from '@/hooks/useLookups';
import {
  DEFAULT_INSIGHTS_TIME_RANGE,
  InsightsFilters,
  InsightsTimeRange,
  resolveInsightsTimeRange,
} from '../types';
import { fetchTestRunsForEndpoint } from '../utils/behavior-insights-utils';
import {
  checkedIdsFromFilter,
  checkedIdsFromOptionalFilter,
  formatInsightsTestRunLabel,
  idsFromCheckedSelection,
  idsFromCheckedSelectionOptional,
  InsightsBehaviorOption,
  InsightsTestRunOption,
  isOptionalFilterActive,
  isRunFilterActive,
} from '../utils/insights-filter-utils';
import InsightsBehaviorFilterSection from './InsightsBehaviorFilterSection';
import InsightsStatusFilterSection from './InsightsStatusFilterSection';
import InsightsTestRunFilterSection from './InsightsTestRunFilterSection';
import InsightsTimeRangeFilterSection from './InsightsTimeRangeFilterSection';

export type InsightsDrawerFilters = Pick<
  InsightsFilters,
  'endpointId' | 'behaviorIds' | 'statusIds' | 'timeRange' | 'testRunIds'
>;

export const EMPTY_INSIGHTS_DRAWER_FILTERS: InsightsDrawerFilters = {
  endpointId: '',
  behaviorIds: null,
  statusIds: null,
  timeRange: DEFAULT_INSIGHTS_TIME_RANGE,
  testRunIds: [],
};

export function hasActiveInsightsDrawerFilters(
  f: InsightsDrawerFilters
): boolean {
  return (
    f.endpointId !== '' ||
    isOptionalFilterActive(f.behaviorIds) ||
    isOptionalFilterActive(f.statusIds) ||
    isRunFilterActive(f)
  );
}

export function countActiveInsightsDrawerFilters(
  f: InsightsDrawerFilters
): number {
  let count = f.endpointId !== '' ? 1 : 0;
  if (isOptionalFilterActive(f.behaviorIds)) {
    count += 1;
  }
  if (isOptionalFilterActive(f.statusIds)) {
    count += 1;
  }
  if (isRunFilterActive(f)) {
    count += 1;
  }
  return count;
}

const selectSx = filterDrawerSelectSx;

interface InsightsFilterDrawerProps {
  open: boolean;
  onClose: () => void;
  filters: InsightsDrawerFilters;
  projectEndpoints: Endpoint[];
  endpointsLoading: boolean;
  behaviorOptions: InsightsBehaviorOption[];
  onApply: (filters: InsightsDrawerFilters) => void;
}

export default function InsightsFilterDrawer({
  open,
  onClose,
  filters,
  projectEndpoints,
  endpointsLoading,
  behaviorOptions,
  onApply,
}: InsightsFilterDrawerProps) {
  const { status } = useSession();
  const { draft, setDraft, handleReset, handleApply } = useFilterDrawerDraft(
    open,
    filters,
    EMPTY_INSIGHTS_DRAWER_FILTERS,
    onApply,
    onClose
  );

  const [testRunOptions, setTestRunOptions] = React.useState<
    InsightsTestRunOption[]
  >([]);
  const [testRunsLoading, setTestRunsLoading] = React.useState(false);

  const { data: statuses = [] } = useStatuses(EntityType.TEST_RESULT, open);

  const allBehaviorIds = React.useMemo(
    () => behaviorOptions.map(option => option.id),
    [behaviorOptions]
  );

  const allTestRunIds = React.useMemo(
    () => testRunOptions.map(option => option.id),
    [testRunOptions]
  );

  const allStatusIds = React.useMemo(
    () => statuses.map(option => option.id),
    [statuses]
  );

  const checkedBehaviorIds = React.useMemo(
    () => checkedIdsFromOptionalFilter(allBehaviorIds, draft.behaviorIds),
    [allBehaviorIds, draft.behaviorIds]
  );

  const checkedTestRunIds = React.useMemo(
    () => checkedIdsFromFilter(allTestRunIds, draft.testRunIds),
    [allTestRunIds, draft.testRunIds]
  );

  const checkedStatusIds = React.useMemo(
    () => checkedIdsFromOptionalFilter(allStatusIds, draft.statusIds),
    [allStatusIds, draft.statusIds]
  );

  React.useEffect(() => {
    if (!open || !isAuthenticated(status) || !draft.endpointId) {
      if (!open) {
        setTestRunOptions([]);
      }
      setTestRunsLoading(false);
      return;
    }

    let cancelled = false;
    setTestRunsLoading(true);

    void (async () => {
      try {
        const allRuns = await fetchTestRunsForEndpoint(
          draft.endpointId,
          resolveInsightsTimeRange(draft.timeRange)
        );

        if (cancelled) return;

        const newOptions = allRuns.map(run => ({
          id: run.id,
          label: formatInsightsTestRunLabel(run),
        }));
        setTestRunOptions(newOptions);
        // Drop any previously-checked runs that fell out of the new
        // time-range window, so an unchanged Apply doesn't silently submit
        // runs outside the currently displayed scope.
        setDraft(prev =>
          prev.testRunIds.length === 0
            ? prev
            : {
                ...prev,
                testRunIds: prev.testRunIds.filter(id =>
                  newOptions.some(option => option.id === id)
                ),
              }
        );
      } catch {
        if (!cancelled) {
          setTestRunOptions([]);
        }
      } finally {
        if (!cancelled) {
          setTestRunsLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [open, status, draft.endpointId, draft.timeRange, setDraft]);

  const handleCheckedBehaviorIdsChange = React.useCallback(
    (checkedIds: string[]) => {
      setDraft(prev => ({
        ...prev,
        behaviorIds: idsFromCheckedSelectionOptional(
          allBehaviorIds,
          checkedIds
        ),
      }));
    },
    [allBehaviorIds, setDraft]
  );

  const handleCheckedTestRunIdsChange = React.useCallback(
    (checkedIds: string[]) => {
      setDraft(prev => ({
        ...prev,
        testRunIds: idsFromCheckedSelection(allTestRunIds, checkedIds),
      }));
    },
    [allTestRunIds, setDraft]
  );

  const handleCheckedStatusIdsChange = React.useCallback(
    (checkedIds: string[]) => {
      setDraft(prev => ({
        ...prev,
        statusIds: idsFromCheckedSelectionOptional(allStatusIds, checkedIds),
      }));
    },
    [allStatusIds, setDraft]
  );

  const handleTimeRangeChange = React.useCallback(
    (timeRange: InsightsTimeRange) => {
      setDraft(prev => ({ ...prev, timeRange }));
    },
    [setDraft]
  );

  const handleEndpointChange = React.useCallback(
    (endpointId: string) => {
      setDraft(prev => ({
        ...prev,
        endpointId,
        testRunIds: [],
        timeRange: DEFAULT_INSIGHTS_TIME_RANGE,
      }));
    },
    [setDraft]
  );

  return (
    <FilterDrawerShell
      open={open}
      onClose={onClose}
      onReset={handleReset}
      onApply={handleApply}
    >
      <FilterSection title="Endpoint">
        <FormControl
          fullWidth
          size="small"
          disabled={endpointsLoading || projectEndpoints.length === 0}
        >
          <InputLabel id="insights-filter-endpoint-label">Endpoint</InputLabel>
          <Select
            labelId="insights-filter-endpoint-label"
            value={draft.endpointId || ''}
            label="Endpoint"
            onChange={e => handleEndpointChange(e.target.value)}
            sx={selectSx}
          >
            {projectEndpoints.map(endpoint => (
              <MenuItem key={endpoint.id} value={endpoint.id}>
                {endpoint.name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </FilterSection>

      <InsightsTimeRangeFilterSection
        timeRange={draft.timeRange}
        onTimeRangeChange={handleTimeRangeChange}
        disabled={!draft.endpointId}
      />

      <InsightsTestRunFilterSection
        options={testRunOptions}
        checkedIds={checkedTestRunIds}
        onCheckedIdsChange={handleCheckedTestRunIdsChange}
        loading={testRunsLoading}
        disabled={!draft.endpointId}
      />

      <InsightsBehaviorFilterSection
        options={behaviorOptions}
        checkedIds={checkedBehaviorIds}
        onCheckedIdsChange={handleCheckedBehaviorIdsChange}
      />

      <InsightsStatusFilterSection
        options={statuses}
        checkedIds={checkedStatusIds}
        onCheckedIdsChange={handleCheckedStatusIdsChange}
      />
    </FilterDrawerShell>
  );
}
