'use client';

import React, { useState, useMemo, useCallback } from 'react';
import {
  Box,
  Collapse,
  IconButton,
  Tooltip,
  Typography,
  useTheme,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import {
  aggregateGroupByTest,
  computeGroupRollup,
  type TestTimingMap,
} from './verdict-timeline';
import { describeStrip } from './verdict-strip-render';
import { trimSharedPrefix } from './shared-prefix';
import MetricRow from './MetricRow';
import VerdictStrip from './VerdictStrip';
import BandChip from './BandChip';
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
import type {
  VerdictRequirement,
  VerdictRow,
} from '@/utils/api-client/interfaces/test-run';
import { passRate } from '@/constants/outcomes';

interface RequirementGroupProps {
  requirement: VerdictRequirement;
  rows: VerdictRow[];
  density: DensityMode;
  testIds: string[];
  timings: TestTimingMap;
  dataVersion: number;
  onViewRequirement?: (id: string) => void;
  onViewMetric?: (name: string, reqId?: string) => void;
  /** Skip the collapsible requirement header and render the metric rows on
   *  their own -- for the pooled bucket of metrics that never linked to a
   *  requirement in the first place (execution-time and test-set metrics),
   *  a "requirement" header has nothing real to say. */
  headerless?: boolean;
}

export default function RequirementGroup({
  requirement,
  rows,
  density,
  testIds,
  timings,
  dataVersion,
  onViewRequirement,
  onViewMetric,
  headerless = false,
}: RequirementGroupProps) {
  const [expanded, setExpanded] = useState(true);

  const groupRows = useMemo(
    () => rows.filter(r => requirement.metric_keys.includes(r.metric_key)),
    [rows, requirement.metric_keys]
  );

  const metricNames = useMemo(
    () => groupRows.map(r => r.metric_name),
    [groupRows]
  );
  const trimmedNames = useMemo(
    () => trimSharedPrefix(metricNames),
    [metricNames]
  );

  const metricRows = groupRows.map((row, idx) => (
    <MetricRow
      key={row.metric_key}
      row={row}
      density={density}
      testIds={testIds}
      timings={timings}
      metricIndex={idx}
      metricCount={groupRows.length}
      trimmedName={trimmedNames[idx]}
      fullName={metricNames[idx]}
      dataVersion={dataVersion}
      onViewMetric={onViewMetric}
    />
  ));

  if (headerless) {
    return <Box sx={{ mb: 0.5 }}>{metricRows}</Box>;
  }

  return (
    <Box sx={{ mb: 0.5 }}>
      <RequirementGroupHeader
        requirement={requirement}
        groupRows={groupRows}
        density={density}
        testIds={testIds}
        timings={timings}
        dataVersion={dataVersion}
        expanded={expanded}
        onToggle={() => setExpanded(prev => !prev)}
        onViewRequirement={onViewRequirement}
      />

      <Collapse in={expanded} timeout="auto">
        {metricRows}
      </Collapse>
    </Box>
  );
}

interface RequirementGroupHeaderProps {
  requirement: VerdictRequirement;
  groupRows: VerdictRow[];
  density: DensityMode;
  testIds: string[];
  timings: TestTimingMap;
  dataVersion: number;
  expanded: boolean;
  onToggle: () => void;
  onViewRequirement?: (id: string) => void;
}

// Split out from RequirementGroup so the rollup/aggregate work below --
// entirely for display in this header -- only runs when a header actually
// renders. The pooled, headerless bucket never mounts this component.
function RequirementGroupHeader({
  requirement,
  groupRows,
  density,
  testIds,
  timings,
  dataVersion,
  expanded,
  onToggle,
  onViewRequirement,
}: RequirementGroupHeaderProps) {
  const theme = useTheme();
  const reducedMotion = useReducedMotion();

  const rollupAt = useCallback(
    (t: number) => computeGroupRollup(groupRows, testIds, timings, t),
    [groupRows, testIds, timings]
  );

  // Header counts describe the settled run, matching the strip's own final
  // state. During the animation's lag they read slightly ahead of the cells,
  // which is preferable to numbers that count backwards on a refetch.
  const agg = useMemo(
    () => aggregateGroupByTest(groupRows, testIds, timings, Infinity),
    [groupRows, testIds, timings]
  );

  const rate = useMemo(() => passRate(agg.passed, agg.failed), [agg]);
  const passRateStr = rate === null ? '--' : `${Math.round(rate)}%`;

  const stripAriaLabel = useMemo(
    () => describeStrip(requirement.name, agg.rollup),
    [requirement.name, agg.rollup]
  );

  const hasDrilldown =
    agg.failed > 0 && !!onViewRequirement && !!requirement.id;

  const handleDrilldown = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      if (requirement.id) onViewRequirement?.(requirement.id);
    },
    [requirement.id, onViewRequirement]
  );

  // Same height as the metric rows in this mode, so a rollup cell and the
  // cells under it are the same shape. Numbers mode is 0 for both.
  const stripHeight = STRIP_HEIGHTS[density];

  return (
    <Box
      role="button"
      tabIndex={0}
      onClick={onToggle}
      onKeyDown={e => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onToggle();
        }
      }}
      aria-expanded={expanded}
      sx={{
        display: 'grid',
        gridTemplateColumns: COLUMN_TEMPLATES[density],
        transition: gridMorphTransition(theme, reducedMotion),
        columnGap: `${GRID_GAP}px`,
        alignItems: 'center',
        width: '100%',
        py: 0.75,
        minHeight: GEOMETRY.rowHeight,
        px: `${GRID_PADDING_X}px`,
        textAlign: 'left',
        borderRadius: 1,
        bgcolor: 'action.hover',
        cursor: 'pointer',
        '&:hover': {
          bgcolor: 'action.selected',
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
        <ExpandMoreIcon
          sx={{
            fontSize: 18,
            transform: expanded ? 'rotate(0deg)' : 'rotate(-90deg)',
            transition: 'transform 200ms',
            flexShrink: 0,
          }}
        />
        <Typography
          variant="body2"
          fontWeight={600}
          noWrap
          sx={{ display: 'block', maxWidth: '100%' }}
          title={requirement.name}
        >
          {requirement.name}
        </Typography>
        {hasDrilldown && (
          <Tooltip title="View failures in Tests" placement="top">
            <IconButton
              size="small"
              onClick={handleDrilldown}
              sx={{ ml: 0.5, p: 0.25 }}
            >
              <OpenInNewIcon sx={{ fontSize: INLINE_ICON_SIZE }} />
            </IconButton>
          </Tooltip>
        )}
      </Box>

      {/* Total: 0-width outside Numbers mode -- kept mounted and in the
          a11y tree deliberately (density is a visual affordance, not a
          reason to hide numbers from screen reader users). */}
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
        {agg.total}
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
        {agg.passed}
      </Typography>

      <Typography
        variant="body2"
        fontWeight={600}
        noWrap
        sx={{
          textAlign: 'right',
          fontVariantNumeric: 'tabular-nums',
          overflow: 'hidden',
          color: agg.failed > 0 ? 'error.main' : 'text.secondary',
        }}
      >
        {agg.failed}
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
        {passRateStr}
      </Typography>

      <BandChip passRate={rate} />

      <Box sx={{ overflow: 'hidden' }}>
        <VerdictStrip
          cellsAt={rollupAt}
          dataVersion={dataVersion}
          height={stripHeight}
          ariaLabel={stripAriaLabel}
        />
      </Box>
    </Box>
  );
}
