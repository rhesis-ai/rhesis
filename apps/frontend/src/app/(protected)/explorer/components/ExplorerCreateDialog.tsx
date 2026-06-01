'use client';

import * as React from 'react';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { ApiClientFactory } from '@/utils/api-client/client-factory';

interface ExplorerCreateDialogProps {
  open: boolean;
  onClose: () => void;
  sessionToken: string;
  onCreated: () => void;
  onNavigateToSession: (sessionId: string) => void;
}

export default function ExplorerCreateDialog({
  open,
  onClose,
  sessionToken,
  onCreated,
  onNavigateToSession,
}: ExplorerCreateDialogProps) {
  const [name, setName] = React.useState('');
  const [description, setDescription] = React.useState('');
  const [submitError, setSubmitError] = React.useState<string | null>(null);
  const [submitting, setSubmitting] = React.useState(false);

  React.useEffect(() => {
    if (!open) return;
    setName('');
    setDescription('');
    setSubmitError(null);
  }, [open]);

  const handleClose = () => {
    if (!submitting) onClose();
  };

  const handleCreate = async () => {
    const trimmedName = name.trim();
    if (!trimmedName) {
      setSubmitError('Name is required');
      return;
    }

    setSubmitting(true);
    setSubmitError(null);
    try {
      const client = new ApiClientFactory(sessionToken).getExplorerClient();
      const created = await client.createExplorerTestSet(
        trimmedName,
        description.trim() || undefined
      );
      onClose();
      onCreated();
      onNavigateToSession(created.id);
    } catch (err) {
      setSubmitError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>New session</DialogTitle>
      <DialogContent>
        <TextField
          autoFocus
          margin="dense"
          label="Name"
          fullWidth
          required
          value={name}
          onChange={e => setName(e.target.value)}
          error={!!submitError && !name.trim()}
        />
        <TextField
          margin="dense"
          label="Description"
          fullWidth
          multiline
          minRows={2}
          value={description}
          onChange={e => setDescription(e.target.value)}
        />
        {submitError && (
          <Typography color="error" variant="body2" sx={{ mt: 1 }}>
            {submitError}
          </Typography>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={submitting}>
          Cancel
        </Button>
        <Button
          onClick={handleCreate}
          variant="contained"
          disabled={submitting}
        >
          {submitting ? 'Creating…' : 'Create'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
