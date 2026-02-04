'use client';

import { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  CircularProgress,
  Alert,
  Typography,
} from '@mui/material';

export interface TopicFormData {
  name: string;
  parentPath?: string;
}

interface TopicDialogProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: TopicFormData) => Promise<void>;
  loading?: boolean;
  mode: 'create' | 'rename';
  initialName?: string;
  parentPath?: string | null;
}

export default function TopicDialog({
  open,
  onClose,
  onSubmit,
  loading = false,
  mode,
  initialName = '',
  parentPath = null,
}: TopicDialogProps) {
  const [name, setName] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setName(initialName);
      setError(null);
    }
  }, [open, initialName]);

  const handleSubmit = async () => {
    setError(null);

    const trimmedName = name.trim();
    if (!trimmedName) {
      setError('Topic name is required');
      return;
    }

    if (trimmedName.includes('/')) {
      setError('Topic name cannot contain "/" character');
      return;
    }

    try {
      await onSubmit({
        name: trimmedName,
        parentPath: parentPath || undefined,
      });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${mode} topic`);
    }
  };

  const handleClose = () => {
    if (!loading) {
      setError(null);
      onClose();
    }
  };

  const dialogTitle = mode === 'create' ? 'Create Topic' : 'Rename Topic';
  const submitButtonText = mode === 'create'
    ? loading ? 'Creating...' : 'Create'
    : loading ? 'Saving...' : 'Save';

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>{dialogTitle}</DialogTitle>
      <DialogContent>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
          {error && (
            <Alert severity="error" onClose={() => setError(null)}>
              {error}
            </Alert>
          )}

          {mode === 'create' && parentPath && (
            <Typography variant="body2" color="text.secondary">
              Creating under: <strong>{decodeURIComponent(parentPath)}</strong>
            </Typography>
          )}

          <TextField
            label="Topic Name"
            value={name}
            onChange={e => setName(e.target.value)}
            fullWidth
            required
            autoFocus
            placeholder="e.g., Harmful Content"
            helperText={
              mode === 'create'
                ? 'Enter the name for the new topic'
                : 'Enter the new name for this topic'
            }
            disabled={loading}
            onKeyDown={e => {
              if (e.key === 'Enter' && !loading && name.trim()) {
                handleSubmit();
              }
            }}
          />
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={loading}>
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={loading || !name.trim()}
          startIcon={loading ? <CircularProgress size={16} /> : null}
        >
          {submitButtonText}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
