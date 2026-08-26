'use client';

import React, { useCallback, useMemo } from 'react';
import { Box, IconButton, Tooltip, Typography, useTheme } from '@mui/material';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import RateReviewIcon from '@mui/icons-material/RateReview';
import VerdictStrip from './VerdictStrip';
import { cellState, aggregateMetric, type CellState } from './verdict-model';
import { describeStrip } from './verdict-strip-render';
import {
  COLUMN_TEMPLATES,
  GEOMETRY,
  GRID_GAP,
  GRID_PADDING_X,
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
  generatingIds: Set<string>;
  evaluatingIds: Set<string>;
  trimmedName: string;
  fullName: string;
  dataVersion: number;
  onViewMetric?: (metricName: string, requirementId?: string) => void;
}

function MetricRowInner({
  row,
  density,
  testIds,
  generatingIds,
  evaluatingIds,
  trimmedName,
  fullName,
  dataVersion,
  onViewMetric,
}: MetricRowProps) {
  const theme = useTheme();
  const reducedMotion = useReducedMotion();

  const cells: CellState[] = useMemo(() => {
    const result: CellState[] = [];
    for (let i = 0; i < row.verdicts.length; i++) {
      const tid = testIds[i] ?? '';
      result.push(
        cellState(
          row.verdicts[i],
          generatingIds.has(tid),
          evaluatingIds.has(tid)
        )
      );
    }
    return result;
  }, [row.verdicts, testIds, generatingIds, evaluatingIds]);

  const stripAriaLabel = useMemo(
    () => describeStrip(fullName, cells),
    [fullName, cells]
  );

  const hasOverride = row.overrides.includes('1');
  const { passRate } = aggregateMetric(row);

  const totalStr = `${row.passed + row.failed + row.pending}`;
  const passedStr = `${row.passed}`;
  const failedStr = `${row.failed}`;
  const passRateStr =
    passRate !== null ? `${Math.round(passRate * 100)}%` : '--';

  const hasDrilldown = row.failed > 0 && !!onViewMetric;

  const handleDrilldown = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      onViewMetric?.(fullName, row.requirement_id ?? undefined);
    },
    [fullName, row.requirement_id, onViewMetric]
  );

  return (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: COLUMN_TEMPLATES[density],
        transition: gridMorphTransition(theme, reducedMotion),
        columnGap: `${GRID_GAP}px`,
        alignItems: 'center',
        py: 0.25,
        px: `${GRID_PADDING_X}px`,
        minHeight: GEOMETRY.rowHeight,
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
              sx={{ fontSize: 14, color: 'primary.dark', flexShrink: 0 }}
            />
          </Tooltip>
        )}
        {hasDrilldown && (
          <Tooltip title="View failures in Test Cases" placement="top">
            <IconButton
              size="small"
              onClick={handleDrilldown}
              sx={{ ml: 0.5, p: 0.25 }}
            >
              <OpenInNewIcon sx={{ fontSize: 14 }} />
            </IconButton>
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
          cells={cells}
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
