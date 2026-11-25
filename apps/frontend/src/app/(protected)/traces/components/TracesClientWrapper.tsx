'use client';

import React, { useCallback, useState } from 'react';
import { useSession } from 'next-auth/react';
import { useSearchParams } from 'next/navigation';
import { Alert, Box } from '@mui/material';
import RefreshOutlinedIcon from '@mui/icons-material/RefreshOutlined';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab, FabGroup } from '@/components/common/Fab';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import TimelineOutlinedIcon from '@mui/icons-material/TimelineOutlined';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import TracesClient from './TracesClient';
import type { TraceSummary } from '@/utils/api-client/interfaces/telemetry';
import AccessDenied from '@/components/common/AccessDenied';
import PageLoadingState from '@/components/common/PageLoadingState';
import { useCanWithStatus } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';
import {
  filtersFromSearchParams,
  viewFromSearchParams,
} from './trace-url-state';
import { PAGE_HEADERS } from '@/constants/page-headers';
import { useSkeletonMode } from '@/components/loading/SkeletonMode';

interface TracesClientWrapperProps {
  currentUserId?: string;
  currentUserName?: string;
  currentUserPicture?: string;
  /** Server-fetched first page -- when present, skips the initial client fetch. */
  initialData?: TraceSummary[];
  initialTotalCount?: number;
}

export default function TracesClientWrapper({
  currentUserId = '',
  currentUserName = '',
  currentUserPicture,
  initialData,
  initialTotalCount = 0,
}: TracesClientWrapperProps) {
  // As the route's loading view: the page drawn without data or a session.
  const skeleton = useSkeletonMode();
  const { status } = useSession();
  const searchParams = useSearchParams();
  const initialTraceId = searchParams.get('open_trace');
  const initialProjectId = searchParams.get('project_id');
  const initialSpanId = searchParams.get('open_span');
  // Read once: TracesClient owns this state after mount and writes it back.
  const [initialView] = useState(() =>
    viewFromSearchParams(new URLSearchParams(searchParams.toString()))
  );
  const [initialFilters] = useState(() =>
    filtersFromSearchParams(new URLSearchParams(searchParams.toString()))
  );
  const { allowed: canRead, loading: permsLoading } = useCanWithStatus(
    Capability.Telemetry.READ
  );
  // Decided on first render when the server already fetched page 1, so an
  // empty project shows the empty state straight away instead of a grid
  // skeleton that swaps out once the client fetch lands.
  const [showEmptyHint, setShowEmptyHint] = useState(
    initialData !== undefined && initialTotalCount === 0 && !initialProjectId
  );
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  useDocumentTitle('Traces');

  const handleRefresh = useCallback(() => {
    setRefreshTrigger(prev => prev + 1);
  }, []);

  const handleUnfilteredEmpty = useCallback((empty: boolean) => {
    setShowEmptyHint(empty);
  }, []);

  if (!skeleton && permsLoading) return <PageLoadingState />;
  if (!skeleton && !canRead) return <AccessDenied resource="traces" />;

  if (!skeleton && !isAuthenticated(status)) {
    return (
      <PageLayout
        title={PAGE_HEADERS.traces.title}
        description={PAGE_HEADERS.traces.description}
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
      title={PAGE_HEADERS.traces.title}
      description={PAGE_HEADERS.traces.description}
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
            showEmptyHint && !skeleton
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
          {/* The grid card lives inside TracesClient, so the rollup tiles can sit
              above it rather than inside it. */}
          <TracesClient
            currentUserId={currentUserId}
            currentUserName={currentUserName}
            currentUserPicture={currentUserPicture}
            initialTraceId={skeleton ? null : initialTraceId}
            initialProjectId={initialProjectId}
            initialSpanId={skeleton ? null : initialSpanId}
            initialView={initialView}
            initialFilters={initialFilters}
            onUnfilteredEmpty={handleUnfilteredEmpty}
            refreshTrigger={refreshTrigger}
            initialData={initialData}
            initialTotalCount={initialTotalCount}
          />
        </Box>
        {showEmptyHint && !skeleton && (
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
