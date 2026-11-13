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
import { fetchTestRunsForEndpoint } from '../utils/requirement-insights-utils';
import {
  checkedIdsFromFilter,
  checkedIdsFromOptionalFilter,
  formatInsightsTestRunLabel,
  idsFromCheckedSelection,
  idsFromCheckedSelectionOptional,
  InsightsRequirementOption,
  InsightsTestRunOption,
  isOptionalFilterActive,
  isRunFilterActive,
} from '../utils/insights-filter-utils';
import { useRequirementImpacts } from '@/app/(protected)/requirements/components/requirement-lookups';
import InsightsImpactFilterSection from './InsightsImpactFilterSection';
import InsightsRequirementFilterSection from './InsightsRequirementFilterSection';
import InsightsStatusFilterSection from './InsightsStatusFilterSection';
import InsightsTestRunFilterSection from './InsightsTestRunFilterSection';
import InsightsTimeRangeFilterSection from './InsightsTimeRangeFilterSection';

export type InsightsDrawerFilters = Pick<
  InsightsFilters,
  | 'endpointId'
  | 'requirementIds'
  | 'impactIds'
  | 'statusIds'
  | 'timeRange'
  | 'testRunIds'
>;

export const EMPTY_INSIGHTS_DRAWER_FILTERS: InsightsDrawerFilters = {
  endpointId: '',
  requirementIds: null,
  impactIds: null,
  statusIds: null,
  timeRange: DEFAULT_INSIGHTS_TIME_RANGE,
  testRunIds: [],
};

export function hasActiveInsightsDrawerFilters(
  f: InsightsDrawerFilters
): boolean {
  return (
    f.endpointId !== '' ||
    isOptionalFilterActive(f.requirementIds) ||
    isOptionalFilterActive(f.impactIds) ||
    isOptionalFilterActive(f.statusIds) ||
    isRunFilterActive(f)
  );
}

export function countActiveInsightsDrawerFilters(
  f: InsightsDrawerFilters
): number {
  let count = f.endpointId !== '' ? 1 : 0;
  if (isOptionalFilterActive(f.requirementIds)) {
    count += 1;
  }
  if (isOptionalFilterActive(f.impactIds)) {
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
  requirementOptions: InsightsRequirementOption[];
  onApply: (filters: InsightsDrawerFilters) => void;
}

export default function InsightsFilterDrawer({
  open,
  onClose,
  filters,
  projectEndpoints,
  endpointsLoading,
  requirementOptions,
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
  const { data: impactOptions = [] } = useRequirementImpacts(open);

  const allRequirementIds = React.useMemo(
    () => requirementOptions.map(option => option.id),
    [requirementOptions]
  );

  const allImpactIds = React.useMemo(
    () => impactOptions.map(option => String(option.id)),
    [impactOptions]
  );

  const allTestRunIds = React.useMemo(
    () => testRunOptions.map(option => option.id),
    [testRunOptions]
  );

  const allStatusIds = React.useMemo(
    () => statuses.map(option => option.id),
    [statuses]
  );

  const checkedRequirementIds = React.useMemo(
    () => checkedIdsFromOptionalFilter(allRequirementIds, draft.requirementIds),
    [allRequirementIds, draft.requirementIds]
  );

  const checkedTestRunIds = React.useMemo(
    () => checkedIdsFromFilter(allTestRunIds, draft.testRunIds),
    [allTestRunIds, draft.testRunIds]
  );

  const checkedStatusIds = React.useMemo(
    () => checkedIdsFromOptionalFilter(allStatusIds, draft.statusIds),
    [allStatusIds, draft.statusIds]
  );

  const checkedImpactIds = React.useMemo(
    () => checkedIdsFromOptionalFilter(allImpactIds, draft.impactIds),
    [allImpactIds, draft.impactIds]
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

  const handleCheckedRequirementIdsChange = React.useCallback(
    (checkedIds: string[]) => {
      setDraft(prev => ({
        ...prev,
        requirementIds: idsFromCheckedSelectionOptional(
          allRequirementIds,
          checkedIds
        ),
      }));
    },
    [allRequirementIds, setDraft]
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

  const handleCheckedImpactIdsChange = React.useCallback(
    (checkedIds: string[]) => {
      setDraft(prev => ({
        ...prev,
        impactIds: idsFromCheckedSelectionOptional(allImpactIds, checkedIds),
      }));
    },
    [allImpactIds, setDraft]
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

      <InsightsImpactFilterSection
        options={impactOptions}
        checkedIds={checkedImpactIds}
        onCheckedIdsChange={handleCheckedImpactIdsChange}
      />

      <InsightsRequirementFilterSection
        options={requirementOptions}
        checkedIds={checkedRequirementIds}
        onCheckedIdsChange={handleCheckedRequirementIdsChange}
      />

      <InsightsStatusFilterSection
        options={statuses}
        checkedIds={checkedStatusIds}
        onCheckedIdsChange={handleCheckedStatusIdsChange}
      />
    </FilterDrawerShell>
  );
}
