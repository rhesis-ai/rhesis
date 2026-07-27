'use client';

import * as React from 'react';
import Box from '@mui/material/Box';
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
import TestRunsGrid from './components/TestRunsGrid';
import RunDrawer from '@/components/common/RunDrawer';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { isAuthenticated, isSessionLoading } from '@/hooks/useIsAuthenticated';

export default function TestRunsPage() {
  const { status } = useSession();
  const queryClient = useQueryClient();
  const { allowed: canRead, loading: permsLoading } = useCanWithStatus(
    Capability.TestRun.READ
  );
  const canCreateTestRun = useCan(Capability.TestRun.CREATE);
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
          <TestRunsGrid
            canCreate={canCreateTestRun}
            onCreateClick={() => setCreateDrawerOpen(true)}
          />
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
