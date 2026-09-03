'use client';

import React, { useEffect, useState } from 'react';
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  TextField,
  Typography,
} from '@mui/material';

export interface MetricTuningRejectDialogProps {
  open: boolean;
  onClose: () => void;
  /** The verdict being rejected, shown so the reviewer writes about the right one. */
  verdict: string | null;
  onSubmit: (comment: string) => Promise<void>;
}

/**
 * Collects the comment a rejection requires.
 *
 * The comment is the product of this whole feature — it is what someone reads
 * when rewriting the evaluation prompt — so Save stays disabled until there is
 * one, rather than letting the API return a 400 for a blank.
 */
export default function MetricTuningRejectDialog({
  open,
  onClose,
  verdict,
  onSubmit,
}: MetricTuningRejectDialogProps) {
  const [comment, setComment] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) return;
    setComment('');
    setError('');
  }, [open]);

  const complete = comment.trim().length > 0;

  const handleSave = async () => {
    if (!complete) return;
    setSaving(true);
    setError('');
    try {
      await onSubmit(comment.trim());
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save the review.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>What did the metric get wrong?</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          {verdict && (
            <Typography variant="body2" color="text.secondary">
              The metric said <strong>{verdict}</strong> for this case.
            </Typography>
          )}
          <TextField
            label="Comment"
            value={comment}
            onChange={e => setComment(e.target.value)}
            required
            fullWidth
            multiline
            minRows={3}
            autoFocus
            placeholder="This answer is toxic, so a passing score is wrong."
            helperText="Required. Whoever rewrites the evaluation prompt reads this."
          />
          {error && (
            <Typography variant="body2" color="error">
              {error}
            </Typography>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          variant="contained"
          onClick={handleSave}
          disabled={!complete || saving}
        >
          Save
        </Button>
      </DialogActions>
    </Dialog>
  );
}
