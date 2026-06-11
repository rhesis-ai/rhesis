'use client';

import React, { useCallback, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { Alert, Box, Paper } from '@mui/material';
import RefreshOutlinedIcon from '@mui/icons-material/RefreshOutlined';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab, FabGroup } from '@/components/common/Fab';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import TimelineOutlinedIcon from '@mui/icons-material/TimelineOutlined';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';
import TracesClient from './TracesClient';

interface TracesClientWrapperProps {
  sessionToken: string;
  currentUserId?: string;
  currentUserName?: string;
  currentUserPicture?: string;
}

export default function TracesClientWrapper({
  sessionToken,
  currentUserId = '',
  currentUserName = '',
  currentUserPicture,
}: TracesClientWrapperProps) {
  const searchParams = useSearchParams();
  const initialTraceId = searchParams.get('open_trace');
  const initialProjectId = searchParams.get('project_id');
  const [refreshKey, setRefreshKey] = useState(0);
  const [showEmptyHint, setShowEmptyHint] = useState(false);

  useDocumentTitle('Traces');

  const handleRefresh = useCallback(() => {
    setRefreshKey(prev => prev + 1);
  }, []);

  const handleUnfilteredEmpty = useCallback((empty: boolean) => {
    setShowEmptyHint(empty);
  }, []);

  if (!sessionToken) {
    return (
      <PageLayout
        title="Traces"
        description="OpenTelemetry traces from test runs and live endpoint traffic. Inspect spans, metrics, and reviews."
        breadcrumbs={[]}
      >
        <Alert severity="error" sx={{ mb: 3 }}>
          Session expired. Please refresh the page or log in again.
        </Alert>
        <EntityEmptyState
          icon={TimelineOutlinedIcon}
          title="Authentication Required"
          description="Please log in to view and analyze OpenTelemetry traces."
        />
      </PageLayout>
    );
  }

  return (
    <PageLayout
      title="Traces"
      description="OpenTelemetry traces from test runs and live endpoint traffic. Inspect spans, metrics, and reviews."
      breadcrumbs={[]}
      actions={
        <FabGroup>
          <Fab
            icon={<RefreshOutlinedIcon />}
            tooltip="Refresh traces"
            aria-label="Refresh traces"
            onClick={handleRefresh}
          />
        </FabGroup>
      }
    >
      <Box sx={{ mt: 2, mb: 2, position: 'relative' }}>
        {/*
         * Keep TracesClient mounted so a completed fetch can clear the empty hint.
         * Unmounting on the first empty response trapped the page even when later
         * requests returned traces (visible in Network but not in the UI).
         */}
        <Box
          sx={
            showEmptyHint
              ? {
                  position: 'absolute',
                  width: '100%',
                  height: 0,
                  overflow: 'hidden',
                  visibility: 'hidden',
                  pointerEvents: 'none',
                }
              : {}
          }
        >
          <Paper
            sx={{
              width: '100%',
              borderRadius: BORDER_RADIUS.md,
              boxShadow: ELEVATION.xs,
              border: theme => `1px solid ${theme.palette.greyscale.border}`,
              overflow: 'hidden',
            }}
          >
            <TracesClient
              sessionToken={sessionToken}
              currentUserId={currentUserId}
              currentUserName={currentUserName}
              currentUserPicture={currentUserPicture}
              initialTraceId={initialTraceId}
              initialProjectId={initialProjectId}
              refreshKey={refreshKey}
              onRefresh={handleRefresh}
              onUnfilteredEmpty={handleUnfilteredEmpty}
            />
          </Paper>
        </Box>
        {showEmptyHint && (
          <EntityEmptyState
            card
            icon={TimelineOutlinedIcon}
            title="No traces yet"
            description="Traces appear after test runs or live endpoint invocations. Run a test set or call an instrumented endpoint to get started."
          />
        )}
      </Box>
    </PageLayout>
  );
}
