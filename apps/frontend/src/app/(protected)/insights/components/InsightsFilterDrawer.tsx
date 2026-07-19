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
import {
  DEFAULT_INSIGHTS_TIME_RANGE,
  InsightsFilters,
  InsightsRunFilterMode,
  InsightsTimeRange,
} from '../types';
import { fetchTestRunsForEndpoint } from '../utils/behavior-insights-utils';
import {
  behaviorIdsFromCheckedSelection,
  checkedBehaviorIdsFromFilter,
  checkedTestRunIdsFromFilter,
  formatInsightsTestRunLabel,
  InsightsBehaviorOption,
  InsightsTestRunOption,
  isRunFilterActive,
  testRunIdsFromCheckedSelection,
} from '../utils/insights-filter-utils';
import InsightsBehaviorFilterSection from './InsightsBehaviorFilterSection';
import InsightsRunFilterSection from './InsightsRunFilterSection';

export type InsightsDrawerFilters = Pick<
  InsightsFilters,
  'endpointId' | 'behaviorIds' | 'runFilterMode' | 'timeRange' | 'testRunIds'
>;

export const EMPTY_INSIGHTS_DRAWER_FILTERS: InsightsDrawerFilters = {
  endpointId: '',
  behaviorIds: [],
  runFilterMode: 'timeRange',
  timeRange: DEFAULT_INSIGHTS_TIME_RANGE,
  testRunIds: [],
};

export function hasActiveInsightsDrawerFilters(
  f: InsightsDrawerFilters
): boolean {
  return (
    f.endpointId !== '' || f.behaviorIds.length > 0 || isRunFilterActive(f)
  );
}

export function countActiveInsightsDrawerFilters(
  f: InsightsDrawerFilters
): number {
  let count = f.endpointId !== '' ? 1 : 0;
  if (f.behaviorIds.length > 0) {
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

  const allBehaviorIds = React.useMemo(
    () => behaviorOptions.map(option => option.id),
    [behaviorOptions]
  );

  const allTestRunIds = React.useMemo(
    () => testRunOptions.map(option => option.id),
    [testRunOptions]
  );

  const checkedBehaviorIds = React.useMemo(
    () => checkedBehaviorIdsFromFilter(allBehaviorIds, draft.behaviorIds),
    [allBehaviorIds, draft.behaviorIds]
  );

  const checkedTestRunIds = React.useMemo(
    () => checkedTestRunIdsFromFilter(allTestRunIds, draft),
    [allTestRunIds, draft]
  );

  React.useEffect(() => {
    if (
      !open ||
      !isAuthenticated(status) ||
      !draft.endpointId ||
      draft.runFilterMode !== 'testRuns'
    ) {
      if (!open || draft.runFilterMode !== 'testRuns') {
        setTestRunOptions([]);
      }
      setTestRunsLoading(false);
      return;
    }

    let cancelled = false;
    setTestRunsLoading(true);

    void (async () => {
      try {
        const allRuns = await fetchTestRunsForEndpoint(draft.endpointId);

        if (cancelled) return;

        setTestRunOptions(
          allRuns.map(run => ({
            id: run.id,
            label: formatInsightsTestRunLabel(run),
          }))
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
  }, [open, status, draft.endpointId, draft.runFilterMode]);

  const handleCheckedBehaviorIdsChange = React.useCallback(
    (checkedIds: string[]) => {
      setDraft(prev => ({
        ...prev,
        behaviorIds: behaviorIdsFromCheckedSelection(
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
        testRunIds: testRunIdsFromCheckedSelection(allTestRunIds, checkedIds),
      }));
    },
    [allTestRunIds, setDraft]
  );

  const handleRunFilterModeChange = React.useCallback(
    (mode: InsightsRunFilterMode) => {
      setDraft(prev => ({
        ...prev,
        runFilterMode: mode,
        ...(mode === 'timeRange'
          ? { testRunIds: [] }
          : { timeRange: DEFAULT_INSIGHTS_TIME_RANGE }),
      }));
    },
    [setDraft]
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
        runFilterMode: 'timeRange',
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

      <InsightsRunFilterSection
        runFilterMode={draft.runFilterMode}
        timeRange={draft.timeRange}
        testRunOptions={testRunOptions}
        checkedTestRunIds={checkedTestRunIds}
        onRunFilterModeChange={handleRunFilterModeChange}
        onTimeRangeChange={handleTimeRangeChange}
        onCheckedTestRunIdsChange={handleCheckedTestRunIdsChange}
        testRunsLoading={testRunsLoading}
        disabled={!draft.endpointId}
      />

      <InsightsBehaviorFilterSection
        options={behaviorOptions}
        checkedIds={checkedBehaviorIds}
        onCheckedIdsChange={handleCheckedBehaviorIdsChange}
      />
    </FilterDrawerShell>
  );
}
