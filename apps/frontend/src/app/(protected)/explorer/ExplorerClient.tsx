'use client';

import * as React from 'react';
import { useRouter } from 'next/navigation';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import FileUploadIcon from '@mui/icons-material/FileUploadOutlined';
import { useSession } from 'next-auth/react';
import { useQueryClient } from '@tanstack/react-query';
import { explorerKeys } from '@/constants/query-keys';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab, FabAddIcon, FabGroup } from '@/components/common/Fab';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { Can, useCan, useCanWithStatus } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import AccessDenied from '@/components/common/AccessDenied';
import { useNotifications } from '@/components/common/NotificationContext';
import type { ImportExplorerTestSetResponse } from '@/utils/api-client/interfaces/explorer';
import ExplorerGrid from './components/ExplorerGrid';
import ExplorerCreateDialog from './components/ExplorerCreateDialog';
import ImportExplorerTestSetDialog from './components/ImportExplorerTestSetDialog';
import { isAuthenticated, isSessionLoading } from '@/hooks/useIsAuthenticated';

export default function ExplorerClient() {
  const { status } = useSession();
  const router = useRouter();
  const queryClient = useQueryClient();
  const notifications = useNotifications();

  const [createDialogOpen, setCreateDialogOpen] = React.useState(false);
  const [importDialogOpen, setImportDialogOpen] = React.useState(false);

  useDocumentTitle('Explorer');

  const canCreateSession = useCan(Capability.Explorer.CREATE);
  const { allowed: canRead, loading: permsLoading } = useCanWithStatus(
    Capability.Explorer.READ
  );

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
      queryClient.invalidateQueries({ queryKey: explorerKeys.all() });
      router.push(`/explorer/${created.id}?openSettings=1`);
    },
    [queryClient, notifications, router]
  );

  if (isSessionLoading(status) || permsLoading) {
    return (
      <PageLayout title="Explorer" breadcrumbs={[]}>
        <Box sx={{ p: 3 }}>
          <Typography>Loading...</Typography>
        </Box>
      </PageLayout>
    );
  }

  if (!isAuthenticated(status)) {
    return (
      <PageLayout title="Explorer" breadcrumbs={[]}>
        <Box sx={{ p: 3 }}>
          <Typography color="error">No session token available</Typography>
        </Box>
      </PageLayout>
    );
  }

  if (!canRead) return <AccessDenied resource="explorer sessions" />;

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
          <ExplorerGrid
            canCreate={canCreateSession}
            onCreateClick={() => setCreateDialogOpen(true)}
          />
        </Box>
      </PageLayout>

      <ExplorerCreateDialog
        open={createDialogOpen}
        onClose={() => setCreateDialogOpen(false)}
        onCreated={() =>
          queryClient.invalidateQueries({ queryKey: explorerKeys.all() })
        }
        onNavigateToSession={sessionId => {
          router.push(`/explorer/${sessionId}?openSettings=1`);
        }}
      />

      <ImportExplorerTestSetDialog
        open={importDialogOpen}
        onClose={() => setImportDialogOpen(false)}
        onImported={handleImportedExplorerSet}
      />
    </>
  );
}
