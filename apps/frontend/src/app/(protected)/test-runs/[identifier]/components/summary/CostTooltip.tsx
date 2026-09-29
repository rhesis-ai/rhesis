'use client';

import React from 'react';
import { Box } from '@mui/material';
import { formatTokenCount } from '@/utils/trace-utils';

interface CostTooltipProps {
  /** The explanation line, e.g. COST_TOOLTIP or NO_COST_DATA_TOOLTIP. */
  text: string;
  inputTokens?: number | null;
  outputTokens?: number | null;
}

/**
 * The (i) tooltip on a Cost card: the explanation, then input and output tokens
 * on their own lines. Shown as two separate figures, not a breakdown of the
 * total: Google ADK folds cache-read tokens into its total, so input + output
 * can fall short of it.
 */
export default function CostTooltip({
  text,
  inputTokens,
  outputTokens,
}: CostTooltipProps) {
  const input = inputTokens ?? 0;
  const output = outputTokens ?? 0;

  if (input === 0 && output === 0) {
    return <>{text}</>;
  }

  return (
    <>
      <Box component="span" sx={{ display: 'block', mb: 0.5 }}>
        {text}
      </Box>
      <Box
        component="span"
        sx={{ display: 'block', fontVariantNumeric: 'tabular-nums' }}
      >
        {formatTokenCount(input)} input tokens
      </Box>
      <Box
        component="span"
        sx={{ display: 'block', fontVariantNumeric: 'tabular-nums' }}
      >
        {formatTokenCount(output)} output tokens
      </Box>
    </>
  );
}
