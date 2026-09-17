'use client';

import React from 'react';
import { Box, Link } from '@mui/material';
import KpiCard from './KpiCard';
import ModelLabel from '@/components/common/ModelLabel';
import { formatCost, formatTokenCount } from '@/utils/trace-utils';
import { isCostKnown } from '../../hooks/useTestRunUsage';
import type { TraceMetricsResponse } from '@/utils/api-client/interfaces/telemetry';

const COSTS_DOC_URL =
  'https://docs.rhesis.ai/docs/tracing/costs#when-a-figure-is-missing';

/**
 * What a test run spent, and on what.
 *
 * Cost leads, because it is the figure people come to this card for; tokens and
 * the model that produced them explain it underneath. Until enrichment has
 * priced the run there is no cost to lead with, so tokens take the headline
 * instead and the card says why rather than showing a confident zero.
 */
export default function UsageCard({ usage }: { usage: TraceMetricsResponse }) {
  const tokens = `${formatTokenCount(usage.total_tokens)} tokens`;
  const models = usage.models_used ?? [];

  if (!isCostKnown(usage)) {
    // Two different silences, and the run can tell them apart: enrichment still
    // has traces to get through, or it finished and found nothing it could
    // price. Only the second is worth explaining.
    const stillPricing = usage.enriched_traces < usage.total_traces;
    return (
      <KpiCard
        title="Usage"
        value={formatTokenCount(usage.total_tokens)}
        valueSuffix="tokens"
        subtitle={
          stillPricing ? (
            'Working out what this cost'
          ) : (
            <>
              No priced models.{' '}
              <Link
                href={COSTS_DOC_URL}
                target="_blank"
                rel="noopener noreferrer"
                underline="hover"
              >
                Why?
              </Link>
            </>
          )
        }
        infoTooltip="Tokens across this run's traced LLM calls. Cost appears once enrichment has priced them, and stays absent for a model with no published price."
      />
    );
  }

  return (
    <KpiCard
      title="Usage"
      value={formatCost(usage.total_cost_usd)}
      subtitle={
        // Wraps rather than clipping: the card is narrow and a model name is
        // long, and `gemini/ge...` answers nothing.
        <Box
          component="span"
          sx={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'baseline',
            columnGap: 0.5,
          }}
        >
          <Box component="span">{tokens}</Box>
          {models.length > 0 && (
            <>
              <Box component="span">·</Box>
              <ModelLabel
                component="span"
                truncate={false}
                models={models}
                providers={usage.providers_used}
              />
            </>
          )}
        </Box>
      }
      infoTooltip="What this run's traced LLM calls cost, and the tokens behind it. Figures keep climbing while enrichment works through the run's traces."
    />
  );
}
