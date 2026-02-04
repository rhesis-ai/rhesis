'use client';

import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  CircularProgress,
  Alert,
} from '@mui/material';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';

interface DeleteTopicDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  loading?: boolean;
  topicPath: string;
  testCount: number;
  childTopicCount: number;
}

export default function DeleteTopicDialog({
  open,
  onClose,
  onConfirm,
  loading = false,
  topicPath,
  testCount,
  childTopicCount,
}: DeleteTopicDialogProps) {
  const topicName = decodeURIComponent(topicPath.split('/').pop() || topicPath);
  const parentPath = topicPath.includes('/')
    ? topicPath.substring(0, topicPath.lastIndexOf('/'))
    : null;
  const parentName = parentPath
    ? decodeURIComponent(parentPath.split('/').pop() || parentPath)
    : 'root level';

  const handleClose = () => {
    if (!loading) {
      onClose();
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <WarningAmberIcon color="warning" />
        Delete Topic
      </DialogTitle>
      <DialogContent>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Typography>
            Are you sure you want to delete the topic{' '}
            <strong>&quot;{topicName}&quot;</strong>?
          </Typography>

          {(testCount > 0 || childTopicCount > 0) && (
            <Alert severity="warning" icon={false}>
              <Typography variant="body2" component="div">
                This action will:
                <ul style={{ margin: '8px 0', paddingLeft: '20px' }}>
                  {testCount > 0 && (
                    <li>
                      Move <strong>{testCount}</strong> test{testCount > 1 ? 's' : ''} to{' '}
                      <strong>{parentName}</strong>
                    </li>
                  )}
                  {childTopicCount > 0 && (
                    <li>
                      Move <strong>{childTopicCount}</strong> child topic
                      {childTopicCount > 1 ? 's' : ''} to <strong>{parentName}</strong>
                    </li>
                  )}
                </ul>
              </Typography>
            </Alert>
          )}

          <Typography variant="body2" color="text.secondary">
            This action cannot be undone.
          </Typography>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={loading}>
          Cancel
        </Button>
        <Button
          onClick={onConfirm}
          color="error"
          variant="contained"
          disabled={loading}
          startIcon={loading ? <CircularProgress size={16} /> : null}
        >
          {loading ? 'Deleting...' : 'Delete Topic'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
