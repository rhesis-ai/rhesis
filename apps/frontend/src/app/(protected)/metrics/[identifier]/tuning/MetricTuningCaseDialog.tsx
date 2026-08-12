'use client';

import React, { useEffect, useState } from 'react';
import {
  Box,
  FormControl,
  FormControlLabel,
  FormLabel,
  MenuItem,
  Radio,
  RadioGroup,
  TextField,
  Typography,
} from '@mui/material';
import BaseDrawer from '@/components/common/BaseDrawer';
import type { ScoreType } from '@/utils/api-client/interfaces/metric';
import type {
  MetricTuningCase,
  MetricTuningCaseCreate,
} from '@/utils/api-client/interfaces/metric-tuning';

const BINARY_OPTIONS = [
  { value: 'pass', label: 'Pass — the metric should accept this' },
  { value: 'fail', label: 'Fail — the metric should reject this' },
] as const;

export interface MetricTuningCaseDialogProps {
  open: boolean;
  onClose: () => void;
  /** Present when editing; absent when adding. */
  tuningCase?: MetricTuningCase | null;
  /** Decides which verdict control is rendered and what counts as valid. */
  scoreType: ScoreType;
  /** Bounds for a numeric metric's verdict, when it declares them. */
  minScore?: number;
  maxScore?: number;
  /** The metric's own categories, for a categorical metric. */
  categories?: string[];
  onSubmit: (data: MetricTuningCaseCreate) => Promise<void>;
}

/** The verdict a fresh form starts on, so the field is never empty. */
function defaultVerdict(scoreType: ScoreType, categories?: string[]): string {
  if (scoreType === 'categorical') return categories?.[0] ?? '';
  if (scoreType === 'numeric') return '';
  return 'fail';
}

/**
 * Add or edit one tuning case.
 *
 * The verdict control is rendered from the metric's score type rather than
 * being free text: the backend validates the verdict against the metric anyway,
 * and for a field with a handful of valid values, letting someone type
 * "passed" and rejecting it after submit is a bad trade.
 */
export default function MetricTuningCaseDialog({
  open,
  onClose,
  tuningCase,
  scoreType,
  minScore,
  maxScore,
  categories,
  onSubmit,
}: MetricTuningCaseDialogProps) {
  const [input, setInput] = useState('');
  const [output, setOutput] = useState('');
  const [expectedOutput, setExpectedOutput] = useState('');
  const [expected, setExpected] = useState<string>('');
  const [rationale, setRationale] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  // Reset the form whenever the drawer opens, so a previous edit does not leak
  // into the next add.
  useEffect(() => {
    if (!open) return;
    setInput(tuningCase?.input ?? '');
    setOutput(tuningCase?.output ?? '');
    setExpectedOutput(tuningCase?.expected_output ?? '');
    setExpected(tuningCase?.expected ?? defaultVerdict(scoreType, categories));
    setRationale(tuningCase?.rationale ?? '');
    setError('');
  }, [open, tuningCase, scoreType, categories]);

  const complete =
    input.trim().length > 0 &&
    output.trim().length > 0 &&
    expected.trim().length > 0;

  const handleSave = async () => {
    if (!complete) {
      setError('Input, output and an expected verdict are all required.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      await onSubmit({
        input: input.trim(),
        output: output.trim(),
        expected_output: expectedOutput.trim() || null,
        expected: expected.trim(),
        rationale: rationale.trim() || null,
      });
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save the case.');
    } finally {
      setSaving(false);
    }
  };

  const renderVerdictControl = () => {
    if (scoreType === 'numeric') {
      const bounded = minScore !== undefined && maxScore !== undefined;
      return (
        <TextField
          label="Expected verdict"
          type="number"
          value={expected}
          onChange={e => setExpected(e.target.value)}
          required
          fullWidth
          inputProps={{ min: minScore, max: maxScore, step: 'any' }}
          helperText={
            bounded
              ? `The score you expect, between ${minScore} and ${maxScore}.`
              : 'The score you expect this metric to return.'
          }
        />
      );
    }

    if (scoreType === 'categorical') {
      const options = categories ?? [];
      return (
        <TextField
          select
          label="Expected verdict"
          value={expected}
          onChange={e => setExpected(e.target.value)}
          required
          fullWidth
          helperText={
            options.length
              ? "The category you expect. Only this metric's own categories are valid."
              : 'This metric has no categories defined yet.'
          }
        >
          {options.map(category => (
            <MenuItem key={category} value={category}>
              {category}
            </MenuItem>
          ))}
        </TextField>
      );
    }

    return (
      <FormControl>
        <FormLabel id="expected-verdict-label">Expected verdict</FormLabel>
        <RadioGroup
          aria-labelledby="expected-verdict-label"
          value={expected}
          onChange={e => setExpected(e.target.value)}
        >
          {BINARY_OPTIONS.map(option => (
            <FormControlLabel
              key={option.value}
              value={option.value}
              control={<Radio />}
              label={option.label}
            />
          ))}
        </RadioGroup>
      </FormControl>
    );
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
          A case is an example the metric has to get right: what went in, what
          came back, and the verdict you expect from the metric.
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

        <TextField
          label="Expected output"
          value={expectedOutput}
          onChange={e => setExpectedOutput(e.target.value)}
          fullWidth
          multiline
          minRows={2}
          placeholder="I am fine, thanks for asking."
          helperText="Optional. What the system under test should have answered — only needed when this metric judges against a reference."
        />

        {renderVerdictControl()}

        <TextField
          label="Why"
          value={rationale}
          onChange={e => setRationale(e.target.value)}
          fullWidth
          multiline
          minRows={2}
          placeholder="The metric scored 0, but this is toxic so it should be 1."
          helperText="Optional. Your reasoning, for whoever reviews this later."
        />
      </Box>
    </BaseDrawer>
  );
}
