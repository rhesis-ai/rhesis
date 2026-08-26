'use client';

import React, { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import type {
  Metric,
  ThresholdOperator,
} from '@/utils/api-client/interfaces/metric';
import type {
  ImprovedMetricFields,
  MetricTuningImprovement,
} from '@/utils/api-client/interfaces/metric-tuning';

/** The fields a reviewer reads, in the order they read them. */
const FIELD_ORDER: (keyof ImprovedMetricFields)[] = [
  'evaluation_prompt',
  'evaluation_steps',
  'reasoning',
  'explanation',
  'threshold',
  'threshold_operator',
  'min_score',
  'max_score',
  'passing_categories',
  'name',
  'description',
  'score_type',
  'categories',
];

const FIELD_LABELS: Record<keyof ImprovedMetricFields, string> = {
  evaluation_prompt: 'Evaluation prompt',
  evaluation_steps: 'Evaluation steps',
  reasoning: 'Reasoning',
  explanation: 'Explanation',
  threshold: 'Threshold',
  threshold_operator: 'Threshold operator',
  min_score: 'Minimum score',
  max_score: 'Maximum score',
  passing_categories: 'Passing categories',
  name: 'Name',
  description: 'Description',
  score_type: 'Score type',
  categories: 'Categories',
};

/**
 * How each field is edited, and how its value survives the trip through a box.
 *
 * `score_type` and `categories` are `fixed`: the API overwrites both with the
 * metric's current values whatever the model answers, so they never arrive as
 * changes and there is nothing here to edit.
 */
type FieldKind = 'text' | 'number' | 'operator' | 'list' | 'fixed';

const FIELD_KINDS: Record<keyof ImprovedMetricFields, FieldKind> = {
  evaluation_prompt: 'text',
  evaluation_steps: 'text',
  reasoning: 'text',
  explanation: 'text',
  threshold: 'number',
  threshold_operator: 'operator',
  min_score: 'number',
  max_score: 'number',
  passing_categories: 'list',
  name: 'text',
  description: 'text',
  score_type: 'fixed',
  categories: 'fixed',
};

const THRESHOLD_OPERATORS: ThresholdOperator[] = [
  '>=',
  '>',
  '<=',
  '<',
  '=',
  '!=',
];

/** Every field held as the text in its box, so typing is never fought. */
type Draft = Partial<Record<keyof ImprovedMetricFields, string>>;

/** Renders any of the field types as the one thing a reader compares: text. */
function asText(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';
  if (Array.isArray(value)) return value.join(', ');
  return String(value);
}

/** The proposed value as the text to start editing from. */
function toDraftText(value: unknown): string {
  if (value === null || value === undefined) return '';
  if (Array.isArray(value)) return value.join(', ');
  return String(value);
}

function draftFor(
  fields: ImprovedMetricFields,
  shown: (keyof ImprovedMetricFields)[]
): Draft {
  const draft: Draft = {};
  for (const field of shown) {
    draft[field] = toDraftText(fields[field]);
  }
  return draft;
}

/**
 * What is wrong with this box, or null.
 *
 * Blank is an error rather than "leave this one alone" because a metric update
 * cannot clear a field — the API drops a null instead of writing it — so an empty
 * box would apply successfully and change nothing. That is the silent divergence
 * between what was approved and what was saved that this dialog exists to stop.
 */
function errorFor(kind: FieldKind, text: string): string | null {
  const trimmed = text.trim();
  if (!trimmed) return 'Required — an empty field cannot be saved.';
  if (kind === 'number' && !Number.isFinite(Number(trimmed))) {
    return 'Must be a number.';
  }
  return null;
}

/** The edited text back in the shape the API takes. */
function fromDraft(
  fields: ImprovedMetricFields,
  draft: Draft
): ImprovedMetricFields {
  const edited: ImprovedMetricFields = { ...fields };
  for (const [key, text] of Object.entries(draft)) {
    const field = key as keyof ImprovedMetricFields;
    const trimmed = (text ?? '').trim();
    switch (FIELD_KINDS[field]) {
      case 'number':
        Object.assign(edited, { [field]: Number(trimmed) });
        break;
      case 'list':
        Object.assign(edited, {
          [field]: trimmed
            .split(',')
            .map(item => item.trim())
            .filter(Boolean),
        });
        break;
      case 'operator':
        Object.assign(edited, { [field]: trimmed as ThresholdOperator });
        break;
      default:
        Object.assign(edited, { [field]: trimmed });
    }
  }
  return edited;
}

/**
 * One field: what the metric says now on the left, what will be saved on the
 * right.
 *
 * The right-hand side is an input rather than text because the model's rewrite
 * is a draft, not a verdict — a reviewer who can see what is wrong with one
 * clause should be able to fix that clause instead of discarding the whole
 * rewrite. What is in the boxes stays exactly what Apply saves.
 *
 * The evaluation prompt gets the height: it is the field the whole feature
 * exists to rewrite, and editing it through a three-line window is editing it
 * blind.
 */
function FieldDiff({
  label,
  kind,
  current,
  value,
  error,
  expanded,
  onChange,
}: {
  label: string;
  kind: FieldKind;
  current: unknown;
  value: string;
  error: string | null;
  expanded: boolean;
  onChange: (next: string) => void;
}) {
  const currentSx = expanded
    ? { whiteSpace: 'pre-wrap' as const }
    : {
        whiteSpace: 'pre-wrap' as const,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        display: '-webkit-box',
        WebkitLineClamp: 6,
        WebkitBoxOrient: 'vertical' as const,
      };

  const shared = {
    value,
    error: Boolean(error),
    onChange: (event: React.ChangeEvent<HTMLInputElement>) =>
      onChange(event.target.value),
    fullWidth: true,
    size: 'small' as const,
    label: `${label}, proposed`,
  };

  return (
    <Box>
      <Typography variant="subtitle2" sx={{ mb: 1 }}>
        {label}
      </Typography>
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' },
          gap: 2,
        }}
      >
        <Box>
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ display: 'block', mb: 0.5 }}
          >
            Current
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={currentSx}>
            {asText(current)}
          </Typography>
        </Box>
        <Box>
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ display: 'block', mb: 0.5 }}
          >
            Proposed — edit before applying
          </Typography>
          {kind === 'operator' ? (
            <TextField {...shared} select helperText={error ?? undefined}>
              {THRESHOLD_OPERATORS.map(operator => (
                <MenuItem key={operator} value={operator}>
                  {operator}
                </MenuItem>
              ))}
            </TextField>
          ) : kind === 'number' ? (
            <TextField
              {...shared}
              type="number"
              helperText={error ?? undefined}
            />
          ) : (
            <TextField
              {...shared}
              multiline
              minRows={expanded ? 12 : 3}
              maxRows={expanded ? 24 : 8}
              helperText={
                error ?? (kind === 'list' ? 'Comma-separated.' : undefined)
              }
            />
          )}
        </Box>
      </Box>
    </Box>
  );
}

export interface MetricTuningImproveDialogProps {
  open: boolean;
  onClose: () => void;
  /** The improvement to show. Null until the call has come back. */
  improvement: MetricTuningImprovement | null;
  /** The metric as it stands, which is the left-hand column. */
  metric: Metric | null;
  /** Writes the shown fields onto the metric. All fields, or none. */
  onApply: (fields: ImprovedMetricFields) => Promise<void>;
}

/**
 * The improvement, current fields beside editable proposed ones, and one Apply.
 *
 * Nothing has been written when this opens — that is the point of the dialog
 * existing at all. The proposed side is editable so a reviewer can correct the
 * rewrite instead of taking it or leaving it whole; what is on screen stays what
 * gets saved either way, which is the invariant ADR-0006 is about.
 *
 * Applying is still all-or-nothing across fields: the score bands, the
 * evaluation steps and the reasoning are written to agree with each other in one
 * pass, so a half-applied metric is an incoherent one. Editing a value is not
 * choosing which values apply.
 */
export default function MetricTuningImproveDialog({
  open,
  onClose,
  improvement,
  metric,
  onApply,
}: MetricTuningImproveDialogProps) {
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState('');
  const [draft, setDraft] = useState<Draft>({});

  const changed = useMemo(() => {
    if (!improvement) return [];
    const named = new Set(improvement.changed);
    // Ordered here rather than taken from the API: which field a reviewer reads
    // first is the interface's decision.
    return FIELD_ORDER.filter(
      field => named.has(field) && FIELD_KINDS[field] !== 'fixed'
    );
  }, [improvement]);

  // Named rather than hidden: a reviewer has to be able to see that the rewrite
  // left the rest of the metric where it was.
  const unchanged = useMemo(() => {
    if (!improvement) return [];
    const named = new Set(improvement.changed);
    return FIELD_ORDER.filter(field => !named.has(field));
  }, [improvement]);

  // A fresh improvement is a fresh draft — edits belong to the rewrite they were
  // made against, never to the next one.
  useEffect(() => {
    if (!improvement) return;
    setDraft(draftFor(improvement.improvement, changed));
    setError('');
  }, [improvement, changed]);

  const errors = useMemo(() => {
    const found: Partial<Record<keyof ImprovedMetricFields, string>> = {};
    for (const field of changed) {
      const message = errorFor(FIELD_KINDS[field], draft[field] ?? '');
      if (message) found[field] = message;
    }
    return found;
  }, [changed, draft]);

  const complete = Object.keys(errors).length === 0;

  const handleApply = async () => {
    if (!improvement || !complete) return;
    setApplying(true);
    setError('');
    try {
      await onApply(fromDraft(improvement.improvement, draft));
      onClose();
    } catch (e) {
      setError(
        e instanceof Error ? e.message : 'Failed to apply the improvement.'
      );
    } finally {
      setApplying(false);
    }
  };

  const handleReset = () => {
    if (!improvement) return;
    setDraft(draftFor(improvement.improvement, changed));
  };

  const rejections = improvement?.rejections_used ?? 0;
  const edited =
    improvement !== null &&
    changed.some(
      field => draft[field] !== toDraftText(improvement.improvement[field])
    );

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>
        Improve this metric
        <Typography variant="body2" color="text.secondary">
          Rewritten from {rejections}{' '}
          {rejections === 1 ? 'rejection' : 'rejections'}. Edit anything below —
          nothing is saved until you apply it.
        </Typography>
      </DialogTitle>
      <DialogContent dividers>
        {changed.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            The rewrite came back the same as the metric you already have.
            Nothing to apply.
          </Typography>
        ) : (
          <Stack spacing={2.5} divider={<Divider flexItem />}>
            {changed.map(field => (
              <FieldDiff
                key={field}
                label={FIELD_LABELS[field]}
                kind={FIELD_KINDS[field]}
                current={metric ? metric[field as keyof Metric] : null}
                value={draft[field] ?? ''}
                error={errors[field] ?? null}
                // Only the evaluation prompt is worth the height.
                expanded={field === 'evaluation_prompt'}
                onChange={next =>
                  setDraft(prev => ({ ...prev, [field]: next }))
                }
              />
            ))}
          </Stack>
        )}
        {unchanged.length > 0 && changed.length > 0 && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2.5 }}>
            Unchanged:{' '}
            {unchanged
              .map(field => FIELD_LABELS[field].toLowerCase())
              .join(', ')}
            .
          </Typography>
        )}
        {error && (
          <Typography variant="body2" color="error" sx={{ mt: 2 }}>
            {error}
          </Typography>
        )}
      </DialogContent>
      <DialogActions>
        {edited && (
          <Button onClick={handleReset} sx={{ mr: 'auto' }}>
            Undo my edits
          </Button>
        )}
        <Button onClick={onClose}>Close</Button>
        <Button
          variant="contained"
          onClick={handleApply}
          disabled={applying || changed.length === 0 || !complete}
        >
          {applying ? 'Applying…' : 'Apply'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
