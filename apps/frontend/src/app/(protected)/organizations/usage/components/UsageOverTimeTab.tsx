'use client';

import * as React from 'react';
import {
  Box,
  Grid,
  Skeleton,
  Stack,
  Typography,
  useTheme,
} from '@mui/material';
import { LineChart } from '@mui/x-charts/LineChart';
import { SectionCard } from '@/components/common/SectionCard';
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
 * Outer height of one grid cell, shared by the loading skeletons, the
 * chart cards, and the no-history cards so every cell in a row lines up.
 */
const CHART_HEIGHT = 180;

/**
 * Height handed to the plot itself. The title sits above it inside the
 * same fixed-height cell, so the plot gets what's left rather than the
 * full cell height.
 */
const CHART_TITLE_ALLOWANCE = 34;
const PLOT_HEIGHT = CHART_HEIGHT - CHART_TITLE_ALLOWANCE;

/**
 * Trimmed from the default: with no legend and a single series, the
 * stock margins leave a fixed-height plot almost no room for the line.
 */
const PLOT_MARGIN = { top: 8, right: 12, bottom: 24, left: 48 };

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

function UsageHistoryChart({
  title,
  points,
}: {
  title: string;
  points: UsageHistoryPoint[];
}) {
  const theme = useTheme();

  return (
    <Box
      sx={{
        height: CHART_HEIGHT,
        border: theme => `1px solid ${theme.palette.divider}`,
        borderRadius: BORDER_RADIUS.sm,
        px: 1.5,
        pt: 1,
      }}
    >
      <Typography variant="subtitle2" noWrap>
        {title}
      </Typography>
      <LineChart
        height={PLOT_HEIGHT}
        margin={PLOT_MARGIN}
        hideLegend
        xAxis={[
          {
            scaleType: 'point',
            data: points.map(point => formatMonthLabel(point.period_start)),
          },
        ]}
        series={[
          {
            data: points.map(point => point.used),
            label: 'Used',
            color: theme.chartPalettes.line[0],
            // Thousands separators in the tooltip: these run to millions
            // for model tokens, where a bare digit run is unreadable.
            valueFormatter: value =>
              value === null ? '' : value.toLocaleString(),
          },
        ]}
      />
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
        <Grid container spacing={2}>
          {flowResources.map(resource => {
            const label = QUOTA_RESOURCE_LABELS[resource as QuotaResource];
            const points = history[resource];
            return (
              // Two per row. Every cell is a fixed CHART_HEIGHT rather than
              // stretching, so a chart and a no-history card sharing a row
              // still line up.
              <Grid key={resource} size={{ xs: 12, md: 6 }}>
                {hasAnyUsage(points) ? (
                  <UsageHistoryChart title={label} points={points} />
                ) : (
                  <NoHistoryCard title={label} height={CHART_HEIGHT} />
                )}
              </Grid>
            );
          })}
        </Grid>
      )}
    </SectionCard>
  );
}
