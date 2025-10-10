import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  CircularProgress,
  TextField,
  Alert,
} from '@mui/material';

interface DeleteModalProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  isLoading?: boolean;
  title?: string;
  message?: React.ReactNode;
  itemName?: string;
  itemType?: string;
  confirmButtonText?: string;
  cancelButtonText?: string;
  requireConfirmation?: boolean;
  confirmationText?: string;
  confirmationLabel?: string;
  warningMessage?: string;
  showTopBorder?: boolean;
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
  cancelButtonText = 'Cancel',
  requireConfirmation = false,
  confirmationText,
  confirmationLabel,
  warningMessage,
  showTopBorder = false,
}: DeleteModalProps) {
  const [inputValue, setInputValue] = useState('');
  const [confirmError, setConfirmError] = useState('');

  // Reset input when dialog opens/closes
  useEffect(() => {
    if (open) {
      setInputValue('');
      setConfirmError('');
    }
  }, [open]);

  // Generate default title if not provided
  const defaultTitle =
    title || `Delete ${itemType.charAt(0).toUpperCase() + itemType.slice(1)}`;

  // Generate default message if not provided
  const defaultMessage =
    message ||
    (itemName
      ? `Are you sure you want to delete the ${itemType} "${itemName}"? Don't worry, related data will not be deleted, only this record.`
      : `Are you sure you want to delete this ${itemType}? Don't worry, related data will not be deleted, only this record.`);

  // Generate default confirm button text if not provided
  const defaultConfirmText =
    confirmButtonText || (isLoading ? 'Deleting...' : 'Delete');

  const handleConfirm = () => {
    if (requireConfirmation && confirmationText) {
      if (inputValue !== confirmationText) {
        setConfirmError(`Please type "${confirmationText}" exactly to confirm`);
        return;
      }
    }
    onConfirm();
  };

  const isConfirmDisabled =
    isLoading ||
    (requireConfirmation && !!confirmationText && inputValue !== confirmationText);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      aria-labelledby="delete-dialog-title"
      aria-describedby="delete-dialog-description"
      maxWidth="sm"
      fullWidth
      PaperProps={
        showTopBorder
          ? {
              sx: {
                borderTop: '4px solid',
                borderColor: 'error.main',
              },
            }
          : undefined
      }
    >
      <DialogTitle id="delete-dialog-title">{defaultTitle}</DialogTitle>
      <DialogContent>
        {warningMessage && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            {warningMessage}
          </Alert>
        )}
        <Typography id="delete-dialog-description" sx={{ mb: requireConfirmation ? 2 : 0 }}>
          {defaultMessage}
        </Typography>
        {requireConfirmation && confirmationText && (
          <>
            <Typography variant="body2" sx={{ mb: 1 }}>
              {confirmationLabel || `To confirm, please type:`}{' '}
              <Typography component="span" fontWeight="medium">
                {confirmationText}
              </Typography>
            </Typography>
            <TextField
              fullWidth
              placeholder={`Type "${confirmationText}" to confirm`}
              value={inputValue}
              onChange={e => {
                setInputValue(e.target.value);
                setConfirmError('');
              }}
              disabled={isLoading}
              error={!!confirmError}
              helperText={confirmError}
              autoFocus
            />
          </>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={isLoading}>
          {cancelButtonText}
        </Button>
        <Button
          onClick={handleConfirm}
          color="error"
          disabled={isConfirmDisabled}
          startIcon={isLoading ? <CircularProgress size={16} /> : undefined}
          autoFocus={!requireConfirmation}
        >
          {defaultConfirmText}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
