'use client';

import React, { useEffect, useState } from 'react';
import { Box, TextField, Typography } from '@mui/material';
import BaseDrawer from '@/components/common/BaseDrawer';
import type {
  MetricTuningCase,
  MetricTuningCaseCreate,
} from '@/utils/api-client/interfaces/metric-tuning';

export interface MetricTuningCaseDialogProps {
  open: boolean;
  onClose: () => void;
  /** Present when editing; absent when adding. */
  tuningCase?: MetricTuningCase | null;
  /** Whether this metric judges against a reference answer, so one is asked for. */
  groundTruthRequired?: boolean;
  onSubmit: (data: MetricTuningCaseCreate) => Promise<void>;
}

/**
 * Add or edit one tuning case.
 *
 * A case is an input and the answer being judged — no verdict. What the metric
 * should have said is not written down in advance; a reviewer judges what it
 * actually said after a run.
 */
export default function MetricTuningCaseDialog({
  open,
  onClose,
  tuningCase,
  groundTruthRequired = false,
  onSubmit,
}: MetricTuningCaseDialogProps) {
  const [input, setInput] = useState('');
  const [output, setOutput] = useState('');
  const [referenceAnswer, setReferenceAnswer] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  // Reset the form whenever the drawer opens, so a previous edit does not leak
  // into the next add.
  useEffect(() => {
    if (!open) return;
    setInput(tuningCase?.input ?? '');
    setOutput(tuningCase?.output ?? '');
    setReferenceAnswer(tuningCase?.reference_answer ?? '');
    setError('');
  }, [open, tuningCase]);

  // These two are what the metric is run over, so a case without them cannot be
  // run at all.
  const complete = input.trim().length > 0 && output.trim().length > 0;

  const handleSave = async () => {
    if (!complete) {
      setError('An input and the answer being judged are both required.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      await onSubmit({
        input: input.trim(),
        output: output.trim(),
        // Sent even when blank: on an update an omitted field means "leave the
        // stored one alone", and this form submits every field, so an emptied
        // reference answer has to say so rather than say nothing.
        reference_answer: referenceAnswer.trim(),
      });
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save the case.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title={tuningCase ? 'Edit tuning case' : 'Add tuning case'}
      onSave={handleSave}
      loading={saving}
      saveDisabled={!complete}
      error={error}
      saveButtonText={tuningCase ? 'Save' : 'Add case'}
    >
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        <Typography variant="body2" color="text.secondary">
          A case is an input and the answer this metric has to judge. Run the
          metric over it, then say whether what it came back with was right.
        </Typography>

        <TextField
          label="Input"
          value={input}
          onChange={e => setInput(e.target.value)}
          required
          fullWidth
          multiline
          minRows={2}
          placeholder="How are you?"
          helperText="What was asked of the system under test."
        />

        <TextField
          label="Output"
          value={output}
          onChange={e => setOutput(e.target.value)}
          required
          fullWidth
          multiline
          minRows={3}
          placeholder="I am fine, thanks for asking."
          helperText="The answer this metric has to judge."
        />

        {groundTruthRequired && (
          <TextField
            label="Reference answer"
            value={referenceAnswer}
            onChange={e => setReferenceAnswer(e.target.value)}
            fullWidth
            multiline
            minRows={2}
            placeholder="I am fine, thanks for asking."
            helperText="What the system under test should have answered. This metric judges against it."
          />
        )}
      </Box>
    </BaseDrawer>
  );
}
