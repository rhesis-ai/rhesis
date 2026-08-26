'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Box, Paper, Typography, useTheme } from '@mui/material';
import RequirementGroup from './RequirementGroup';
import DensityControl from './DensityControl';
import {
  COLUMN_TEMPLATES,
  GEOMETRY,
  GRID_GAP,
  GRID_PADDING_X,
  LAST_COLUMN_LABEL,
  gridMorphTransition,
  type DensityMode,
} from './summary-tokens';
import { useReducedMotion } from '@/hooks/useReducedMotion';
import { useRunClock } from './RunClockProvider';
import type { VerdictMatrix } from '@/utils/api-client/interfaces/test-run';

interface RequirementTableProps {
  matrix: VerdictMatrix;
  density: DensityMode;
  onDensityChange: (d: DensityMode) => void;
  hideDensityControl?: boolean;
  generatingIds: Set<string>;
  evaluatingIds: Set<string>;
  onViewRequirement?: (id: string) => void;
  onViewMetric?: (name: string, reqId?: string) => void;
}

const MODE_ANNOUNCEMENT: Record<DensityMode, string> = {
  numbers: 'Numbers view. Showing exact figures, no strip.',
  shape:
    'Numbers and shape view. Showing counts and a compact distribution strip.',
  detail: 'Detail view. Showing every test per metric.',
};

export default function RequirementTable({
  matrix,
  density,
  onDensityChange,
  hideDensityControl = false,
  generatingIds,
  evaluatingIds,
  onViewRequirement,
  onViewMetric,
}: RequirementTableProps) {
  const theme = useTheme();
  const reducedMotion = useReducedMotion();
  const clock = useRunClock();
  const [announcement, setAnnouncement] = useState('');

  const testIds = useMemo(
    () => (matrix.test_ids ?? []).map(String),
    [matrix.test_ids]
  );

  const settleTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    return () => {
      if (settleTimeoutRef.current) clearTimeout(settleTimeoutRef.current);
    };
  }, []);

  const handleDensityChange = (next: DensityMode) => {
    onDensityChange(next);
    setAnnouncement(MODE_ANNOUNCEMENT[next]);
    // Repaint immediately, then once more after the transition settles --
    // a cheap safety net on top of the resize-driven repaints each
    // VerdictStrip already does on its own via ResizeObserver.
    clock.poke();
    if (settleTimeoutRef.current) clearTimeout(settleTimeoutRef.current);
    settleTimeoutRef.current = setTimeout(() => clock.poke(), 460);
  };

  const gridSx = {
    display: 'grid',
    gridTemplateColumns: COLUMN_TEMPLATES[density],
    transition: gridMorphTransition(theme, reducedMotion),
    columnGap: `${GRID_GAP}px`,
    px: `${GRID_PADDING_X}px`,
    alignItems: 'center',
    '@media print': {
      gridTemplateColumns: COLUMN_TEMPLATES.numbers,
    },
  } as const;

  return (
    <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden' }}>
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: 2,
          py: 1.5,
          borderBottom: 1,
          borderColor: 'divider',
        }}
      >
        <Typography
          variant="subtitle1"
          fontWeight={600}
          sx={{ color: theme.palette.greyscale.title }}
        >
          Verdict Grid
        </Typography>
        {!hideDensityControl && (
          <DensityControl density={density} onChange={handleDensityChange} />
        )}
      </Box>

      {/* aria-live region: screen readers get no benefit from the visual
          morph, so the mode change is announced explicitly. */}
      <Box
        aria-live="polite"
        sx={{
          position: 'absolute',
          width: 1,
          height: 1,
          overflow: 'hidden',
          clip: 'rect(0 0 0 0)',
        }}
      >
        {announcement}
      </Box>

      {/* Column headers */}
      <Box>
        <Box
          sx={{
            ...gridSx,
            py: 0.75,
            minHeight: GEOMETRY.rowHeight,
            borderBottom: 1,
            borderColor: 'divider',
          }}
        >
          <Typography
            variant="caption"
            color="text.secondary"
            fontWeight={600}
            noWrap
            sx={{ overflow: 'hidden' }}
          >
            Metric
          </Typography>
          <Typography
            variant="caption"
            color="text.secondary"
            fontWeight={600}
            noWrap
            sx={{ textAlign: 'right', overflow: 'hidden' }}
          >
            Total
          </Typography>
          <Typography
            variant="caption"
            color="text.secondary"
            fontWeight={600}
            noWrap
            sx={{ textAlign: 'right', overflow: 'hidden' }}
          >
            Passed
          </Typography>
          <Typography
            variant="caption"
            color="text.secondary"
            fontWeight={600}
            noWrap
            sx={{ textAlign: 'right', overflow: 'hidden' }}
          >
            Failed
          </Typography>
          <Typography
            variant="caption"
            color="text.secondary"
            fontWeight={600}
            noWrap
            sx={{ textAlign: 'right', overflow: 'hidden' }}
          >
            Pass rate
          </Typography>
          <Typography
            variant="caption"
            color="text.secondary"
            fontWeight={600}
            noWrap
            sx={{ overflow: 'hidden' }}
          >
            {/* A non-breaking space keeps this cell's line box the same
                  height as every other header cell when the label is empty
                  (Numbers mode) -- an empty inline element can collapse to
                  zero height in some browsers once overflow:hidden applies,
                  which only this cell is exposed to since every other
                  header label always has real text. */}
            {LAST_COLUMN_LABEL[density] || ' '}
          </Typography>
        </Box>

        {/* Requirement groups */}
        {matrix.requirements.map(req => (
          <RequirementGroup
            key={req.id ?? req.name}
            requirement={req}
            rows={matrix.rows}
            density={density}
            testIds={testIds}
            generatingIds={generatingIds}
            evaluatingIds={evaluatingIds}
            dataVersion={matrix.version}
            onViewRequirement={onViewRequirement}
            onViewMetric={onViewMetric}
          />
        ))}

        {matrix.requirements.length === 0 && (
          <Box sx={{ py: 4, textAlign: 'center' }}>
            <Typography color="text.secondary">
              No verdict data available.
            </Typography>
          </Box>
        )}
      </Box>

      {/* Legend */}
      <VerdictLegend />
    </Paper>
  );
}

function VerdictLegend() {
  const theme = useTheme();

  const items: { label: string; color: string; outlined?: boolean }[] = [
    { label: 'Passed', color: theme.palette.success.main },
    { label: 'Failed', color: theme.palette.error.main },
    { label: 'Pending', color: theme.palette.greyscale.surface2 },
    { label: 'Scored', color: theme.palette.warning.main },
    { label: 'Error', color: theme.palette.error.main, outlined: true },
    { label: 'N/A', color: theme.palette.greyscale.border },
  ];

  return (
    <Box
      sx={{
        display: 'flex',
        gap: 2,
        flexWrap: 'wrap',
        px: 2,
        py: 1,
        borderTop: 1,
        borderColor: 'divider',
      }}
    >
      {items.map(item => (
        <Box
          key={item.label}
          sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}
        >
          <Box
            sx={{
              width: 10,
              height: 10,
              borderRadius: 0.5,
              ...(item.outlined
                ? {
                    bgcolor: 'transparent',
                    border: 1,
                    borderColor: item.color,
                  }
                : { bgcolor: item.color }),
            }}
          />
          <Typography variant="caption" color="text.secondary">
            {item.label}
          </Typography>
        </Box>
      ))}
    </Box>
  );
}
