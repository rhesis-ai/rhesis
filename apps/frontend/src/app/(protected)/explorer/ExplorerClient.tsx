'use client';

import * as React from 'react';
import { useRouter } from 'next/navigation';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import FileUploadIcon from '@mui/icons-material/FileUploadOutlined';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import IosShareOutlinedIcon from '@mui/icons-material/IosShareOutlined';
import { useSession } from 'next-auth/react';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab, FabAddIcon, FabGroup } from '@/components/common/Fab';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { Can, useCan, useCanWithStatus } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import AccessDenied from '@/components/common/AccessDenied';
import { useNotifications } from '@/components/common/NotificationContext';
import type {
  ExplorerTestSetDetail,
  ImportExplorerTestSetResponse,
} from '@/utils/api-client/interfaces/explorer';
import ExplorerGrid, {
  type ExplorerBulkActionsState,
} from './components/ExplorerGrid';
import ExplorerCreateDialog from './components/ExplorerCreateDialog';
import ImportExplorerTestSetDialog from './components/ImportExplorerTestSetDialog';
import { isAuthenticated, isSessionLoading } from '@/hooks/useIsAuthenticated';

interface ExplorerClientProps {
  /** Server-fetched first page — when present, skips the initial client fetch. */
  initialData?: ExplorerTestSetDetail[];
  initialTotalCount?: number;
}

const HIDDEN_BULK_ACTIONS: ExplorerBulkActionsState = {
  visible: false,
  onDelete: () => {},
  onSave: () => {},
  saveDisabled: true,
};

export default function ExplorerClient({
  initialData,
  initialTotalCount,
}: ExplorerClientProps) {
  const { status } = useSession();
  const router = useRouter();
  const notifications = useNotifications();

  const [createDialogOpen, setCreateDialogOpen] = React.useState(false);
  const [importDialogOpen, setImportDialogOpen] = React.useState(false);
  const [refreshTrigger, setRefreshTrigger] = React.useState(0);
  const [bulkActions, setBulkActions] =
    React.useState<ExplorerBulkActionsState>(HIDDEN_BULK_ACTIONS);

  useDocumentTitle('Explorer');

  const canCreateSession = useCan(Capability.Explorer.CREATE);
  const { allowed: canRead, loading: permsLoading } = useCanWithStatus(
    Capability.Explorer.READ
  );

  const bumpRefresh = React.useCallback(
    () => setRefreshTrigger(prev => prev + 1),
    []
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
      bumpRefresh();
      router.push(`/explorer/${created.id}?openSettings=1`);
    },
    [bumpRefresh, notifications, router]
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
        description="Interactive sessions to discover requirements, generate tests, and export them to test sets."
        breadcrumbs={[]}
        actions={
          <FabGroup>
            {bulkActions.visible && !bulkActions.saveDisabled && (
              <Fab
                icon={<IosShareOutlinedIcon />}
                tooltip="Save to Test Set"
                aria-label="Save to Test Set"
                onClick={bulkActions.onSave}
              />
            )}
            {bulkActions.visible && (
              <Can capability={Capability.Explorer.DELETE}>
                <Fab
                  icon={<DeleteOutlineIcon sx={{ fontSize: 28 }} />}
                  tooltip="Delete sessions"
                  aria-label="Delete sessions"
                  onClick={bulkActions.onDelete}
                  sx={{
                    bgcolor: 'error.main',
                    '&:hover': { bgcolor: 'error.dark' },
                  }}
                />
              </Can>
            )}
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
            onBulkActionsChange={setBulkActions}
            refreshTrigger={refreshTrigger}
            initialData={initialData}
            initialTotalCount={initialTotalCount}
          />
        </Box>
      </PageLayout>

      <ExplorerCreateDialog
        open={createDialogOpen}
        onClose={() => setCreateDialogOpen(false)}
        onCreated={bumpRefresh}
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
