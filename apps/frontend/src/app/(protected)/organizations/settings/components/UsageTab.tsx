'use client';

import * as React from 'react';
import {
  Box,
  LinearProgress,
  Skeleton,
  Stack,
  Typography,
} from '@mui/material';
import { SectionCard } from '@/components/common/SectionCard';
import { useUsage } from '@/contexts/UsageContext';
import {
  QUOTA_RESOURCE_LABELS,
  QUOTA_RESOURCE_ORDER,
  type QuotaResource,
} from '@/constants/quota';
import type { UsageResourceItem } from '@/utils/api-client/usage-client';

function formatPeriodDate(isoDate: string): string {
  return new Date(isoDate).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

function progressColor(ratio: number): 'success' | 'warning' | 'error' {
  if (ratio >= 1) return 'error';
  if (ratio >= 0.8) return 'warning';
  return 'success';
}

function ResourceMeter({
  label,
  item,
}: {
  label: string;
  item: UsageResourceItem;
}) {
  const { limit } = item;
  const ratio = limit === null ? 0 : limit === 0 ? 1 : item.used / limit;

  return (
    <Box sx={{ mb: 3, '&:last-child': { mb: 0 } }}>
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="baseline"
        sx={{ mb: 0.5 }}
      >
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          {label}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {item.used.toLocaleString()}
          {limit === null ? ' (Unlimited)' : ` / ${limit.toLocaleString()}`}
        </Typography>
      </Stack>
      <LinearProgress
        variant="determinate"
        value={limit === null ? 0 : Math.min(ratio, 1) * 100}
        color={limit === null ? 'primary' : progressColor(ratio)}
        sx={{
          height: 6,
          borderRadius: 2,
          bgcolor: theme => theme.palette.action.hover,
          '& .MuiLinearProgress-bar': {
            borderRadius: 2,
          },
        }}
      />
    </Box>
  );
}

function ResourceGroup({
  title,
  kind,
  usage,
}: {
  title: string;
  kind: UsageResourceItem['kind'];
  usage: Readonly<Record<string, UsageResourceItem>>;
}) {
  const entries = QUOTA_RESOURCE_ORDER.filter(
    resource => usage[resource]?.kind === kind
  );
  if (entries.length === 0) return null;

  return (
    <Box sx={{ mb: 4, '&:last-child': { mb: 0 } }}>
      <Typography
        variant="subtitle2"
        sx={{ mb: 2, color: 'text.secondary', textTransform: 'uppercase' }}
      >
        {title}
      </Typography>
      {entries.map(resource => (
        <ResourceMeter
          key={resource}
          label={QUOTA_RESOURCE_LABELS[resource as QuotaResource]}
          item={usage[resource]}
        />
      ))}
    </Box>
  );
}

export default function UsageTab() {
  const { resources, edition, loading, error } = useUsage();

  if (loading) {
    return (
      <SectionCard title="Usage">
        <Stack spacing={2}>
          {Array.from({ length: 4 }).map((_, i) => (
            // eslint-disable-next-line react/no-array-index-key -- fixed-count skeleton placeholders, never reordered
            <Skeleton key={i} variant="rectangular" height={48} />
          ))}
        </Stack>
      </SectionCard>
    );
  }

  if (error) {
    return (
      <SectionCard title="Usage">
        <Typography color="error.main">
          Could not load usage data. Please try again later.
        </Typography>
      </SectionCard>
    );
  }

  const anyResource = Object.values(resources)[0];
  const periodLabel = anyResource
    ? `${formatPeriodDate(anyResource.period_start)} – ${formatPeriodDate(anyResource.period_end)}`
    : null;

  return (
    <SectionCard
      title="Usage"
      subtitle={
        periodLabel
          ? `Current billing period: ${periodLabel}${edition ? ` · ${edition} plan` : ''}`
          : undefined
      }
    >
      <ResourceGroup title="Metered Resources" kind="flow" usage={resources} />
      <ResourceGroup title="Resource Counts" kind="stock" usage={resources} />
    </SectionCard>
  );
}
