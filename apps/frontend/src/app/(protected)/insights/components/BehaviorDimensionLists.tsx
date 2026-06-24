'use client';

import React from 'react';
import { Box, Chip, Typography } from '@mui/material';
import { getReviewBand } from '@/app/(protected)/test-runs/[identifier]/components/test-run-summary-utils';
import { DimensionItem } from '../utils/behavior-insights-utils';

function BandChip({ passRate }: { passRate: number }) {
  const band = getReviewBand(passRate);
  return (
    <Chip
      label={band.label}
      size="small"
      color={band.colorKey}
      sx={{ fontWeight: 500 }}
    />
  );
}

function DimensionRows({ items }: { items: DimensionItem[] }) {
  if (items.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ py: 1 }}>
        No data
      </Typography>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
      {items.map(item => (
        <Box
          key={item.name}
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            py: 0.75,
            borderBottom: 1,
            borderColor: 'divider',
            '&:last-child': { borderBottom: 0 },
          }}
        >
          <Typography
            variant="body2"
            sx={{
              flex: 1,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
            title={item.name}
          >
            {item.name}
          </Typography>
          <Typography
            variant="body2"
            fontWeight={600}
            sx={{ whiteSpace: 'nowrap', minWidth: 44, textAlign: 'right' }}
          >
            {item.pass_rate.toFixed(0)}%
          </Typography>
          <Box sx={{ minWidth: 100, display: { xs: 'none', sm: 'block' } }}>
            <BandChip passRate={item.pass_rate} />
          </Box>
        </Box>
      ))}
    </Box>
  );
}

interface BehaviorMetricListProps {
  items: DimensionItem[];
}

export function BehaviorMetricList({ items }: BehaviorMetricListProps) {
  return (
    <Box>
      <Typography
        variant="caption"
        fontWeight={600}
        color="text.secondary"
        sx={{ display: 'block', mb: 1, textTransform: 'uppercase' }}
      >
        Metrics
      </Typography>
      <DimensionRows items={items} />
    </Box>
  );
}

interface BehaviorTopicListProps {
  items: DimensionItem[];
}

export function BehaviorTopicList({ items }: BehaviorTopicListProps) {
  return (
    <Box sx={{ mt: 2 }}>
      <Typography
        variant="caption"
        fontWeight={600}
        color="text.secondary"
        sx={{ display: 'block', mb: 1, textTransform: 'uppercase' }}
      >
        Topics
      </Typography>
      <DimensionRows items={items} />
    </Box>
  );
}
