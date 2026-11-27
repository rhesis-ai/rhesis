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
import {
  getMetricTargetIcon,
  moreConditionsText,
  targetPhrase,
  whereConditions,
} from '@/utils/metric-targets';
import { CODE_FONT_SIZE, rem } from '@/styles/theme-constants';

interface MetricTargetLineProps {
  target: MetricTarget;
  choices: MetricTargetChoice[] | undefined;
  metricId?: string;
}

const TOOLTIP = 'Show the spans this metric judges';

function Code({ children }: { children: React.ReactNode }) {
  return (
    <Box
      component="code"
      sx={{
        fontFamily: theme => theme.typography.fontFamilyCode,
        fontSize: rem(CODE_FONT_SIZE),
      }}
    >
      {children}
    </Box>
  );
}

/**
 * What a metric judges, as the end of a sentence under its name: "on each tool
 * call named issue_refund inside billing_agent and 1 more condition". Nothing is
 * hidden: attribute conditions are counted here and listed in the tooltip. The
 * target links to the Traces page filtered to the spans it picks. Nothing
 * renders until the target labels load.
 */
export default function MetricTargetLine({
  target,
  choices,
  metricId,
}: MetricTargetLineProps) {
  const phrase = targetPhrase(target, choices);
  if (!phrase) return null;
  const conditions = whereConditions(target);
  const tooltip = conditions.length
    ? `${TOOLTIP}. Also where ${conditions.join(' and ')}`
    : TOOLTIP;

  return (
    <>
      on{' '}
      {/* describeChild: the target stays the link's name; the tooltip describes it. */}
      <Tooltip title={tooltip} describeChild>
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
              <Code>{target.name}</Code>
            </>
          )}
          {target.within && (
            <>
              {' inside '}
              <Code>{target.within}</Code>
            </>
          )}
          {conditions.length > 0 && ` ${moreConditionsText(conditions.length)}`}
        </Link>
      </Tooltip>
    </>
  );
}
