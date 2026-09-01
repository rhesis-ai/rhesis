'use client';

import Box from '@mui/material/Box';
import Skeleton from '@mui/material/Skeleton';
import type { Theme } from '@mui/material/styles';
import { BORDER_RADIUS } from '@/styles/theme-constants';
import { delayedRevealSx } from './DelayedReveal';
import SkeletonPageHeader from './SkeletonPageHeader';
import { skeletonTextSx } from './skeletonText';

/**
 * Loading placeholder for the insights dashboard, which is neither a table nor
 * a card directory: a compact filter bar, a pass-rate summary bar, a
 * three-column requirement breakdown, then a stack of per-requirement rows.
 *
 * Geometry mirrors `InsightsPage`, `InsightsSummaryBar` and
 * `RequirementInsightsView`.
 */

/** Compact filter bar, mirroring `TestResultsFilters` in its compact variant. */
const FILTERS = {
  gap: '20px',
  filterButtonSize: 36,
  searchWidth: 240,
  controlHeight: 38,
  chipWidths: [104, 132, 88],
} as const;

/** Pass-rate summary, mirroring `InsightsSummaryBar`. */
const SUMMARY = {
  /** Container padding, in MUI spacing units. */
  paddingX: 1.75,
  paddingY: 1.25,
  /** Container radius, in MUI spacing units. */
  radius: 1.5,
  labelWidth: 280,
  /** Height of the LinearProgress under the label. */
  barHeight: 4,
} as const;

/** Requirement breakdown, mirroring `RequirementInsightsView`. */
const BREAKDOWN = {
  columns: { xs: '1fr', md: '1fr 1fr 1fr' },
  /** Gap between the view's stacked sections, in MUI spacing units. */
  sectionGap: 3,
  /** Gap between the requirement rows, in MUI spacing units. */
  rowGap: 1.5,
  columnHeadingWidth: 128,
  columnLines: 4,
  rowHeight: 56,
  rows: 5,
} as const;

const panelBorder = (theme: Theme) =>
  `1px solid ${theme.palette.greyscale.border}`;

export interface PageDashboardSkeletonProps {
  /** FAB placeholders in the header, matching the page's action cluster. */
  actionCount?: number;
}

export default function PageDashboardSkeleton({
  actionCount = 2,
}: PageDashboardSkeletonProps = {}) {
  const columnKeys = ['passed', 'failed', 'pending'];
  const rowKeys = Array.from({ length: BREAKDOWN.rows }, (_, i) => `row-${i}`);
  const lineKeys = Array.from(
    { length: BREAKDOWN.columnLines },
    (_, i) => `line-${i}`
  );

  return (
    <Box
      sx={{ width: '100%', ...delayedRevealSx }}
      role="status"
      aria-label="Loading page"
    >
      <SkeletonPageHeader actionCount={actionCount} />

      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          gap: BREAKDOWN.sectionGap,
        }}
        aria-hidden
      >
        {/* Compact filter bar */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: FILTERS.gap }}>
          <Skeleton
            variant="rounded"
            width={FILTERS.filterButtonSize}
            height={FILTERS.filterButtonSize}
            sx={{ borderRadius: BORDER_RADIUS.sm, flexShrink: 0 }}
          />
          <Skeleton
            variant="rounded"
            width={FILTERS.searchWidth}
            height={FILTERS.controlHeight}
            sx={{
              borderRadius: '30px', // Intentional: matches SearchPill's elongated pill
              flexShrink: 0,
            }}
          />
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            {FILTERS.chipWidths.map(width => (
              <Skeleton
                key={width}
                variant="rounded"
                width={width}
                height={FILTERS.controlHeight}
                sx={{ borderRadius: BORDER_RADIUS.pill }}
              />
            ))}
          </Box>
        </Box>

        {/* Pass-rate summary bar */}
        <Box
          sx={{
            px: SUMMARY.paddingX,
            py: SUMMARY.paddingY,
            borderRadius: SUMMARY.radius,
            border: panelBorder,
            bgcolor: 'background.paper',
          }}
        >
          <Skeleton
            variant="text"
            width={SUMMARY.labelWidth}
            sx={skeletonTextSx('bodyMReg')}
          />
          <Skeleton
            variant="rounded"
            width="100%"
            height={SUMMARY.barHeight}
            sx={{ borderRadius: BORDER_RADIUS.pill }}
          />
        </Box>

        {/* Three-column requirement breakdown */}
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: BREAKDOWN.columns,
            gap: BREAKDOWN.sectionGap,
          }}
        >
          {columnKeys.map(columnKey => (
            <Box
              key={columnKey}
              sx={{
                display: 'flex',
                flexDirection: 'column',
                gap: 1,
                border: panelBorder,
                borderRadius: BORDER_RADIUS.md,
                bgcolor: 'background.paper',
                p: 2,
              }}
            >
              <Skeleton
                variant="text"
                width={BREAKDOWN.columnHeadingWidth}
                sx={skeletonTextSx('bodyMReg')}
              />
              {lineKeys.map((lineKey, idx) => (
                <Skeleton
                  key={lineKey}
                  variant="text"
                  width={idx % 2 === 0 ? '88%' : '64%'}
                  sx={skeletonTextSx('bodySReg')}
                />
              ))}
            </Box>
          ))}
        </Box>

        {/* Per-requirement rows */}
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            gap: BREAKDOWN.rowGap,
          }}
        >
          {rowKeys.map(rowKey => (
            <Skeleton
              key={rowKey}
              variant="rounded"
              width="100%"
              height={BREAKDOWN.rowHeight}
              sx={{ borderRadius: BORDER_RADIUS.md }}
            />
          ))}
        </Box>
      </Box>
    </Box>
  );
}
