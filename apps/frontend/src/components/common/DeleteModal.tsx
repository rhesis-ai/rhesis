import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  CircularProgress,
} from '@mui/material';

interface DeleteModalProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  isLoading?: boolean;
  title?: string;
  message?: string;
  itemName?: string;
  itemType?: string;
  confirmButtonText?: string;
  cancelButtonText?: string;
}

export function DeleteModal({ 
  open, 
  onClose, 
  onConfirm, 
  isLoading = false,
  title,
  message,
  itemName,
  itemType = 'item',
  confirmButtonText,
  cancelButtonText = 'Cancel'
}: DeleteModalProps) {
  // Generate default title if not provided
  const defaultTitle = title || `Delete ${itemType.charAt(0).toUpperCase() + itemType.slice(1)}`;
  
  // Generate default message if not provided
  const defaultMessage = message || 
    (itemName 
      ? `Are you sure you want to permanently delete the ${itemType} "${itemName}"? This action cannot be undone.`
      : `Are you sure you want to delete this ${itemType}? This action cannot be undone.`
    );
  
  // Generate default confirm button text if not provided
  const defaultConfirmText = confirmButtonText || (isLoading ? 'Deleting...' : 'Delete');

  return (
    <Dialog 
      open={open} 
      onClose={onClose}
      aria-labelledby="delete-dialog-title"
      aria-describedby="delete-dialog-description"
    >
      <DialogTitle id="delete-dialog-title">
        {defaultTitle}
      </DialogTitle>
      <DialogContent>
        <Typography id="delete-dialog-description">
          {defaultMessage}
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={isLoading}>
          {cancelButtonText}
        </Button>
        <Button 
          onClick={onConfirm} 
          color="error" 
          disabled={isLoading}
          startIcon={isLoading ? <CircularProgress size={16} /> : undefined}
          autoFocus
        >
          {defaultConfirmText}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
