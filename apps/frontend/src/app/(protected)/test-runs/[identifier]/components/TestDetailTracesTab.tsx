'use client';

import { useEffect, useState } from 'react';
import { Alert, Box, CircularProgress, Typography } from '@mui/material';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';
import { BORDER_RADIUS } from '@/styles/theme';
import TraceExplorer from '@/app/(protected)/traces/components/TraceExplorer';

interface TestDetailTracesTabProps {
  test: TestResultDetail;
  /** Whether the tab is showing; the trace loads on first view, not with the drawer. */
  active: boolean;
  currentUserId: string;
  currentUserName: string;
  currentUserPicture?: string;
}

interface FirstTrace {
  traceId: string;
  projectId: string;
}

/**
 * The trace a test result produced, in the same explorer as the trace drawer.
 * A multi-turn result spread over several traces opens on the first; the
 * explorer's turn switcher walks the rest.
 */
export default function TestDetailTracesTab({
  test,
  active,
  currentUserId,
  currentUserName,
  currentUserPicture,
}: TestDetailTracesTabProps) {
  const { status } = useSession();
  const [first, setFirst] = useState<FirstTrace | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadedFor, setLoadedFor] = useState<string | null>(null);

  useEffect(() => {
    if (!active || !isAuthenticated(status) || loadedFor === test.id) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setFirst(null);

    new ApiClientFactory()
      .getTelemetryClient()
      .listTraces({ test_result_id: test.id, limit: 100 })
      .then(response => {
        if (cancelled) return;
        // The earliest trace holds turn 1; the list's own order is not guaranteed.
        const trace = [...response.traces].sort(
          (a, b) =>
            new Date(a.start_time).getTime() - new Date(b.start_time).getTime()
        )[0];
        setFirst(
          trace
            ? { traceId: trace.trace_id, projectId: trace.project_id }
            : null
        );
        setLoadedFor(test.id);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(
          err instanceof Error ? err.message : 'Failed to load the trace'
        );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [active, status, test.id, loadedFor]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress size={28} />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">{error}</Alert>
      </Box>
    );
  }

  if (!first) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography variant="body2" color="text.secondary">
          No trace was recorded for this test.
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ height: '100%', pt: 2, boxSizing: 'border-box' }}>
      <Box
        sx={{
          height: '100%',
          minHeight: 0,
          display: 'flex',
          flexDirection: 'column',
          border: 1,
          borderColor: 'divider',
          borderRadius: BORDER_RADIUS.sm,
          overflow: 'hidden',
        }}
      >
        <TraceExplorer
          active={active}
          embedded
          traceId={first.traceId}
          projectId={first.projectId}
          currentUserId={currentUserId}
          currentUserName={currentUserName}
          currentUserPicture={currentUserPicture}
        />
      </Box>
    </Box>
  );
}
