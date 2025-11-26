'use client';

import * as React from 'react';
import Box from '@mui/material/Box';
import { useSearchParams } from 'next/navigation';
import { useNotifications } from '@/components/common/NotificationContext';
import ErrorBoundary from '@/components/common/ErrorBoundary';
import { BehaviorClient } from '@/utils/api-client/behavior-client';
import { MetricsClient } from '@/utils/api-client/metrics-client';
import { MetricDetail } from '@/utils/api-client/interfaces/metric';
import type {
  Behavior as ApiBehavior,
  BehaviorWithMetrics,
} from '@/utils/api-client/interfaces/behavior';
import type { UUID } from 'crypto';

import MetricsDirectoryTab from './MetricsDirectoryTab';

interface FilterState {
  search: string;
  backend: string[];
  type: string[];
  scoreType: string[];
  metricScope: string[];
  behavior: string[];
}

const initialFilterState: FilterState = {
  search: '',
  backend: [],
  type: [],
  scoreType: [],
  metricScope: [],
  behavior: [],
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
    { value: 'Single-Turn', label: 'Single-Turn' },
    { value: 'Multi-Turn', label: 'Multi-Turn' },
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
  sessionToken: string;
  organizationId: UUID;
}

export default function MetricsClientComponent({
  sessionToken,
  organizationId,
}: MetricsClientProps) {
  const searchParams = useSearchParams();
  const notifications = useNotifications();

  // Check if we're in assign mode (coming from behaviors page)
  const assignMode = searchParams.get('assignMode') === 'true';

  // Data state
  const [behaviors, setBehaviors] = React.useState<ApiBehavior[]>([]);
  const [behaviorsWithMetrics, setBehaviorsWithMetrics] = React.useState<
    BehaviorWithMetrics[]
  >([]);
  const [metrics, setMetrics] = React.useState<MetricDetail[]>([]);

  // Loading states
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  // Filter state
  const [filters, setFilters] = React.useState<FilterState>(initialFilterState);
  const [filterOptions, setFilterOptions] =
    React.useState<FilterOptions>(initialFilterOptions);
  const [behaviorMetrics, setBehaviorMetrics] = React.useState<BehaviorMetrics>(
    {}
  );

  // Refresh key for manual refresh
  const [refreshKey, setRefreshKey] = React.useState(0);

  // Use ref to track the actual session token value to prevent unnecessary re-fetches
  const lastSessionTokenRef = React.useRef<string | null>(null);
  const hasFetchedRef = React.useRef(false);

  // Fetch behaviors, metrics, and filter options - using same pattern as test runs
  React.useEffect(() => {
    const fetchData = async () => {
      if (!sessionToken) return;

      // Check if this is a real session token change or just a session object recreation
      const isTokenChange = lastSessionTokenRef.current !== sessionToken;
      const isRefresh = refreshKey > 0;
      const isFirstLoad = !hasFetchedRef.current;

      if (!isTokenChange && !isRefresh && !isFirstLoad) {
        return;
      }

      // Update refs
      lastSessionTokenRef.current = sessionToken;
      hasFetchedRef.current = true;

      try {
        setIsLoading(true);
        setError(null);

        const behaviorClient = new BehaviorClient(sessionToken);
        const metricsClient = new MetricsClient(sessionToken);

        const [behaviorsWithMetricsData, allMetricsData] = await Promise.all([
          behaviorClient.getBehaviorsWithMetrics({
            skip: 0,
            limit: 100,
            sort_by: 'created_at',
            sort_order: 'desc',
          }),
          metricsClient.getMetrics({
            skip: 0,
            limit: 100,
            sort_by: 'created_at',
            sort_order: 'desc',
          }),
        ]);

        // Extract behaviors from the optimized response
        const behaviorsData = behaviorsWithMetricsData;

        // Use all metrics from the dedicated metrics endpoint
        const metricsData = allMetricsData.data || [];

        // Add behavior IDs to each metric for compatibility
        const metricsWithBehaviors = metricsData.map(metric => {
          const behaviorIds = behaviorsWithMetricsData
            .filter(behavior => behavior.metrics?.some(m => m.id === metric.id))
            .map(behavior => behavior.id);

          return {
            ...metric,
            behaviors: behaviorIds,
          };
        });

        // Set the data
        setBehaviorsWithMetrics(behaviorsWithMetricsData);
        setBehaviors(behaviorsData);
        setMetrics(metricsWithBehaviors as MetricDetail[]);

        // Initialize behavior metrics state
        const initialBehaviorMetrics: BehaviorMetrics = {};
        behaviorsWithMetricsData.forEach(behavior => {
          initialBehaviorMetrics[behavior.id] = {
            metrics: (behavior.metrics || []) as MetricDetail[],
            isLoading: false,
            error: null,
          };
        });
        setBehaviorMetrics(initialBehaviorMetrics);

        // Extract backend types and metric types from the metrics in the response
        const uniqueBackendTypes = new Map<string, { type_value: string }>();
        const uniqueMetricTypes = new Map<
          string,
          { type_value: string; description: string }
        >();

        metricsWithBehaviors.forEach(metric => {
          // Extract backend types from metric.backend_type
          if (metric.backend_type) {
            const backendTypeValue =
              metric.backend_type.type_value.charAt(0).toUpperCase() +
              metric.backend_type.type_value.slice(1);
            uniqueBackendTypes.set(metric.backend_type.type_value, {
              type_value: backendTypeValue,
            });
          }

          // Extract metric types from metric.metric_type
          if (metric.metric_type) {
            uniqueMetricTypes.set(metric.metric_type.type_value, {
              type_value: metric.metric_type.type_value,
              description: metric.metric_type.description || '',
            });
          }
        });

        const backendTypes = Array.from(uniqueBackendTypes.values());
        const metricTypes = Array.from(uniqueMetricTypes.values());

        // Create behavior filter options
        const behaviorOptions = behaviorsWithMetricsData.map(behavior => ({
          id: behavior.id,
          name: behavior.name,
        }));

        setFilterOptions(prev => ({
          ...prev,
          backend: backendTypes,
          type: metricTypes,
          behavior: behaviorOptions,
        }));
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'An error occurred';
        setError(errorMessage);
        notifications.show('Failed to load metrics data', {
          severity: 'error',
          autoHideDuration: 4000,
        });
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [sessionToken, refreshKey, notifications]);

  // Refresh data function - trigger re-render by updating a key
  const handleRefresh = React.useCallback(() => {
    setRefreshKey(prev => prev + 1);
  }, []);

  return (
    <ErrorBoundary>
      <Box
        sx={{
          width: '100%',
          minHeight: '100%',
        }}
      >
        <MetricsDirectoryTab
          sessionToken={sessionToken}
          organizationId={organizationId}
          behaviors={behaviors}
          metrics={metrics}
          filters={filters}
          filterOptions={filterOptions}
          isLoading={isLoading}
          error={error}
          onRefresh={handleRefresh}
          setFilters={setFilters}
          setMetrics={setMetrics}
          setBehaviorMetrics={setBehaviorMetrics}
          setBehaviorsWithMetrics={setBehaviorsWithMetrics}
          assignMode={assignMode}
        />
      </Box>
    </ErrorBoundary>
  );
}
