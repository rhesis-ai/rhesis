'use client';

import * as React from 'react';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import { useSession } from 'next-auth/react';
import { useQueryClient } from '@tanstack/react-query';
import { testRunKeys } from '@/constants/query-keys';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab, FabAddIcon, FabGroup } from '@/components/common/Fab';
import { Can, useCan, useCanWithStatus } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import AccessDenied from '@/components/common/AccessDenied';
import PageLoadingState from '@/components/common/PageLoadingState';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { getEntityEmptyStateEnrichment } from '@/constants/entity-empty-state-env';
import { PlayArrowIcon } from '@/components/icons';
import TestRunsGrid from './components/TestRunsGrid';
import RunDrawer from '@/components/common/RunDrawer';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';
import { isAuthenticated, isSessionLoading } from '@/hooks/useIsAuthenticated';

export default function TestRunsPage() {
  const { status } = useSession();
  const queryClient = useQueryClient();
  const { allowed: canRead, loading: permsLoading } = useCanWithStatus(
    Capability.TestRun.READ
  );
  const canCreateTestRun = useCan(Capability.TestRun.CREATE);
  const [testRunCount, setTestRunCount] = React.useState<number | null>(null);
  const [createDrawerOpen, setCreateDrawerOpen] = React.useState(false);

  useDocumentTitle('Test Runs');

  const handleCreateSuccess = React.useCallback(() => {
    setCreateDrawerOpen(false);
    queryClient.invalidateQueries({ queryKey: testRunKeys.all() });
  }, [queryClient]);

  if (isSessionLoading(status)) {
    return (
      <PageLayout title="Test Runs" breadcrumbs={[]}>
        <Box sx={{ p: 3 }}>
          <Typography>Loading...</Typography>
        </Box>
      </PageLayout>
    );
  }

  if (permsLoading) return <PageLoadingState />;
  if (!canRead) return <AccessDenied resource="test runs" />;

  if (!isAuthenticated(status)) {
    return (
      <PageLayout title="Test Runs" breadcrumbs={[]}>
        <Box sx={{ p: 3 }}>
          <Typography color="error">No session token available</Typography>
        </Box>
      </PageLayout>
    );
  }

  return (
    <>
      <PageLayout
        title="Test Runs"
        description="Executions of your test sets against AI endpoints. Track status, results, and history of each run."
        breadcrumbs={[]}
        actions={
          <FabGroup>
            <Can capability={Capability.TestRun.CREATE}>
              <Fab
                icon={<FabAddIcon />}
                tooltip="New Test Run"
                onClick={() => setCreateDrawerOpen(true)}
              />
            </Can>
          </FabGroup>
        }
      >
        <Box sx={{ mt: 2, mb: 2 }}>
          {testRunCount === 0 ? (
            <EntityEmptyState
              card
              icon={PlayArrowIcon}
              title="No test runs yet"
              description="Execute a test set against an AI endpoint to start your first test run. Test runs measure quality, safety, and reliability of your AI endpoints."
              actionLabel={canCreateTestRun ? 'Create test run' : undefined}
              onAction={
                canCreateTestRun ? () => setCreateDrawerOpen(true) : undefined
              }
              enrichment={getEntityEmptyStateEnrichment('test-runs')}
            />
          ) : (
            <Paper
              sx={{
                width: '100%',
                borderRadius: BORDER_RADIUS.md,
                boxShadow: ELEVATION.xs,
                border: theme => `1px solid ${theme.palette.greyscale.border}`,
                overflow: 'hidden',
              }}
            >
              <TestRunsGrid onTotalCountChange={setTestRunCount} />
            </Paper>
          )}
        </Box>
      </PageLayout>

      <RunDrawer
        mode="newTestRun"
        open={createDrawerOpen}
        onClose={() => setCreateDrawerOpen(false)}
        onSuccess={handleCreateSuccess}
      />
    </>
  );
}
