'use client';

import { useState, useEffect, useCallback } from 'react';
import { Box, Typography, Alert, Button } from '@mui/material';
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
}

export default function TracesClient({ sessionToken }: TracesClientProps) {
  const notifications = useNotifications();
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState(0);
  
  // Track if we've encountered a fatal error to prevent infinite retries
  const [hasFatalError, setHasFatalError] = useState(false);

  // Drawer state
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(
    null
  );
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Filter state - default to last 24 hours
  const [filters, setFilters] = useState<TraceQueryParams>({
    limit: 50,
    offset: 0,
  });

  const fetchTraces = useCallback(async () => {
    // Don't fetch if we've encountered a fatal error
    if (hasFatalError) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const clientFactory = new ApiClientFactory(sessionToken);
      const client = clientFactory.getTelemetryClient();
      const response = await client.listTraces(filters);
      setTraces(response.traces);
      setTotalCount(response.total);
      // Clear fatal error flag on successful fetch
      setHasFatalError(false);
    } catch (err: any) {
      const errorMsg = err.message || 'Failed to fetch traces';
      setError(errorMsg);
      notifications.show(errorMsg, { severity: 'error' });
      setTraces([]);
      setTotalCount(0);
      
      // Check if this is a fatal error (4xx client errors) that shouldn't be retried
      const isFatalError = err.status && err.status >= 400 && err.status < 500;
      if (isFatalError) {
        setHasFatalError(true);
      }
    } finally {
      setLoading(false);
    }
  }, [sessionToken, filters, notifications, hasFatalError]);

  useEffect(() => {
    fetchTraces();
  }, [fetchTraces]);

  const handleRowClick = (traceId: string, projectId: string) => {
    setSelectedTraceId(traceId);
    setSelectedProjectId(projectId);
    setDrawerOpen(true);
  };

  const handleCloseDrawer = () => {
    setDrawerOpen(false);
    setSelectedTraceId(null);
    setSelectedProjectId(null);
  };

  const handlePageChange = (newPage: number) => {
    // Clear fatal error flag when changing pages (allow retry)
    setHasFatalError(false);
    setFilters(prev => ({
      ...prev,
      offset: newPage * (prev.limit || 50),
    }));
  };

  const handlePageSizeChange = (newSize: number) => {
    // Clear fatal error flag when changing page size (allow retry)
    setHasFatalError(false);
    setFilters(prev => ({
      ...prev,
      limit: newSize,
      offset: 0,
    }));
  };
  
  const handleRetry = () => {
    // Clear the fatal error flag and retry
    setHasFatalError(false);
    setError(null);
    fetchTraces();
  };

  return (
    <>
      {error && (
        <Alert 
          severity="error" 
          sx={{ mb: 2 }} 
          onClose={() => {
            setError(null);
            setHasFatalError(false);
          }}
          action={
            hasFatalError ? (
              <Button
                color="inherit"
                size="small"
                onClick={handleRetry}
              >
                Retry
              </Button>
            ) : undefined
          }
        >
          {error}
        </Alert>
      )}

      <TraceFilters
        filters={filters}
        onFiltersChange={(newFilters) => {
          // Clear fatal error flag when filters change (allow new query)
          setHasFatalError(false);
          setFilters(newFilters);
        }}
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
          filters={filters}
        />
      )}

      <TraceDrawer
        open={drawerOpen}
        onClose={handleCloseDrawer}
        traceId={selectedTraceId}
        projectId={selectedProjectId || ''}
        sessionToken={sessionToken}
      />
    </>
  );
}
