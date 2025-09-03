import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
} from '@mui/material';

interface DeleteCommentModalProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  isLoading?: boolean;
}

export function DeleteCommentModal({ 
  open, 
  onClose, 
  onConfirm, 
  isLoading = false 
}: DeleteCommentModalProps) {
  return (
    <Dialog open={open} onClose={onClose}>
      <DialogTitle>Delete Comment</DialogTitle>
      <DialogContent>
        <Typography>
          Are you sure you want to delete this comment? This action cannot be undone.
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={isLoading}>
          Cancel
        </Button>
        <Button onClick={onConfirm} color="error" disabled={isLoading}>
          {isLoading ? 'Deleting...' : 'Delete'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
