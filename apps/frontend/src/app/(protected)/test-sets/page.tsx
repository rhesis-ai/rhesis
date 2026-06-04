'use client';

import * as React from 'react';
import { useRouter } from 'next/navigation';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import FileUploadIcon from '@mui/icons-material/FileUploadOutlined';
import SecurityIcon from '@mui/icons-material/SecurityOutlined';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import { useSession } from 'next-auth/react';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab, FabAddIcon, FabGroup } from '@/components/common/Fab';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { HorizontalSplitIcon } from '@/components/icons';
import TestSetsGrid from './components/TestSetsGrid';
import TestSetDrawer from './components/TestSetDrawer';
import FileImportDrawer from './components/FileImportDrawer';
import GarakImportDrawer from './components/GarakImportDrawer';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';

export default function TestSetsPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const notifications = useNotifications();

  const [refreshKey, setRefreshKey] = React.useState(0);
  const [testSetCount, setTestSetCount] = React.useState<number | null>(null);
  const [createDrawerOpen, setCreateDrawerOpen] = React.useState(false);
  const [fileImportDrawerOpen, setFileImportDrawerOpen] = React.useState(false);
  const [garakImportDrawerOpen, setGarakImportDrawerOpen] =
    React.useState(false);

  useDocumentTitle('Test Sets');

  const sessionToken = session?.session_token ?? '';

  React.useEffect(() => {
    const fetchCount = async () => {
      if (!sessionToken) return;
      try {
        const apiFactory = new ApiClientFactory(sessionToken);
        const testSetsClient = apiFactory.getTestSetsClient();
        const response = await testSetsClient.getTestSets({
          skip: 0,
          limit: 1,
          sort_by: 'created_at',
          sort_order: 'desc',
        });
        setTestSetCount(response.pagination?.totalCount ?? 0);
      } catch {
        setTestSetCount(0);
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

  const handleFileImportSuccess = React.useCallback(
    (_testSetId: string) => {
      handleRefresh();
      notifications.show('Test set imported successfully from file', {
        severity: 'success',
      });
    },
    [handleRefresh, notifications]
  );

  const handleGarakImportSuccess = React.useCallback(
    (testSetIds: string[]) => {
      handleRefresh();
      const count = testSetIds.length;
      notifications.show(
        `${count} Garak ${count === 1 ? 'probe' : 'probes'} imported successfully`,
        { severity: 'success', autoHideDuration: 6000 }
      );
      if (testSetIds.length === 1) {
        router.push(`/test-sets/${testSetIds[0]}`);
      }
    },
    [handleRefresh, notifications, router]
  );

  if (status === 'loading') {
    return (
      <PageLayout title="Test Sets" breadcrumbs={[]}>
        <Box sx={{ p: 3 }}>
          <Typography>Loading...</Typography>
        </Box>
      </PageLayout>
    );
  }

  if (!sessionToken) {
    return (
      <PageLayout title="Test Sets" breadcrumbs={[]}>
        <Box sx={{ p: 3 }}>
          <Typography color="error">No session token available</Typography>
        </Box>
      </PageLayout>
    );
  }

  return (
    <>
      <PageLayout
        title="Test Sets"
        description="Curated collections of tests you can version, share, and execute against your AI endpoints."
        breadcrumbs={[]}
        actions={
          <FabGroup>
            <Fab
              icon={<FileUploadIcon />}
              tooltip="Import from File"
              onClick={() => setFileImportDrawerOpen(true)}
            />
            <Fab
              icon={<SecurityIcon />}
              tooltip="Import from Garak"
              onClick={() => setGarakImportDrawerOpen(true)}
            />
            <Fab
              icon={<AutoFixHighIcon />}
              tooltip="AI generated Test Set"
              aria-label="AI generated Test Set"
              onClick={() => router.push('/tests/new-generated')}
            />
            <Fab
              icon={<FabAddIcon />}
              tooltip="New Test Set"
              onClick={() => setCreateDrawerOpen(true)}
            />
          </FabGroup>
        }
      >
        <Box sx={{ mt: 2, mb: 2 }}>
          {testSetCount === 0 ? (
            <EntityEmptyState
              icon={HorizontalSplitIcon}
              title="No test sets yet"
              description="Group related tests into a test set to version, share, and run them together."
              actionLabel="Create test set"
              onAction={() => setCreateDrawerOpen(true)}
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
              <TestSetsGrid
                sessionToken={sessionToken}
                refreshKey={refreshKey}
                onRefresh={handleRefresh}
              />
            </Paper>
          )}
        </Box>
      </PageLayout>

      <TestSetDrawer
        open={createDrawerOpen}
        onClose={() => setCreateDrawerOpen(false)}
        sessionToken={sessionToken}
        onSuccess={handleCreateSuccess}
      />

      <FileImportDrawer
        open={fileImportDrawerOpen}
        onClose={() => setFileImportDrawerOpen(false)}
        sessionToken={sessionToken}
        onSuccess={handleFileImportSuccess}
      />

      <GarakImportDrawer
        open={garakImportDrawerOpen}
        onClose={() => setGarakImportDrawerOpen(false)}
        sessionToken={sessionToken}
        onSuccess={handleGarakImportSuccess}
      />
    </>
  );
}
