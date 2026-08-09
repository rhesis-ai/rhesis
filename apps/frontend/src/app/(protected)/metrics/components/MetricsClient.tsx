'use client';

import * as React from 'react';
import { useSearchParams } from 'next/navigation';
import { useNotifications } from '@/components/common/NotificationContext';
import ErrorBoundary from '@/components/common/ErrorBoundary';
import { MetricsClient } from '@/utils/api-client/metrics-client';
import { MetricDetail } from '@/utils/api-client/interfaces/metric';
import type {
  Requirement as ApiRequirement,
  RequirementWithMetrics,
} from '@/utils/api-client/interfaces/requirement';
import type { UUID } from 'crypto';
import { TEST_TYPES } from '@/constants/test-types';
import { buildMetricODataFilter } from '@/utils/odata-filter';
import { METRICS_SELECT } from './metrics-constants';
import { useCanWithStatus } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import AccessDenied from '@/components/common/AccessDenied';
import PageLoadingState from '@/components/common/PageLoadingState';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { useTypeLookups, useRequirements } from '@/hooks/useLookups';

import MetricsDirectoryTab, { type FilterState } from './MetricsDirectoryTab';

const initialFilterState: FilterState = {
  search: '',
  backend: [],
  type: [],
  scoreType: [],
  metricScope: [],
  requirement: '',
};

interface FilterOptions {
  backend: { type_value: string }[];
  type: { type_value: string; description: string }[];
  scoreType: { value: string; label: string }[];
  metricScope: { value: string; label: string }[];
  requirement: { id: string; name: string }[];
}

const initialFilterOptions: FilterOptions = {
  backend: [],
  type: [],
  scoreType: [
    { value: 'numeric', label: 'Numeric' },
    { value: 'categorical', label: 'Categorical' },
  ],
  metricScope: [
    { value: TEST_TYPES.SINGLE_TURN, label: TEST_TYPES.SINGLE_TURN },
    { value: TEST_TYPES.MULTI_TURN, label: TEST_TYPES.MULTI_TURN },
    { value: 'Trace', label: 'Trace' },
  ],
  requirement: [],
};

interface RequirementMetrics {
  [requirementId: string]: {
    metrics: MetricDetail[];
    isLoading: boolean;
    error: string | null;
  };
}

interface MetricsClientProps {
  organizationId: UUID;
  /** Server-fetched first page — when present, skips the initial client fetch. */
  initialData?: MetricDetail[];
  initialTotalCount?: number;
}

export default function MetricsClientComponent({
  organizationId,
  initialData,
  initialTotalCount = 0,
}: MetricsClientProps) {
  const searchParams = useSearchParams();
  const notifications = useNotifications();
  const { allowed: canRead, loading: permsLoading } = useCanWithStatus(
    Capability.Metric.READ
  );

  const assignMode = searchParams.get('assignMode') === 'true';

  const lookupEnabled = !permsLoading && canRead;
  const { data: backendTypes = [] } = useTypeLookups(
    "type_name eq 'BackendType'",
    lookupEnabled
  );
  const { data: metricTypes = [] } = useTypeLookups(
    "type_name eq 'MetricType'",
    lookupEnabled
  );
  const { data: allRequirements = [] } = useRequirements(lookupEnabled);

  const requirements = React.useMemo<ApiRequirement[]>(
    () => allRequirements as ApiRequirement[],
    [allRequirements]
  );

  const [_requirementsWithMetrics, setRequirementsWithMetrics] = React.useState<
    RequirementWithMetrics[]
  >([]);

  // Filter state
  const [filters, setFilters] = React.useState<FilterState>(initialFilterState);

  const filterOptions = React.useMemo<FilterOptions>(
    () => ({
      ...initialFilterOptions,
      backend: backendTypes.map(t => ({
        type_value:
          t.type_value.charAt(0).toUpperCase() + t.type_value.slice(1),
      })),
      type: metricTypes.map(t => ({
        type_value: t.type_value,
        description: t.description || '',
      })),
      requirement: allRequirements
        .filter(b => b.name?.trim())
        .map(b => ({ id: b.id, name: b.name })),
    }),
    [backendTypes, metricTypes, allRequirements]
  );

  const [_requirementMetrics, setRequirementMetrics] =
    React.useState<RequirementMetrics>({});

  const filterFingerprint = React.useMemo(
    () =>
      JSON.stringify([
        filters.search,
        filters.backend,
        filters.type,
        filters.scoreType,
        filters.metricScope,
        filters.requirement,
      ]),
    [filters]
  );

  const {
    data: metrics,
    setData: setMetrics,
    totalCount,
    isLoading,
    error,
    page,
    rowsPerPage,
    onPageChange: handlePageChange,
    onRowsPerPageChange: handleRowsPerPageChange,
    refresh: handleRefresh,
  } = usePaginatedList<MetricDetail>({
    fetchPage: ({ skip, limit }) => {
      const metricsClient = new MetricsClient();
      const odataFilter = buildMetricODataFilter(filters);
      return metricsClient.getMetrics({
        skip,
        limit,
        sort_by: 'name',
        sort_order: 'asc',
        $filter: odataFilter,
        $select: METRICS_SELECT,
        ...(filters.metricScope.length > 0 && {
          metric_scope: filters.metricScope.join(','),
        }),
      });
    },
    filterFingerprint,
    initialData,
    initialTotalCount,
    enabled: !permsLoading && canRead,
    onError: () => {
      notifications.show('Failed to load metrics data', {
        severity: 'error',
        autoHideDuration: 4000,
      });
    },
  });

  if (permsLoading) return <PageLoadingState />;
  if (!canRead) return <AccessDenied resource="metrics" />;

  return (
    <ErrorBoundary>
      <MetricsDirectoryTab
        organizationId={organizationId}
        requirements={requirements}
        metrics={metrics}
        totalCount={totalCount}
        page={page}
        rowsPerPage={rowsPerPage}
        onPageChange={handlePageChange}
        onRowsPerPageChange={handleRowsPerPageChange}
        onRefresh={handleRefresh}
        filters={filters}
        filterOptions={filterOptions}
        isLoading={isLoading}
        error={error}
        setFilters={setFilters}
        setMetrics={setMetrics}
        setRequirementMetrics={setRequirementMetrics}
        setRequirementsWithMetrics={setRequirementsWithMetrics}
        assignMode={assignMode}
      />
    </ErrorBoundary>
  );
}
