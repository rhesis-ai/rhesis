'use client';

import React, { useState, useEffect } from 'react';
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
} from '@mui/material';

export interface TestFormData {
  id?: string;
  input: string;
  output: string;
  topic: string;
}

interface TestDialogProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (test: TestFormData) => Promise<void>;
  selectedTopic: string | null;
  loading?: boolean;
  initialData?: TestFormData | null;
  mode?: 'add' | 'edit';
}

export default function AddTestDialog({
  open,
  onClose,
  onSubmit,
  selectedTopic,
  loading = false,
  initialData = null,
  mode = 'add',
}: TestDialogProps) {
  const [input, setInput] = useState('');
  const [output, setOutput] = useState('');
  const [topic, setTopic] = useState('');
  const [error, setError] = useState<string | null>(null);

  // Initialize/reset form when dialog opens or initialData changes
  useEffect(() => {
    if (open) {
      if (initialData) {
        setInput(initialData.input);
        setOutput(initialData.output);
        setTopic(initialData.topic);
      } else {
        setInput('');
        setOutput('');
        setTopic(selectedTopic ? decodeURIComponent(selectedTopic) : '');
      }
      setError(null);
    }
  }, [open, initialData, selectedTopic]);

  const handleSubmit = async () => {
    setError(null);

    if (!input.trim()) {
      setError('Input is required');
      return;
    }

    if (!topic.trim()) {
      setError('Topic is required');
      return;
    }

    try {
      await onSubmit({
        id: initialData?.id,
        input: input.trim(),
        output: output.trim(),
        topic: topic.trim(),
      });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${mode} test`);
    }
  };

  const isEditing = mode === 'edit';
  const dialogTitle = isEditing ? 'Edit Test' : 'Add Test';
  const submitButtonText = isEditing
    ? loading
      ? 'Saving...'
      : 'Save'
    : loading
      ? 'Adding...'
      : 'Add Test';

  const handleClose = () => {
    if (!loading) {
      setError(null);
      onClose();
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
      <DialogTitle>{dialogTitle}</DialogTitle>
      <DialogContent>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
          {error && (
            <Alert severity="error" onClose={() => setError(null)}>
              {error}
            </Alert>
          )}

          <TextField
            label="Input"
            value={input}
            onChange={e => setInput(e.target.value)}
            multiline
            rows={3}
            fullWidth
            required
            placeholder="Enter the test input (prompt)"
            disabled={loading}
          />

          <TextField
            label="Expected Output"
            value={output}
            onChange={e => setOutput(e.target.value)}
            multiline
            rows={3}
            fullWidth
            placeholder="Enter the expected output (optional)"
            disabled={loading}
          />

          <TextField
            label="Topic"
            value={topic}
            onChange={e => setTopic(e.target.value)}
            fullWidth
            required
            placeholder="e.g., Safety/Harmful Content"
            helperText="Use '/' to create nested topics"
            disabled={loading}
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
          disabled={loading || !input.trim() || !topic.trim()}
          startIcon={loading ? <CircularProgress size={16} /> : null}
        >
          {submitButtonText}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
