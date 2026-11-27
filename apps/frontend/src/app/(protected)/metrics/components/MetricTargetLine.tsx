'use client';

import * as React from 'react';
import NextLink from 'next/link';
import Box from '@mui/material/Box';
import Link from '@mui/material/Link';
import Tooltip from '@mui/material/Tooltip';
import { tracesHrefForTarget } from '@/app/(protected)/traces/components/target-filters';
import type {
  MetricTarget,
  MetricTargetChoice,
} from '@/utils/api-client/interfaces/metric';
import { getMetricTargetIcon, targetPhrase } from '@/utils/metric-targets';
import { CODE_FONT_SIZE, rem } from '@/styles/theme-constants';

interface MetricTargetLineProps {
  target: MetricTarget;
  choices: MetricTargetChoice[] | undefined;
  metricId?: string;
}

/**
 * What a metric judges, as the end of a sentence under its name: "on each tool
 * call named issue_refund". The target links to the Traces page filtered to the
 * spans it picks. Nothing renders until the target labels load.
 */
export default function MetricTargetLine({
  target,
  choices,
  metricId,
}: MetricTargetLineProps) {
  const phrase = targetPhrase(target, choices);
  if (!phrase) return null;

  return (
    <>
      on{' '}
      {/* describeChild: the target stays the link's name; the tooltip describes it. */}
      <Tooltip title="Show the spans this metric judges" describeChild>
        <Link
          component={NextLink}
          href={tracesHrefForTarget(target, choices, metricId)}
          underline="hover"
          data-testid="metric-target-link"
          // The card opens the metric; this link opens the target's spans instead.
          onClick={(e: React.MouseEvent) => e.stopPropagation()}
        >
          <Box
            component="span"
            aria-hidden
            sx={{
              display: 'inline-flex',
              verticalAlign: 'middle',
              mr: 0.5,
              '& .MuiSvgIcon-root': { fontSize: rem(16) },
            }}
          >
            {getMetricTargetIcon(target.on, choices, 'inherit')}
          </Box>
          {phrase}
          {target.name && (
            <>
              {' named '}
              <Box
                component="code"
                sx={{
                  fontFamily: theme => theme.typography.fontFamilyCode,
                  fontSize: rem(CODE_FONT_SIZE),
                }}
              >
                {target.name}
              </Box>
            </>
          )}
        </Link>
      </Tooltip>
    </>
  );
}
