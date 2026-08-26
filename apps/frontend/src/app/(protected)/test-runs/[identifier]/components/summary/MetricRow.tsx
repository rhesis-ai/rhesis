'use client';

import React, { useCallback, useMemo } from 'react';
import { Box, Tooltip, Typography, useTheme } from '@mui/material';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import RateReviewIcon from '@mui/icons-material/RateReview';
import VerdictStrip from './VerdictStrip';
import { aggregateMetric, type CellState } from './verdict-model';
import { cellState, type TestTimingMap } from './verdict-timeline';
import { describeStrip } from './verdict-strip-render';
import {
  COLUMN_TEMPLATES,
  GEOMETRY,
  GRID_GAP,
  GRID_PADDING_X,
  INLINE_ICON_SIZE,
  STRIP_HEIGHTS,
  gridMorphTransition,
  type DensityMode,
} from './summary-tokens';
import { useReducedMotion } from '@/hooks/useReducedMotion';
import type { VerdictRow } from '@/utils/api-client/interfaces/test-run';

interface MetricRowProps {
  row: VerdictRow;
  density: DensityMode;
  testIds: string[];
  timings: TestTimingMap;
  /** This metric's position within its requirement, for the reveal cascade. */
  metricIndex: number;
  metricCount: number;
  trimmedName: string;
  fullName: string;
  dataVersion: number;
  onViewMetric?: (metricName: string, requirementId?: string) => void;
}

function MetricRowInner({
  row,
  density,
  testIds,
  timings,
  metricIndex,
  metricCount,
  trimmedName,
  fullName,
  dataVersion,
  onViewMetric,
}: MetricRowProps) {
  const theme = useTheme();
  const reducedMotion = useReducedMotion();

  const cellsAt = useCallback(
    (t: number): CellState[] => {
      const result: CellState[] = [];
      for (let i = 0; i < row.verdicts.length; i++) {
        const testId = testIds[i] ?? '';
        result.push(
          cellState(
            timings.get(testId),
            row.verdicts[i],
            metricIndex,
            metricCount,
            testId,
            t
          )
        );
      }
      return result;
    },
    [row.verdicts, testIds, timings, metricIndex, metricCount]
  );

  // Describes the settled grid: a screen reader gets the run's outcome, not
  // a snapshot of whichever cells happen to be mid-flight.
  const stripAriaLabel = useMemo(
    () => describeStrip(fullName, cellsAt(Infinity)),
    [fullName, cellsAt]
  );

  const hasOverride = row.overrides.includes('1');
  const { passRate } = aggregateMetric(row);

  const totalStr = `${row.passed + row.failed + row.pending}`;
  const passedStr = `${row.passed}`;
  const failedStr = `${row.failed}`;
  const passRateStr =
    passRate !== null ? `${Math.round(passRate * 100)}%` : '--';

  const hasDrilldown = row.failed > 0 && !!onViewMetric;

  const handleDrilldown = useCallback(() => {
    onViewMetric?.(fullName, row.requirement_id ?? undefined);
  }, [fullName, row.requirement_id, onViewMetric]);

  return (
    <Box
      role={hasDrilldown ? 'button' : undefined}
      tabIndex={hasDrilldown ? 0 : undefined}
      onClick={hasDrilldown ? handleDrilldown : undefined}
      onKeyDown={
        hasDrilldown
          ? e => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                handleDrilldown();
              }
            }
          : undefined
      }
      aria-label={hasDrilldown ? `View failures for ${fullName}` : undefined}
      sx={{
        display: 'grid',
        gridTemplateColumns: COLUMN_TEMPLATES[density],
        transition: gridMorphTransition(theme, reducedMotion),
        columnGap: `${GRID_GAP}px`,
        alignItems: 'center',
        py: 0.25,
        px: `${GRID_PADDING_X}px`,
        minHeight: GEOMETRY.rowHeight,
        cursor: hasDrilldown ? 'pointer' : 'default',
        '&:hover': {
          bgcolor: 'action.hover',
        },
        '@media print': {
          gridTemplateColumns: COLUMN_TEMPLATES.numbers,
        },
      }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 0.5,
          minWidth: 0,
          overflow: 'hidden',
        }}
      >
        <Tooltip title={fullName} placement="top" arrow>
          <Typography
            variant="body2"
            noWrap
            sx={{ display: 'block', maxWidth: '100%' }}
          >
            {trimmedName}
          </Typography>
        </Tooltip>
        {hasOverride && (
          <Tooltip
            title="Contains human review corrections"
            placement="top"
            arrow
          >
            <RateReviewIcon
              sx={{
                fontSize: INLINE_ICON_SIZE,
                color: 'primary.dark',
                flexShrink: 0,
              }}
            />
          </Tooltip>
        )}
        {hasDrilldown && (
          <Tooltip title="View failures in Tests" placement="top">
            {/* Decorative -- the whole row is the click target (see the
                outer Box's role="button"), so this isn't its own control. */}
            <OpenInNewIcon
              sx={{
                fontSize: INLINE_ICON_SIZE,
                color: 'text.secondary',
                ml: 0.5,
              }}
            />
          </Tooltip>
        )}
      </Box>

      {/* Total/Passed/Failed/Pass rate stay mounted at 0-width columns in
          modes that visually collapse them -- kept in the a11y tree
          deliberately (see RequirementGroup for the same choice). */}
      <Typography
        variant="body2"
        color="text.secondary"
        noWrap
        sx={{
          textAlign: 'right',
          fontVariantNumeric: 'tabular-nums',
          overflow: 'hidden',
        }}
      >
        {totalStr}
      </Typography>

      <Typography
        variant="body2"
        color="text.secondary"
        noWrap
        sx={{
          textAlign: 'right',
          fontVariantNumeric: 'tabular-nums',
          overflow: 'hidden',
        }}
      >
        {passedStr}
      </Typography>

      <Typography
        variant="body2"
        fontWeight={600}
        noWrap
        sx={{
          textAlign: 'right',
          fontVariantNumeric: 'tabular-nums',
          overflow: 'hidden',
          color: row.failed > 0 ? 'error.main' : 'text.secondary',
        }}
      >
        {failedStr}
      </Typography>

      <Typography
        variant="body2"
        noWrap
        sx={{
          textAlign: 'right',
          fontWeight: 600,
          fontVariantNumeric: 'tabular-nums',
          overflow: 'hidden',
        }}
      >
        {passRateStr}
      </Typography>

      <Box sx={{ overflow: 'hidden' }}>
        <VerdictStrip
          cellsAt={cellsAt}
          dataVersion={dataVersion}
          height={STRIP_HEIGHTS[density]}
          ariaLabel={stripAriaLabel}
        />
      </Box>
    </Box>
  );
}

const MetricRow = React.memo(MetricRowInner);
MetricRow.displayName = 'MetricRow';
export default MetricRow;
