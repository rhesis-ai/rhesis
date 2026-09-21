'use client';

import React from 'react';
import { Box, Link } from '@mui/material';
import KpiCard from './KpiCard';
import ModelLabel from '@/components/common/ModelLabel';
import {
  COST_TOOLTIP,
  COSTS_DOC_URL,
  formatTokenCount,
  isCostKnown,
  isPricingInProgress,
  NO_COST_DATA,
  NO_COST_DATA_TOOLTIP,
  PRICING_IN_PROGRESS,
} from '@/utils/trace-utils';
import { useCurrency } from '@/contexts/CurrencyContext';
import type { TraceMetricsResponse } from '@/utils/api-client/interfaces/telemetry';

/**
 * What a test run spent, and on what.
 *
 * Cost leads, because it is the figure people come to this card for; tokens and
 * the model that produced them explain it underneath. Until enrichment has
 * priced the run there is no cost to lead with, so tokens take the headline
 * instead, and once enrichment has finished without pricing anything the card
 * says so in words rather than showing a confident zero.
 */
export default function CostCard({ usage }: { usage: TraceMetricsResponse }) {
  const { format: money } = useCurrency();
  const tokens = `${formatTokenCount(usage.total_tokens)} tokens`;
  const models = usage.models_used ?? [];

  if (!isCostKnown(usage)) {
    // Two different silences, and the run can tell them apart: enrichment still
    // has traces to get through, or it finished and found nothing it could
    // price. The first is worth waiting for, the second worth explaining.
    if (isPricingInProgress(usage)) {
      return (
        <KpiCard
          title="Cost"
          value={formatTokenCount(usage.total_tokens)}
          valueSuffix="tokens"
          subtitle={PRICING_IN_PROGRESS}
          infoTooltip={COST_TOOLTIP}
        />
      );
    }

    return (
      <KpiCard
        title="Cost"
        value={NO_COST_DATA}
        valueVariant="h6"
        valueColor="text.secondary"
        subtitle={
          <>
            {tokens} &middot;{' '}
            <Link
              href={COSTS_DOC_URL}
              target="_blank"
              rel="noopener noreferrer"
              underline="hover"
            >
              Why?
            </Link>
          </>
        }
        infoTooltip={NO_COST_DATA_TOOLTIP}
      />
    );
  }

  return (
    <KpiCard
      title="Cost"
      value={money(usage.total_cost_usd)}
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
      infoTooltip={COST_TOOLTIP}
    />
  );
}
