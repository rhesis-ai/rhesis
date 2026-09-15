'use client';

import React from 'react';
import { Box, Tooltip } from '@mui/material';
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';
import CircleOutlinedIcon from '@mui/icons-material/CircleOutlined';
import { ANNOTATION_COPY } from './annotation-copy';

export interface AnnotationIndicatorProps {
  /** The human verdict, or null when nothing has been annotated. */
  verdict: 'passed' | 'failed' | null;
  /** True when the human verdict disagrees with the automated one. */
  hasConflict?: boolean;
  annotator?: string | null;
  comment?: string | null;
  /** Opacity applied to the empty state, so grids can mute it further. */
  emptyOpacity?: number;
}

function tooltipFor(
  verdict: 'passed' | 'failed',
  annotator?: string | null,
  comment?: string | null
): string {
  const outcome = verdict === 'passed' ? 'Passed' : 'Failed';
  if (!annotator) return ANNOTATION_COPY.indicatorAnnotated;
  const base = `${ANNOTATION_COPY.indicatorBy(annotator)}: ${outcome}`;
  return comment ? `${base} - ${comment}` : base;
}

/**
 * Whether a human has annotated something, and whether they agreed.
 *
 * One icon with three states: nothing yet, a verdict that matches automation,
 * and a verdict that contradicts it (the same icon in the warning colour, so a
 * disagreement reads differently from a plain pass or fail).
 */
export default function AnnotationIndicator({
  verdict,
  hasConflict = false,
  annotator,
  comment,
  emptyOpacity,
}: AnnotationIndicatorProps) {
  if (verdict === null) {
    return (
      <Tooltip title={ANNOTATION_COPY.indicatorNone}>
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <CircleOutlinedIcon
            fontSize="small"
            sx={{ color: 'action.disabled', opacity: emptyOpacity }}
          />
        </Box>
      </Tooltip>
    );
  }

  const Icon = verdict === 'passed' ? CheckIcon : CloseIcon;
  const color = hasConflict
    ? 'warning.main'
    : verdict === 'passed'
      ? 'success.main'
      : 'error.main';

  return (
    <Tooltip title={tooltipFor(verdict, annotator, comment)}>
      <Box sx={{ display: 'flex', alignItems: 'center' }}>
        <Icon fontSize="small" sx={{ color }} />
      </Box>
    </Tooltip>
  );
}
