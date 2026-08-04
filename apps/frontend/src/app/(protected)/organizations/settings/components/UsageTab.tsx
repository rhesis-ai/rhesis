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
import { BaseChartsGrid, BaseLineChart } from '@/components/common/BaseCharts';
import { filterChipSx } from '@/components/common/FilterDrawer';
import { useUsage } from '@/contexts/UsageContext';
import { useUsageHistory } from '@/hooks/useUsageHistory';
import {
  QUOTA_RESOURCE_LABELS,
  QUOTA_RESOURCE_ORDER,
  type QuotaResource,
} from '@/constants/quota';
import type {
  UsageHistoryPoint,
  UsageResourceItem,
} from '@/utils/api-client/usage-client';

function formatPeriodDate(isoDate: string): string {
  // period_start/period_end are date-only strings (YYYY-MM-DD), computed
  // in UTC by the backend. `new Date(isoDate)` parses that as UTC
  // midnight, so formatting must stay in UTC too -- otherwise
  // toLocaleDateString() converts to the viewer's local time and users
  // west of UTC see the previous day.
  return new Date(isoDate).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  });
}

// Same UTC-pinning as formatPeriodDate, and for the same reason: these are
// date-only strings, so formatting must not drift onto the previous day
// for viewers west of UTC. Includes the year (not just "MMM") since the
// 12-month option can span a calendar boundary, where two points would
// otherwise both read "Jan".
function formatMonthLabel(isoDate: string): string {
  return new Date(isoDate).toLocaleDateString('en-US', {
    month: 'short',
    year: '2-digit',
    timeZone: 'UTC',
  });
}

const HISTORY_RANGE_OPTIONS: { months: number; label: string }[] = [
  { months: 3, label: '3M' },
  { months: 6, label: '6M' },
  { months: 12, label: '12M' },
];
const DEFAULT_HISTORY_MONTHS = 6;

function toChartData(
  points: UsageHistoryPoint[]
): { name: string; used: number }[] {
  return points.map(point => ({
    name: formatMonthLabel(point.period_start),
    used: point.used,
  }));
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

function UsageHistorySection() {
  const [months, setMonths] = React.useState(DEFAULT_HISTORY_MONTHS);
  const { resources: history, loading, error } = useUsageHistory(months);

  const flowResources = QUOTA_RESOURCE_ORDER.filter(
    resource => resource in history
  );

  return (
    <SectionCard title="Usage Over Time">
      <Box sx={{ display: 'flex', gap: 1, mb: 3 }}>
        {HISTORY_RANGE_OPTIONS.map(option => (
          <Box
            key={option.months}
            component="button"
            type="button"
            onClick={() => setMonths(option.months)}
            sx={filterChipSx(months === option.months)}
          >
            {option.label}
          </Box>
        ))}
      </Box>

      {loading && (
        <Stack direction="row" spacing={2}>
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton
              // eslint-disable-next-line react/no-array-index-key -- fixed-count skeleton placeholders, never reordered
              key={i}
              variant="rectangular"
              height={180}
              sx={{ flex: 1 }}
            />
          ))}
        </Stack>
      )}

      {!loading && error && (
        <Typography color="error.main">
          Could not load usage history. Please try again later.
        </Typography>
      )}

      {!loading && !error && (
        <BaseChartsGrid>
          {flowResources.map(resource => (
            <BaseLineChart
              key={resource}
              title={QUOTA_RESOURCE_LABELS[resource as QuotaResource]}
              data={toChartData(history[resource])}
              series={[{ dataKey: 'used', name: 'Used' }]}
              height={180}
            />
          ))}
        </BaseChartsGrid>
      )}
    </SectionCard>
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
    <Stack spacing={3}>
      <SectionCard
        title="Usage"
        subtitle={
          periodLabel
            ? `Current billing period: ${periodLabel}${edition ? ` · ${edition} plan` : ''}`
            : undefined
        }
      >
        <ResourceGroup
          title="Metered Resources"
          kind="flow"
          usage={resources}
        />
        <ResourceGroup title="Resource Counts" kind="stock" usage={resources} />
      </SectionCard>
      <UsageHistorySection />
    </Stack>
  );
}
