'use client';

import * as React from 'react';
import {
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Tooltip,
} from '@mui/material';
import MuiFab from '@mui/material/Fab';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import DownloadIcon from '@mui/icons-material/Download';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import RefreshIcon from '@mui/icons-material/Refresh';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import { useRouter } from 'next/navigation';
import { DeleteModal } from '@/components/common/DeleteModal';
import ExecuteTestSetDrawer from './ExecuteTestSetDrawer';
import type { GarakSyncPreviewResponse } from '@/utils/api-client/garak-client';

const FAB_SX = {
  bgcolor: 'primary.main',
  color: '#fff',
  boxShadow: '0px 2px 2px rgba(84, 90, 101, 0.25)',
  width: 56,
  height: 56,
  '&:hover': { bgcolor: 'primary.dark' },
  '&:active': { boxShadow: '0px 2px 2px rgba(84, 90, 101, 0.25)' },
} as const;

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
      <Box sx={{ display: 'flex', gap: '20px', alignItems: 'center' }}>
        {/* Delete FAB */}
        <Tooltip title="Delete test set" placement="bottom">
          <MuiFab
            size="medium"
            sx={FAB_SX}
            onClick={() => setDeleteDialogOpen(true)}
            disabled={isDeleting}
          >
            {isDeleting ? (
              <CircularProgress size={24} color="inherit" />
            ) : (
              <DeleteOutlineIcon sx={{ fontSize: 28 }} />
            )}
          </MuiFab>
        </Tooltip>

        {/* Download FAB */}
        <Tooltip title="Download test set (CSV)" placement="bottom">
          <MuiFab
            size="medium"
            sx={FAB_SX}
            onClick={handleDownload}
            disabled={isDownloading}
          >
            {isDownloading ? (
              <CircularProgress size={24} color="inherit" />
            ) : (
              <DownloadIcon sx={{ fontSize: 28 }} />
            )}
          </MuiFab>
        </Tooltip>

        {/* Execute FAB */}
        <Tooltip title="Execute test set" placement="bottom">
          <MuiFab
            size="medium"
            sx={FAB_SX}
            onClick={() => setExecuteDrawerOpen(true)}
            disabled={testCount === 0}
          >
            <PlayArrowIcon sx={{ fontSize: 32 }} />
          </MuiFab>
        </Tooltip>

        {/* Garak Sync — conditional rectangular button */}
        {isGarakTestSet && (
          <Button
            variant="outlined"
            startIcon={
              isSyncing ? <CircularProgress size={16} /> : <RefreshIcon />
            }
            onClick={handleGarakSyncPreview}
            disabled={isSyncing}
          >
            {isSyncing ? 'Syncing…' : 'Sync from Garak'}
          </Button>
        )}
      </Box>

      {/* Execute Drawer */}
      <ExecuteTestSetDrawer
        open={executeDrawerOpen}
        onClose={() => setExecuteDrawerOpen(false)}
        testSetId={testSetId}
        sessionToken={sessionToken}
      />

      {/* Delete Confirmation */}
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

      {/* Garak Sync Confirmation */}
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
