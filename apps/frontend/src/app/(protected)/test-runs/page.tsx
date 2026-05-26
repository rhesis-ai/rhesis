'use client';

import * as React from 'react';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import AddIcon from '@mui/icons-material/Add';
import { useSession } from 'next-auth/react';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab, FabGroup } from '@/components/common/Fab';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { PlayArrowIcon } from '@/components/icons';
import TestRunsGrid from './components/TestRunsGrid';
import TestRunDrawer from './components/TestRunDrawer';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { BORDER_RADIUS, ELEVATION, GREYSCALE } from '@/styles/theme';
import { ApiClientFactory } from '@/utils/api-client/client-factory';

export default function TestRunsPage() {
  const { data: session, status } = useSession();
  const [refreshKey, setRefreshKey] = React.useState(0);
  const [testRunCount, setTestRunCount] = React.useState<number | null>(null);
  const [createDrawerOpen, setCreateDrawerOpen] = React.useState(false);

  useDocumentTitle('Test Runs');

  const sessionToken = session?.session_token ?? '';

  React.useEffect(() => {
    const fetchCount = async () => {
      if (!sessionToken) return;
      try {
        const apiFactory = new ApiClientFactory(sessionToken);
        const testRunsClient = apiFactory.getTestRunsClient();
        const response = await testRunsClient.getTestRuns({
          skip: 0,
          limit: 1,
        });
        setTestRunCount(response.pagination?.totalCount ?? 0);
      } catch {
        setTestRunCount(0);
      }
    };
    fetchCount();
  }, [sessionToken, refreshKey]);

  const handleRefresh = React.useCallback(() => {
    setRefreshKey(prev => prev + 1);
  }, []);

  const handleCreateSuccess = React.useCallback(() => {
    setCreateDrawerOpen(false);
    handleRefresh();
  }, [handleRefresh]);

  if (status === 'loading') {
    return (
      <PageLayout title="Test Runs" breadcrumbs={[]}>
        <Box sx={{ p: 3 }}>
          <Typography>Loading...</Typography>
        </Box>
      </PageLayout>
    );
  }

  if (!sessionToken) {
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
            <Fab
              icon={<AddIcon />}
              tooltip="New Test Run"
              onClick={() => setCreateDrawerOpen(true)}
            />
          </FabGroup>
        }
      >
        <Box sx={{ mt: 2, mb: 2 }}>
          {testRunCount === 0 ? (
            <EntityEmptyState
              icon={PlayArrowIcon}
              title="No test runs yet"
              description="Execute a test set against an AI endpoint to start your first test run. Test runs measure quality, safety, and reliability of your AI endpoints."
              actionLabel="Create test run"
              onAction={() => setCreateDrawerOpen(true)}
            />
          ) : (
            <Paper
              sx={{
                width: '100%',
                borderRadius: BORDER_RADIUS.md,
                boxShadow: ELEVATION.xs,
                border: theme =>
                  `1px solid ${theme.palette.mode === 'light' ? GREYSCALE.light.border : GREYSCALE.dark.border}`,
                overflow: 'hidden',
              }}
            >
              <TestRunsGrid
                sessionToken={sessionToken}
                refreshKey={refreshKey}
                onRefresh={handleRefresh}
              />
            </Paper>
          )}
        </Box>
      </PageLayout>

      <TestRunDrawer
        open={createDrawerOpen}
        onClose={() => setCreateDrawerOpen(false)}
        sessionToken={sessionToken}
        onSuccess={handleCreateSuccess}
      />
    </>
  );
}
