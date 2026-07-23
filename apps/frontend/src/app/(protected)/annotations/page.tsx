'use client';

import * as React from 'react';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import { useSession } from 'next-auth/react';
import { PageLayout } from '@/components/layout/PageLayout';
import { useCanWithStatus } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import AccessDenied from '@/components/common/AccessDenied';
import PageLoadingState from '@/components/common/PageLoadingState';
import AnnotationsGrid from './components/AnnotationsGrid';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';
import { isAuthenticated, isSessionLoading } from '@/hooks/useIsAuthenticated';

export default function AnnotationsPage() {
  const { status } = useSession();
  const { allowed: canReadResults, loading: resultsPermsLoading } =
    useCanWithStatus(Capability.TestResult.READ);
  const { allowed: canReadTelemetry, loading: telemetryPermsLoading } =
    useCanWithStatus(Capability.Telemetry.READ);

  useDocumentTitle('Annotations');

  const canRead = canReadResults || canReadTelemetry;
  const permsLoading = resultsPermsLoading || telemetryPermsLoading;

  if (isSessionLoading(status)) {
    return (
      <PageLayout title="Annotations" breadcrumbs={[]}>
        <Box sx={{ p: 3 }}>
          <Typography>Loading...</Typography>
        </Box>
      </PageLayout>
    );
  }

  if (permsLoading) return <PageLoadingState />;
  if (!canRead) return <AccessDenied resource="annotations" />;

  if (!isAuthenticated(status)) {
    return (
      <PageLayout title="Annotations" breadcrumbs={[]}>
        <Box sx={{ p: 3 }}>
          <Typography color="error">You are not signed in</Typography>
        </Box>
      </PageLayout>
    );
  }

  return (
    <PageLayout
      title="Annotations"
      description="Browse human judgments on test results and traces across your project."
      breadcrumbs={[]}
    >
      <Box sx={{ mt: 2, mb: 2 }}>
        <Paper
          sx={{
            width: '100%',
            borderRadius: BORDER_RADIUS.md,
            boxShadow: ELEVATION.xs,
            border: theme => `1px solid ${theme.palette.greyscale.border}`,
            overflow: 'hidden',
          }}
        >
          <AnnotationsGrid />
        </Paper>
      </Box>
    </PageLayout>
  );
}
