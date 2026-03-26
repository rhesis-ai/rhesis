'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { Alert } from '@mui/material';
import TracesTable from './TracesTable';
import TraceFilters from './TraceFilters';
import TraceDrawer from './TraceDrawer';
import { NoTracesFound } from './EmptyStates';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  TraceSummary,
  TraceQueryParams,
} from '@/utils/api-client/interfaces/telemetry';
import { useNotifications } from '@/components/common/NotificationContext';

interface TracesClientProps {
  sessionToken: string;
  currentUserId?: string;
  currentUserName?: string;
  currentUserPicture?: string;
  initialTraceId?: string | null;
  initialProjectId?: string | null;
}

export default function TracesClient({
  sessionToken,
  currentUserId = '',
  currentUserName = '',
  currentUserPicture,
  initialTraceId = null,
  initialProjectId = null,
}: TracesClientProps) {
  const router = useRouter();
  const pathname = usePathname();
  const notifications = useNotifications();
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState(0);

  // Drawer state - initialize from props for deep-link support
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(
    initialTraceId
  );
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(
    initialProjectId
  );
  const [drawerOpen, setDrawerOpen] = useState(
    !!(initialTraceId && initialProjectId)
  );

  // Filter state - default to last 24 hours
  const [filters, setFilters] = useState<TraceQueryParams>({
    limit: 50,
    offset: 0,
  });

  // Refresh key for manual refresh (consistent with other components)
  const [refreshKey, setRefreshKey] = useState(0);

  // Fetch traces - using pattern from BehaviorsClient and MetricsClient
  useEffect(() => {
    const fetchTraces = async () => {
      if (!sessionToken) return;

      setLoading(true);
      setError(null);

      try {
        const clientFactory = new ApiClientFactory(sessionToken);
        const client = clientFactory.getTelemetryClient();
        const response = await client.listTraces(filters);
        setTraces(response.traces);
        setTotalCount(response.total);
      } catch (err: unknown) {
        const errorMsg =
          err instanceof Error ? err.message : 'Failed to fetch traces';
        setError(errorMsg);
        notifications.show(errorMsg, { severity: 'error' });
        setTraces([]);
        setTotalCount(0);
      } finally {
        setLoading(false);
      }
    };

    fetchTraces();
  }, [sessionToken, filters, refreshKey, notifications]);

  const handleRowClick = (traceId: string, projectId: string) => {
    setSelectedTraceId(traceId);
    setSelectedProjectId(projectId);
    setDrawerOpen(true);
  };

  const handleCloseDrawer = useCallback(() => {
    setDrawerOpen(false);
    setSelectedTraceId(null);
    setSelectedProjectId(null);
    if (initialTraceId) {
      router.replace(pathname, { scroll: false });
    }
  }, [initialTraceId, router, pathname]);

  const handlePageChange = (newPage: number) => {
    setFilters(prev => ({
      ...prev,
      offset: newPage * (prev.limit || 50),
    }));
  };

  const handlePageSizeChange = (newSize: number) => {
    setFilters(prev => ({
      ...prev,
      limit: newSize,
      offset: 0,
    }));
  };

  const handleRefresh = () => {
    setRefreshKey(prev => prev + 1);
  };

  return (
    <>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <TraceFilters
        filters={filters}
        onFiltersChange={setFilters}
        onRefresh={handleRefresh}
        sessionToken={sessionToken}
      />

      {traces.length === 0 && !loading ? (
        <NoTracesFound />
      ) : (
        <TracesTable
          traces={traces}
          loading={loading}
          onRowClick={handleRowClick}
          totalCount={totalCount}
          page={Math.floor((filters.offset || 0) / (filters.limit || 50))}
          pageSize={filters.limit || 50}
          onPageChange={handlePageChange}
          onPageSizeChange={handlePageSizeChange}
        />
      )}

      <TraceDrawer
        open={drawerOpen}
        onClose={handleCloseDrawer}
        traceId={selectedTraceId}
        projectId={selectedProjectId || ''}
        sessionToken={sessionToken}
        currentUserId={currentUserId}
        currentUserName={currentUserName}
        currentUserPicture={currentUserPicture}
      />
    </>
  );
}
