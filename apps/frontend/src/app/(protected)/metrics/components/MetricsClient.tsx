'use client';

import * as React from 'react';
import { useSearchParams } from 'next/navigation';
import { useNotifications } from '@/components/common/NotificationContext';
import ErrorBoundary from '@/components/common/ErrorBoundary';
import { MetricsClient } from '@/utils/api-client/metrics-client';
import { MetricDetail } from '@/utils/api-client/interfaces/metric';
import type {
  Behavior as ApiBehavior,
  BehaviorWithMetrics,
} from '@/utils/api-client/interfaces/behavior';
import type { UUID } from 'crypto';
import { TEST_TYPES } from '@/constants/test-types';
import { buildMetricODataFilter } from '@/utils/odata-filter';
import { METRICS_SELECT, METRICS_READ_CAPABILITY } from './metrics-constants';
import { useCanWithStatus } from '@/components/common/Can';
import AccessDenied from '@/components/common/AccessDenied';
import PageLoadingState from '@/components/common/PageLoadingState';
import { usePaginatedList } from '@/hooks/usePaginatedList';

import MetricsDirectoryTab, { type FilterState } from './MetricsDirectoryTab';

const initialFilterState: FilterState = {
  search: '',
  backend: [],
  type: [],
  scoreType: [],
  metricScope: [],
  behavior: '',
};

interface FilterOptions {
  backend: { type_value: string }[];
  type: { type_value: string; description: string }[];
  scoreType: { value: string; label: string }[];
  metricScope: { value: string; label: string }[];
  behavior: { id: string; name: string }[];
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
  behavior: [],
};

interface BehaviorMetrics {
  [behaviorId: string]: {
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

interface MetricsOptionMaps {
  behaviors: Map<string, ApiBehavior>;
  backendTypes: Map<string, { type_value: string }>;
  metricTypes: Map<string, { type_value: string; description: string }>;
}

/**
 * Extracts the behavior/backend/type dropdown options a page of metrics
 * contributes and merges them into the running accumulator maps. Mutating
 * maps that persist across fetches -- rather than deriving from just the
 * current page -- matters because pages are server-filtered: filtering by
 * one backend type would otherwise make that fetch's response (and thus the
 * dropdown) contain only that value, making every other option vanish from
 * the filter UI the moment it's applied.
 */
function deriveMetricsPageOptions(
  data: MetricDetail[],
  maps: MetricsOptionMaps
) {
  data.forEach(metric => {
    metric.behaviors?.forEach(behavior => {
      if (behavior && typeof behavior !== 'string' && behavior.id) {
        maps.behaviors.set(behavior.id, {
          id: behavior.id,
          name: behavior.name || 'Unnamed Behavior',
          description: behavior.description ?? undefined,
        } as ApiBehavior);
      }
    });
    if (metric.backend_type) {
      const val = metric.backend_type.type_value;
      maps.backendTypes.set(val, {
        type_value: val.charAt(0).toUpperCase() + val.slice(1),
      });
    }
    if (metric.metric_type) {
      maps.metricTypes.set(metric.metric_type.type_value, {
        type_value: metric.metric_type.type_value,
        description: metric.metric_type.description || '',
      });
    }
  });

  const behaviorsData = Array.from(maps.behaviors.values());
  return {
    behaviorsData,
    behaviorOptions: behaviorsData.map(b => ({ id: b.id, name: b.name })),
    backendTypeOptions: Array.from(maps.backendTypes.values()),
    metricTypeOptions: Array.from(maps.metricTypes.values()),
  };
}

export default function MetricsClientComponent({
  organizationId,
  initialData,
  initialTotalCount = 0,
}: MetricsClientProps) {
  const searchParams = useSearchParams();
  const notifications = useNotifications();
  const { allowed: canRead, loading: permsLoading } = useCanWithStatus(
    METRICS_READ_CAPABILITY
  );

  const assignMode = searchParams.get('assignMode') === 'true';

  // Accumulate dropdown options across page/filter navigations (see
  // deriveMetricsPageOptions) so filtering to one value doesn't erase the
  // other options from the dropdowns.
  const optionMapsRef = React.useRef<MetricsOptionMaps>({
    behaviors: new Map(),
    backendTypes: new Map(),
    metricTypes: new Map(),
  });

  const [behaviors, setBehaviors] = React.useState<ApiBehavior[]>(() =>
    initialData
      ? deriveMetricsPageOptions(initialData, optionMapsRef.current)
          .behaviorsData
      : []
  );
  const [_behaviorsWithMetrics, setBehaviorsWithMetrics] = React.useState<
    BehaviorWithMetrics[]
  >([]);

  // Filter state
  const [filters, setFilters] = React.useState<FilterState>(initialFilterState);
  const [filterOptions, setFilterOptions] = React.useState<FilterOptions>(
    () => {
      if (!initialData) return initialFilterOptions;
      const { behaviorOptions, backendTypeOptions, metricTypeOptions } =
        deriveMetricsPageOptions(initialData, optionMapsRef.current);
      return {
        ...initialFilterOptions,
        backend: backendTypeOptions,
        type: metricTypeOptions,
        behavior: behaviorOptions,
      };
    }
  );
  const [_behaviorMetrics, setBehaviorMetrics] =
    React.useState<BehaviorMetrics>({});

  const filterFingerprint = React.useMemo(
    () =>
      JSON.stringify([
        filters.search,
        filters.backend,
        filters.type,
        filters.scoreType,
        filters.metricScope,
        filters.behavior,
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
        sort_by: 'created_at',
        sort_order: 'desc',
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
    onData: data => {
      const {
        behaviorsData,
        behaviorOptions,
        backendTypeOptions,
        metricTypeOptions,
      } = deriveMetricsPageOptions(data, optionMapsRef.current);
      setBehaviors(behaviorsData);

      setFilterOptions(prev => ({
        ...prev,
        backend: backendTypeOptions,
        type: metricTypeOptions,
        behavior: behaviorOptions,
      }));
    },
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
        behaviors={behaviors}
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
        setBehaviorMetrics={setBehaviorMetrics}
        setBehaviorsWithMetrics={setBehaviorsWithMetrics}
        assignMode={assignMode}
      />
    </ErrorBoundary>
  );
}
