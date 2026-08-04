'use client';

import * as React from 'react';
import { Box, Skeleton, Stack, Typography } from '@mui/material';
import { SectionCard } from '@/components/common/SectionCard';
import { BaseChartsGrid, BaseLineChart } from '@/components/common/BaseCharts';
import { FilterButton } from '@/components/common/FilterButton';
import { BORDER_RADIUS } from '@/styles/theme';
import UsageOverTimeFilterDrawer from './UsageOverTimeFilterDrawer';
import { useUsageHistory } from '@/hooks/useUsageHistory';
import {
  QUOTA_RESOURCE_LABELS,
  QUOTA_RESOURCE_ORDER,
  type QuotaResource,
} from '@/constants/quota';
import type { UsageHistoryPoint } from '@/utils/api-client/usage-client';

// Same UTC-pinning as UsageOverviewTab's formatPeriodDate, and for the same
// reason: these are date-only strings, so formatting must not drift onto
// the previous day for viewers west of UTC. Includes the year (not just
// "MMM") since the 12-month option can span a calendar boundary, where two
// points would otherwise both read "Jan".
function formatMonthLabel(isoDate: string): string {
  return new Date(isoDate).toLocaleDateString('en-US', {
    month: 'short',
    year: '2-digit',
    timeZone: 'UTC',
  });
}

const DEFAULT_HISTORY_MONTHS = 6;

/**
 * Shared by the loading skeletons, the chart cells, and the no-history
 * cards. The three chart-cell uses must agree: see the wrapper `Box` in
 * the grid below for why the cell needs an explicit pixel height.
 */
const CHART_HEIGHT = 180;

function toChartData(
  points: UsageHistoryPoint[]
): { name: string; used: number }[] {
  return points.map(point => ({
    name: formatMonthLabel(point.period_start),
    used: point.used,
  }));
}

// The backend zero-fills every month in range, so a resource with no
// accrual at all still returns N points -- just every one at used: 0. A
// flat line at zero reads as "broken chart," not "nothing happened here
// yet," so this is checked explicitly rather than just handing an
// all-zero series to BaseLineChart.
function hasAnyUsage(points: UsageHistoryPoint[]): boolean {
  return points.some(point => point.used > 0);
}

function NoHistoryCard({ title, height }: { title: string; height: number }) {
  return (
    <Box
      sx={{
        height,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 0.5,
        border: theme => `1px solid ${theme.palette.divider}`,
        borderRadius: BORDER_RADIUS.sm,
        p: 2,
      }}
    >
      <Typography variant="subtitle2">{title}</Typography>
      <Typography variant="body2" color="text.secondary" textAlign="center">
        No history for this period
      </Typography>
    </Box>
  );
}

export default function UsageOverTimeTab() {
  const [months, setMonths] = React.useState(DEFAULT_HISTORY_MONTHS);
  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const { resources: history, loading, error } = useUsageHistory(months);

  const flowResources = QUOTA_RESOURCE_ORDER.filter(
    resource => resource in history
  );

  return (
    <SectionCard
      title="Usage Over Time"
      subtitle={`Showing the last ${months} months`}
      actions={
        <>
          <FilterButton
            onClick={() => setDrawerOpen(true)}
            hasActiveFilters={months !== DEFAULT_HISTORY_MONTHS}
          />
          <UsageOverTimeFilterDrawer
            open={drawerOpen}
            onClose={() => setDrawerOpen(false)}
            months={months}
            onChange={setMonths}
          />
        </>
      }
    >
      {loading && (
        <Stack direction="row" spacing={2}>
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton
              // eslint-disable-next-line react/no-array-index-key -- fixed-count skeleton placeholders, never reordered
              key={i}
              variant="rectangular"
              height={CHART_HEIGHT}
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
        <BaseChartsGrid columns={{ xs: 12, md: 6 }}>
          {flowResources.map(resource => {
            const label = QUOTA_RESOURCE_LABELS[resource as QuotaResource];
            const points = history[resource];
            return (
              // BaseLineChart's Card relies on `height: 100%`, which only
              // resolves against a flex row's cross-size if some sibling
              // in that row has an explicit pixel height to stretch
              // against. Two charts sharing a row (no NoHistoryCard
              // sibling to anchor it) would otherwise both collapse to
              // their title's intrinsic height -- so every cell gets an
              // explicit height here instead of relying on a neighbor.
              <Box key={resource} sx={{ height: CHART_HEIGHT }}>
                {hasAnyUsage(points) ? (
                  <BaseLineChart
                    title={label}
                    data={toChartData(points)}
                    series={[{ dataKey: 'used', name: 'Used' }]}
                    height={CHART_HEIGHT}
                  />
                ) : (
                  <NoHistoryCard title={label} height={CHART_HEIGHT} />
                )}
              </Box>
            );
          })}
        </BaseChartsGrid>
      )}
    </SectionCard>
  );
}
