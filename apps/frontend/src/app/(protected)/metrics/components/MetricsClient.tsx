'use client';

import * as React from 'react';
import { useSession } from 'next-auth/react';
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
import { METRICS_SELECT } from './metrics-constants';

import MetricsDirectoryTab, { type FilterState } from './MetricsDirectoryTab';
import { isAuthenticated, isSessionLoading } from '@/hooks/useIsAuthenticated';

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

/**
 * Extracts the behavior/backend/type dropdown options a page of metrics
 * contributes. Used both to seed state from the server-fetched first page
 * and to update state after each subsequent client-side fetch.
 */
function deriveMetricsPageOptions(
  data: MetricDetail[],
  behaviorMap: Map<string, ApiBehavior>
) {
  data.forEach(metric => {
    metric.behaviors?.forEach(behavior => {
      if (behavior && typeof behavior !== 'string' && behavior.id) {
        behaviorMap.set(behavior.id, {
          id: behavior.id,
          name: behavior.name || 'Unnamed Behavior',
          description: behavior.description ?? undefined,
        } as ApiBehavior);
      }
    });
  });
  const behaviorsData = Array.from(behaviorMap.values());
  const behaviorOptions = behaviorsData.map(b => ({ id: b.id, name: b.name }));

  const uniqueBackendTypes = new Map<string, { type_value: string }>();
  const uniqueMetricTypes = new Map<
    string,
    { type_value: string; description: string }
  >();

  data.forEach(metric => {
    if (metric.backend_type) {
      const val = metric.backend_type.type_value;
      uniqueBackendTypes.set(val, {
        type_value: val.charAt(0).toUpperCase() + val.slice(1),
      });
    }
    if (metric.metric_type) {
      uniqueMetricTypes.set(metric.metric_type.type_value, {
        type_value: metric.metric_type.type_value,
        description: metric.metric_type.description || '',
      });
    }
  });

  return { behaviorsData, behaviorOptions, uniqueBackendTypes, uniqueMetricTypes };
}

export default function MetricsClientComponent({
  organizationId,
  initialData,
  initialTotalCount = 0,
}: MetricsClientProps) {
  const searchParams = useSearchParams();
  const notifications = useNotifications();
  const { status: sessionStatus } = useSession();

  const assignMode = searchParams.get('assignMode') === 'true';

  // Accumulate unique behaviors across page navigations for the dropdown
  const behaviorMapRef = React.useRef(new Map<string, ApiBehavior>());

  // Data state — seeded from the server-fetched first page when available
  const [behaviors, setBehaviors] = React.useState<ApiBehavior[]>(() =>
    initialData
      ? deriveMetricsPageOptions(initialData, behaviorMapRef.current)
          .behaviorsData
      : []
  );
  const [_behaviorsWithMetrics, setBehaviorsWithMetrics] = React.useState<
    BehaviorWithMetrics[]
  >([]);
  const [metrics, setMetrics] = React.useState<MetricDetail[]>(
    initialData ?? []
  );
  const [totalCount, setTotalCount] = React.useState(initialTotalCount);

  // Loading / error — no initial spinner when the server already provided data
  const [isLoading, setIsLoading] = React.useState(initialData === undefined);
  const [error, setError] = React.useState<string | null>(null);

  // Filter state
  const [filters, setFilters] = React.useState<FilterState>(initialFilterState);
  const [filterOptions, setFilterOptions] = React.useState<FilterOptions>(
    () => {
      if (!initialData) return initialFilterOptions;
      const { behaviorOptions, uniqueBackendTypes, uniqueMetricTypes } =
        deriveMetricsPageOptions(initialData, behaviorMapRef.current);
      return {
        ...initialFilterOptions,
        backend:
          uniqueBackendTypes.size > 0
            ? Array.from(uniqueBackendTypes.values())
            : initialFilterOptions.backend,
        type:
          uniqueMetricTypes.size > 0
            ? Array.from(uniqueMetricTypes.values())
            : initialFilterOptions.type,
        behavior:
          behaviorOptions.length > 0
            ? behaviorOptions
            : initialFilterOptions.behavior,
      };
    }
  );
  const [_behaviorMetrics, setBehaviorMetrics] =
    React.useState<BehaviorMetrics>({});

  // Pagination (owned here so filter/page changes trigger a single re-fetch)
  const [page, setPage] = React.useState(0);
  const [rowsPerPage, setRowsPerPage] = React.useState(25);
  const [refreshKey, setRefreshKey] = React.useState(0);

  // Reset page to 0 whenever filters change
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

  // Identifies the request whose result is currently reflected in `metrics`/
  // `totalCount`. Seeded with the server-fetched first page's signature
  // (page 0, default size, no filters, refreshKey 0 -- exactly what `page`/
  // `rowsPerPage`/`filterFingerprint`/`refreshKey` hold on this first render)
  // when the server provided initial data. The fetch effect below compares
  // against this on every run rather than consuming a one-shot flag, so it
  // stays correct under React 18 Strict Mode's dev-only double-invoke of
  // mount effects -- both invocations compute the same signature and both
  // no-op, instead of the second one slipping through a "consumed" ref.
  const loadedRequestKeyRef = React.useRef<string | null>(
    initialData !== undefined
      ? `${page}|${rowsPerPage}|${filterFingerprint}|${refreshKey}`
      : null
  );

  React.useEffect(() => {
    setPage(0);
  }, [filterFingerprint]);

  // Main data-fetching effect — runs on page, rowsPerPage, or filter change
  React.useEffect(() => {
    const requestKey = `${page}|${rowsPerPage}|${filterFingerprint}|${refreshKey}`;
    if (loadedRequestKeyRef.current === requestKey) {
      return;
    }
    loadedRequestKeyRef.current = requestKey;

    let cancelled = false;

    const fetchData = async () => {
      if (!isAuthenticated(sessionStatus)) {
        if (!isSessionLoading(sessionStatus)) {
          setIsLoading(false);
        }
        return;
      }

      try {
        setIsLoading(true);
        setError(null);

        const metricsClient = new MetricsClient();
        const odataFilter = buildMetricODataFilter(filters);

        const response = await metricsClient.getMetrics({
          skip: page * rowsPerPage,
          limit: rowsPerPage,
          sort_by: 'created_at',
          sort_order: 'desc',
          $filter: odataFilter,
          $select: METRICS_SELECT,
          ...(filters.metricScope.length > 0 && {
            metric_scope: filters.metricScope.join(','),
          }),
        });

        if (cancelled) return;

        setMetrics(response.data);
        setTotalCount(response.pagination.totalCount);

        const { behaviorsData, behaviorOptions, uniqueBackendTypes, uniqueMetricTypes } =
          deriveMetricsPageOptions(response.data, behaviorMapRef.current);
        setBehaviors(behaviorsData);

        setFilterOptions(prev => ({
          ...prev,
          backend:
            uniqueBackendTypes.size > 0
              ? Array.from(uniqueBackendTypes.values())
              : prev.backend,
          type:
            uniqueMetricTypes.size > 0
              ? Array.from(uniqueMetricTypes.values())
              : prev.type,
          behavior:
            behaviorOptions.length > 0 ? behaviorOptions : prev.behavior,
        }));
      } catch (err) {
        if (cancelled) return;
        const errorMessage =
          err instanceof Error ? err.message : 'An error occurred';
        setError(errorMessage);
        notifications.show('Failed to load metrics data', {
          severity: 'error',
          autoHideDuration: 4000,
        });
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    fetchData();
    return () => {
      cancelled = true;
    };
    // filterFingerprint captures all filter state; no need to list individual fields
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, rowsPerPage, filterFingerprint, refreshKey, sessionStatus, notifications]);

  // Clamp page when the result set shrinks below the current page (e.g. after delete)
  React.useEffect(() => {
    if (totalCount === 0) return;
    const lastPage = Math.max(0, Math.ceil(totalCount / rowsPerPage) - 1);
    if (page > lastPage) {
      setPage(lastPage);
    }
  }, [totalCount, rowsPerPage, page]);

  const handleRefresh = React.useCallback(() => {
    setRefreshKey(prev => prev + 1);
  }, []);

  const handlePageChange = React.useCallback((newPage: number) => {
    setPage(newPage);
  }, []);

  const handleRowsPerPageChange = React.useCallback((newSize: number) => {
    setRowsPerPage(newSize);
    setPage(0);
  }, []);

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
