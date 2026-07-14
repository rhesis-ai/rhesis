'use client';

import * as React from 'react';
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
} from '@mui/material';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import DownloadIcon from '@mui/icons-material/Download';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import RefreshIcon from '@mui/icons-material/Refresh';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import { Fab, FabGroup } from '@/components/common/Fab';
import { useRouter } from 'next/navigation';
import { DeleteModal } from '@/components/common/DeleteModal';
import RunDrawer from '@/components/common/RunDrawer';
import type { GarakSyncPreviewResponse } from '@/utils/api-client/garak-client';
import { Can } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';

interface TestSetHeaderActionsProps {
  sessionToken: string;
  testSetId: string;
  testSetName: string;
  testCount: number;
  isGarakTestSet: boolean;
}

export default function TestSetHeaderActions({
  sessionToken,
  testSetId,
  testSetName,
  testCount,
  isGarakTestSet,
}: TestSetHeaderActionsProps) {
  const router = useRouter();
  const notifications = useNotifications();

  const [executeDrawerOpen, setExecuteDrawerOpen] = React.useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = React.useState(false);
  const [isDeleting, setIsDeleting] = React.useState(false);
  const [isDownloading, setIsDownloading] = React.useState(false);
  const [isSyncing, setIsSyncing] = React.useState(false);
  const [garakPreview, setGarakPreview] =
    React.useState<GarakSyncPreviewResponse | null>(null);
  const [syncDialogOpen, setSyncDialogOpen] = React.useState(false);

  const handleDeleteConfirm = async () => {
    setIsDeleting(true);
    try {
      const factory = new ApiClientFactory(sessionToken);
      await factory.getTestSetsClient().deleteTestSet(testSetId);
      notifications.show('Test set deleted', {
        severity: 'success',
        autoHideDuration: 4000,
      });
      router.push('/test-sets');
    } catch {
      notifications.show('Failed to delete test set', {
        severity: 'error',
        autoHideDuration: 6000,
      });
      setIsDeleting(false);
    } finally {
      setDeleteDialogOpen(false);
    }
  };

  const handleDownload = async () => {
    setIsDownloading(true);
    try {
      const factory = new ApiClientFactory(sessionToken);
      const blob = await factory.getTestSetsClient().downloadTestSet(testSetId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${testSetName.replace(/\s+/g, '_')}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      notifications.show('Failed to download test set', {
        severity: 'error',
        autoHideDuration: 6000,
      });
    } finally {
      setIsDownloading(false);
    }
  };

  const handleGarakSyncPreview = async () => {
    setIsSyncing(true);
    try {
      const factory = new ApiClientFactory(sessionToken);
      const preview = await factory.getGarakClient().previewSync(testSetId);
      if (preview.error) {
        notifications.show(`Garak sync unavailable: ${preview.error}`, {
          severity: 'warning',
          autoHideDuration: 6000,
        });
        return;
      }
      setGarakPreview(preview);
      setSyncDialogOpen(true);
    } catch {
      notifications.show('Failed to preview Garak sync', {
        severity: 'error',
        autoHideDuration: 6000,
      });
    } finally {
      setIsSyncing(false);
    }
  };

  const handleGarakSyncConfirm = async () => {
    setIsSyncing(true);
    setSyncDialogOpen(false);
    try {
      const factory = new ApiClientFactory(sessionToken);
      await factory.getGarakClient().syncTestSet(testSetId);
      notifications.show('Garak sync started', {
        severity: 'success',
        autoHideDuration: 4000,
      });
      router.refresh();
    } catch {
      notifications.show('Garak sync failed', {
        severity: 'error',
        autoHideDuration: 6000,
      });
    } finally {
      setIsSyncing(false);
      setGarakPreview(null);
    }
  };

  return (
    <>
      <FabGroup>
        <Can capability={Capability.TestSet.DELETE}>
          <Fab
            icon={<DeleteOutlineIcon sx={{ fontSize: 28 }} />}
            tooltip="Delete test set"
            onClick={() => setDeleteDialogOpen(true)}
            loading={isDeleting}
          />
        </Can>
        <Can capability={Capability.TestSet.EXPORT}>
          <Fab
            icon={<DownloadIcon sx={{ fontSize: 28 }} />}
            tooltip="Download test set (CSV)"
            onClick={handleDownload}
            loading={isDownloading}
          />
        </Can>
        <Can capability={Capability.TestSet.EXECUTE}>
          <Fab
            icon={<PlayArrowIcon sx={{ fontSize: 28 }} />}
            tooltip="Execute test set"
            onClick={() => setExecuteDrawerOpen(true)}
            disabled={testCount === 0}
          />
        </Can>
        {isGarakTestSet && (
          <Can capability={Capability.TestSet.UPDATE}>
            <Fab
              icon={<RefreshIcon sx={{ fontSize: 28 }} />}
              tooltip="Sync from Garak"
              onClick={handleGarakSyncPreview}
              loading={isSyncing}
            />
          </Can>
        )}
      </FabGroup>

      <RunDrawer
        mode="executeTestSet"
        open={executeDrawerOpen}
        onClose={() => setExecuteDrawerOpen(false)}
        sessionToken={sessionToken}
        data={{ testSetId }}
      />

      <DeleteModal
        open={deleteDialogOpen}
        onClose={() => !isDeleting && setDeleteDialogOpen(false)}
        onConfirm={handleDeleteConfirm}
        isLoading={isDeleting}
        title="Delete test set?"
        message={
          <>
            &ldquo;{testSetName}&rdquo; and all its data will be permanently
            deleted. This cannot be undone.
          </>
        }
      />

      <Dialog open={syncDialogOpen} onClose={() => setSyncDialogOpen(false)}>
        <DialogTitle>Confirm Garak sync</DialogTitle>
        <DialogContent>
          <DialogContentText>
            {garakPreview
              ? `This will add ${garakPreview.to_add} and remove ${garakPreview.to_remove} tests (${garakPreview.unchanged} unchanged). New version: ${garakPreview.new_version}.`
              : 'Ready to sync from Garak.'}
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSyncDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleGarakSyncConfirm}
            disabled={isSyncing}
          >
            Confirm sync
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
