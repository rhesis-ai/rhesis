'use client';

import * as React from 'react';
import { Box, type SxProps, type Theme } from '@mui/material';
import { impactColor } from '@/app/(protected)/requirements/components/requirement-lookups';

interface InsightsImpactDotProps {
  /** The impact name; picks the same colour as the requirement cards. */
  impact: string;
  /** Set when the impact is written out beside the dot. */
  decorative?: boolean;
  sx?: SxProps<Theme>;
}

/** The coloured impact dot from the requirement cards, for Insights rows and filters. */
export default function InsightsImpactDot({
  impact,
  decorative = false,
  sx,
}: InsightsImpactDotProps) {
  return (
    <Box
      component="span"
      {...(decorative
        ? { 'aria-hidden': true }
        : { role: 'img', 'aria-label': `${impact} impact` })}
      data-testid="insights-impact-dot"
      sx={[
        {
          display: 'inline-block',
          width: theme => theme.spacing(1),
          height: theme => theme.spacing(1),
          borderRadius: '50%',
          bgcolor: impactColor(impact),
        },
        ...(Array.isArray(sx) ? sx : sx ? [sx] : []),
      ]}
    />
  );
}
