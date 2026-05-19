'use client';

import * as React from 'react';
import {
  Box,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Button,
  Tooltip,
  CircularProgress,
} from '@mui/material';
import Fab from '@mui/material/Fab';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import FileCopyOutlinedIcon from '@mui/icons-material/FileCopyOutlined';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import TrialDrawer from '../../components/TrialDrawer';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import { useRouter } from 'next/navigation';

const FAB_SX = {
  bgcolor: 'primary.main',
  color: '#fff',
  boxShadow: '0px 2px 2px rgba(84, 90, 101, 0.25)',
  width: 56,
  height: 56,
  '&:hover': { bgcolor: 'primary.dark' },
  '&:active': { boxShadow: '0px 2px 2px rgba(84, 90, 101, 0.25)' },
} as const;

interface TestToTestSetProps {
  sessionToken: string;
  testId: string;
  parentButton?: React.ReactNode;
}

export default function TestToTestSet({
  sessionToken,
  testId,
  parentButton,
}: TestToTestSetProps) {
  const router = useRouter();
  const notifications = useNotifications();

  const [trialDrawerOpen, setTrialDrawerOpen] = React.useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = React.useState(false);
  const [isDeleting, setIsDeleting] = React.useState(false);
  const [isDuplicating, setIsDuplicating] = React.useState(false);

  const handleTrialSuccess = () => {
    setTrialDrawerOpen(false);
  };

  const handleDeleteConfirm = async () => {
    setIsDeleting(true);
    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      await apiFactory.getTestsClient().deleteTest(testId);
      notifications.show('Test deleted', {
        severity: 'success',
        autoHideDuration: 4000,
      });
      router.push('/tests');
    } catch {
      notifications.show('Failed to delete test', {
        severity: 'error',
        autoHideDuration: 6000,
      });
      setIsDeleting(false);
    } finally {
      setDeleteDialogOpen(false);
    }
  };

  const handleDuplicate = async () => {
    setIsDuplicating(true);
    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const testsClient = apiFactory.getTestsClient();
      const original = await testsClient.getTest(testId);
      const duplicate = await testsClient.createTest({
        prompt_id: original.prompt_id,
        behavior_id: original.behavior?.id,
        topic_id: original.topic?.id,
        category_id: original.category?.id,
        priority: original.priority,
        test_type_id: original.test_type?.id,
      });
      notifications.show('Test duplicated', {
        severity: 'success',
        autoHideDuration: 4000,
      });
      router.push(`/tests/${duplicate.id}`);
    } catch {
      notifications.show('Failed to duplicate test', {
        severity: 'error',
        autoHideDuration: 6000,
      });
    } finally {
      setIsDuplicating(false);
    }
  };

  return (
    <>
      <Box sx={{ display: 'flex', gap: '20px', alignItems: 'center' }}>
        {parentButton}

        {/* Delete FAB */}
        <Tooltip title="Delete test" placement="bottom">
          <Fab
            size="medium"
            sx={FAB_SX}
            onClick={() => setDeleteDialogOpen(true)}
          >
            <DeleteOutlineIcon sx={{ fontSize: 32 }} />
          </Fab>
        </Tooltip>

        {/* Duplicate FAB */}
        <Tooltip title="Duplicate test" placement="bottom">
          <Fab
            size="medium"
            sx={FAB_SX}
            onClick={handleDuplicate}
            disabled={isDuplicating}
          >
            {isDuplicating ? (
              <CircularProgress size={24} sx={{ color: '#fff' }} />
            ) : (
              <FileCopyOutlinedIcon sx={{ fontSize: 32 }} />
            )}
          </Fab>
        </Tooltip>

        {/* Run Test FAB */}
        <Tooltip title="Run test" placement="bottom">
          <Fab
            size="medium"
            sx={FAB_SX}
            onClick={() => setTrialDrawerOpen(true)}
          >
            <PlayArrowIcon sx={{ fontSize: 32 }} />
          </Fab>
        </Tooltip>
      </Box>

      {/* Run Test drawer */}
      <TrialDrawer
        open={trialDrawerOpen}
        onClose={() => setTrialDrawerOpen(false)}
        sessionToken={sessionToken}
        testIds={[testId]}
        onSuccess={handleTrialSuccess}
      />

      {/* Delete confirmation dialog */}
      <Dialog
        open={deleteDialogOpen}
        onClose={() => !isDeleting && setDeleteDialogOpen(false)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>Delete test?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            This action cannot be undone. The test will be permanently removed.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => setDeleteDialogOpen(false)}
            disabled={isDeleting}
          >
            Cancel
          </Button>
          <Button
            variant="contained"
            color="error"
            onClick={handleDeleteConfirm}
            disabled={isDeleting}
            startIcon={
              isDeleting ? (
                <CircularProgress size={16} color="inherit" />
              ) : undefined
            }
          >
            {isDeleting ? 'Deleting…' : 'Delete'}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
