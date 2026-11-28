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
import { getMetricTargetIcon } from '@/utils/metric-targets';
import { rem } from '@/styles/theme-constants';
import TargetSummaryText, { summaryPlainText } from './TargetSummaryText';

interface MetricTargetLineProps {
  target: MetricTarget;
  /** `target_summary_short` from the API: "each tool call named `issue_refund`". */
  summary: string;
  /** `target_summary`, shown in the tooltip when the short form drops conditions. */
  fullSummary?: string | null;
  /** `GET /metrics/targets`, for the per-kind icon. */
  choices: MetricTargetChoice[] | undefined;
  metricId?: string;
}

const TOOLTIP = 'Show the spans this metric judges';

/**
 * What a metric judges, as the end of a sentence under its name: "on each tool
 * call named issue_refund inside billing_agent and 1 more condition". The words
 * are the API's; the full summary is in the tooltip when the short one counts
 * conditions instead of listing them. The target links to exactly its spans.
 */
export default function MetricTargetLine({
  target,
  summary,
  fullSummary,
  choices,
  metricId,
}: MetricTargetLineProps) {
  const tooltip =
    fullSummary && fullSummary !== summary
      ? `${TOOLTIP}: ${summaryPlainText(fullSummary)}`
      : TOOLTIP;

  return (
    <>
      on{' '}
      {/* describeChild: the target stays the link's name; the tooltip describes it. */}
      <Tooltip title={tooltip} describeChild>
        <Link
          component={NextLink}
          href={tracesHrefForTarget(target, metricId)}
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
            {getMetricTargetIcon(target.on, choices, 'inherit', target.where)}
          </Box>
          <TargetSummaryText summary={summary} />
        </Link>
      </Tooltip>
    </>
  );
}
