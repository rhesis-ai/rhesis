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
import { aggregateGroupByTest } from './verdict-model';
import { describeStrip } from './verdict-strip-render';
import { trimSharedPrefix } from './shared-prefix';
import MetricRow from './MetricRow';
import VerdictStrip from './VerdictStrip';
import {
  COLUMN_TEMPLATES,
  GEOMETRY,
  GRID_GAP,
  GRID_PADDING_X,
  ROLLUP_HEIGHT,
  gridMorphTransition,
  type DensityMode,
} from './summary-tokens';
import { useReducedMotion } from '@/hooks/useReducedMotion';
import type {
  VerdictRequirement,
  VerdictRow,
} from '@/utils/api-client/interfaces/test-run';

interface RequirementGroupProps {
  requirement: VerdictRequirement;
  rows: VerdictRow[];
  density: DensityMode;
  testIds: string[];
  generatingIds: Set<string>;
  evaluatingIds: Set<string>;
  dataVersion: number;
  onViewRequirement?: (id: string) => void;
  onViewMetric?: (name: string, reqId?: string) => void;
}

export default function RequirementGroup({
  requirement,
  rows,
  density,
  testIds,
  generatingIds,
  evaluatingIds,
  dataVersion,
  onViewRequirement,
  onViewMetric,
}: RequirementGroupProps) {
  const theme = useTheme();
  const reducedMotion = useReducedMotion();
  const [expanded, setExpanded] = useState(true);

  const groupRows = useMemo(
    () => rows.filter(r => requirement.metric_keys.includes(r.metric_key)),
    [rows, requirement.metric_keys]
  );

  const agg = useMemo(
    () =>
      aggregateGroupByTest(groupRows, testIds, generatingIds, evaluatingIds),
    [groupRows, testIds, generatingIds, evaluatingIds]
  );

  const metricNames = useMemo(
    () => groupRows.map(r => r.metric_name),
    [groupRows]
  );
  const trimmedNames = useMemo(
    () => trimSharedPrefix(metricNames),
    [metricNames]
  );

  const passRateStr = useMemo(() => {
    const resolved = agg.passed + agg.failed;
    if (resolved === 0) return '--';
    return `${Math.round((agg.passed / resolved) * 100)}%`;
  }, [agg]);

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

  const stripHeight = density === 'numbers' ? 0 : ROLLUP_HEIGHT;

  return (
    <Box sx={{ mb: 0.5 }}>
      <Box
        role="button"
        tabIndex={0}
        onClick={() => setExpanded(prev => !prev)}
        onKeyDown={e => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            setExpanded(prev => !prev);
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

        <Box sx={{ overflow: 'hidden' }}>
          <VerdictStrip
            cells={agg.rollup}
            dataVersion={dataVersion}
            height={stripHeight}
            ariaLabel={stripAriaLabel}
          />
        </Box>
      </Box>

      <Collapse in={expanded} timeout="auto">
        {groupRows.map((row, idx) => (
          <MetricRow
            key={row.metric_key}
            row={row}
            density={density}
            testIds={testIds}
            generatingIds={generatingIds}
            evaluatingIds={evaluatingIds}
            trimmedName={trimmedNames[idx]}
            fullName={metricNames[idx]}
            dataVersion={dataVersion}
            onViewMetric={onViewMetric}
          />
        ))}
      </Collapse>
    </Box>
  );
}
