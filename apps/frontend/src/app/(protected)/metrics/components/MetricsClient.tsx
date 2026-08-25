'use client';

import * as React from 'react';
import { useSearchParams } from 'next/navigation';
import { useNotifications } from '@/components/common/NotificationContext';
import ErrorBoundary from '@/components/common/ErrorBoundary';
import { MetricDetail } from '@/utils/api-client/interfaces/metric';
import type { RequirementOption } from '@/utils/api-client/interfaces/requirement';
import type { TypeLookup } from '@/utils/api-client/interfaces/type-lookup';
import type { UUID } from 'crypto';
import { TEST_TYPES } from '@/constants/test-types';
import { useList } from '@/hooks/useList';
import { useTypeLookups, useRequirements } from '@/hooks/useLookups';
import { metricsList } from './list';

import MetricsDirectoryTab, {
  type FilterState,
  type FilterOptions,
} from './MetricsDirectoryTab';

const initialFilterState: FilterState = {
  search: '',
  backend: [],
  type: [],
  scoreType: [],
  metricScope: [],
  requirement: '',
};

/** Filter options that are fixed rather than resolved from the backend. */
const STATIC_FILTER_OPTIONS = {
  scoreType: [
    { value: 'numeric', label: 'Numeric' },
    { value: 'categorical', label: 'Categorical' },
  ],
  metricScope: [
    { value: TEST_TYPES.SINGLE_TURN, label: TEST_TYPES.SINGLE_TURN },
    { value: TEST_TYPES.MULTI_TURN, label: TEST_TYPES.MULTI_TURN },
    { value: 'Trace', label: 'Trace' },
  ],
} satisfies Pick<FilterOptions, 'scoreType' | 'metricScope'>;

// Stable identities: an inline `data = []` default would mint a fresh array
// each render while a query is pending, so the memo below would never hold.
const NO_TYPE_LOOKUPS: TypeLookup[] = [];
const NO_REQUIREMENTS: RequirementOption[] = [];

/** Drops duplicate `type_value` rows so repeated options can't collide as React keys. */
function uniqueByTypeValue(types: TypeLookup[]): TypeLookup[] {
  return Array.from(new Map(types.map(t => [t.type_value, t])).values());
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

  const assignMode = searchParams.get('assignMode') === 'true';

  // Filter state
  const [filters, setFilters] = React.useState<FilterState>(initialFilterState);

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
    ready,
    gateNode,
  } = useList(metricsList, {
    filters,
    initialData,
    initialTotalCount,
    onError: () => {
      notifications.show('Failed to load metrics data', {
        severity: 'error',
        autoHideDuration: 4000,
      });
    },
  });

  // Options come from the reference tables, not the metrics on screen: that
  // list is server-paginated and server-filtered, so deriving from it hides
  // values on later pages and drops the rest as soon as a filter is applied.
  const { data: backendTypes = NO_TYPE_LOOKUPS } = useTypeLookups(
    "type_name eq 'BackendType'",
    ready
  );
  const { data: metricTypes = NO_TYPE_LOOKUPS } = useTypeLookups(
    "type_name eq 'MetricType'",
    ready
  );
  const { data: allRequirements = NO_REQUIREMENTS } = useRequirements(ready);

  const filterOptions = React.useMemo<FilterOptions>(
    () => ({
      ...STATIC_FILTER_OPTIONS,
      backend: uniqueByTypeValue(backendTypes).map(t => ({
        type_value:
          t.type_value.charAt(0).toUpperCase() + t.type_value.slice(1),
      })),
      type: uniqueByTypeValue(metricTypes).map(t => ({
        type_value: t.type_value,
        description: t.description || '',
      })),
      requirement: allRequirements
        .filter(b => b.name?.trim())
        .map(b => ({ id: b.id, name: b.name })),
    }),
    [backendTypes, metricTypes, allRequirements]
  );

  if (!ready) return gateNode;

  return (
    <ErrorBoundary>
      <MetricsDirectoryTab
        organizationId={organizationId}
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
        assignMode={assignMode}
      />
    </ErrorBoundary>
  );
}
