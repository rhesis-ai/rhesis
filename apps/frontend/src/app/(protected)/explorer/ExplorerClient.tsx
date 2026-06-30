'use client';

import * as React from 'react';
import { useRouter } from 'next/navigation';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import FileUploadIcon from '@mui/icons-material/FileUploadOutlined';
import { useSession } from 'next-auth/react';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab, FabAddIcon, FabGroup } from '@/components/common/Fab';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { AccountTreeIcon } from '@/components/icons';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';
import { Can, useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { useNotifications } from '@/components/common/NotificationContext';
import type { ImportExplorerTestSetResponse } from '@/utils/api-client/interfaces/explorer';
import ExplorerGrid from './components/ExplorerGrid';
import ExplorerCreateDialog from './components/ExplorerCreateDialog';
import ImportExplorerTestSetDialog from './components/ImportExplorerTestSetDialog';

export default function ExplorerClient() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const notifications = useNotifications();

  const [refreshKey, setRefreshKey] = React.useState(0);
  const [sessionCount, setSessionCount] = React.useState<number | null>(null);
  const [createDialogOpen, setCreateDialogOpen] = React.useState(false);
  const [importDialogOpen, setImportDialogOpen] = React.useState(false);

  useDocumentTitle('Explorer');

  const sessionToken = session?.session_token ?? '';
  const canCreateSession = useCan(Capability.Explorer.CREATE);

  const handleRefresh = React.useCallback(() => {
    setRefreshKey(prev => prev + 1);
  }, []);

  const handleImportedExplorerSet = React.useCallback(
    (result: ImportExplorerTestSetResponse) => {
      const { imported, skipped, test_set: created } = result;
      const parts = [`Imported ${imported} test(s)`];
      if (skipped > 0) {
        parts.push(`skipped ${skipped}`);
      }
      notifications.show(parts.join(', '), {
        severity: 'success',
        autoHideDuration: 5000,
      });
      setImportDialogOpen(false);
      handleRefresh();
      router.push(`/explorer/${created.id}?openSettings=1`);
    },
    [handleRefresh, notifications, router]
  );

  if (status === 'loading') {
    return (
      <PageLayout title="Explorer" breadcrumbs={[]}>
        <Box sx={{ p: 3 }}>
          <Typography>Loading...</Typography>
        </Box>
      </PageLayout>
    );
  }

  if (!sessionToken) {
    return (
      <PageLayout title="Explorer" breadcrumbs={[]}>
        <Box sx={{ p: 3 }}>
          <Typography color="error">No session token available</Typography>
        </Box>
      </PageLayout>
    );
  }

  return (
    <>
      <PageLayout
        title="Explorer"
        description="Interactive sessions to discover behaviors, generate tests, and export them to test sets."
        breadcrumbs={[]}
        actions={
          <FabGroup>
            <Can capability={Capability.Explorer.CREATE}>
              <Fab
                icon={<FileUploadIcon />}
                tooltip="Load test set"
                onClick={() => setImportDialogOpen(true)}
              />
              <Fab
                icon={<FabAddIcon />}
                tooltip="New session"
                onClick={() => setCreateDialogOpen(true)}
              />
            </Can>
          </FabGroup>
        }
      >
        <Box sx={{ mt: 2, mb: 2 }}>
          {sessionCount === 0 ? (
            <EntityEmptyState
              icon={AccountTreeIcon}
              title="No explorer sessions yet"
              description="Start a new session to explore behaviors and generate tests, or load an existing test set."
              actionLabel={canCreateSession ? 'New session' : undefined}
              onAction={
                canCreateSession ? () => setCreateDialogOpen(true) : undefined
              }
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
              <ExplorerGrid
                sessionToken={sessionToken}
                refreshKey={refreshKey}
                onRefresh={handleRefresh}
                onTotalCountChange={setSessionCount}
              />
            </Paper>
          )}
        </Box>
      </PageLayout>

      <ExplorerCreateDialog
        open={createDialogOpen}
        onClose={() => setCreateDialogOpen(false)}
        sessionToken={sessionToken}
        onCreated={handleRefresh}
        onNavigateToSession={sessionId => {
          router.push(`/explorer/${sessionId}?openSettings=1`);
        }}
      />

      <ImportExplorerTestSetDialog
        open={importDialogOpen}
        onClose={() => setImportDialogOpen(false)}
        onImported={handleImportedExplorerSet}
        sessionToken={sessionToken}
      />
    </>
  );
}
