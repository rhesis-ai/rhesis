'use client';

import React from 'react';
import { Box, IconButton } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { InsightsFilters } from '../types';
import {
  BehaviorInsightColumn,
  isBehaviorRowExpandable,
} from '../utils/behavior-insights-utils';
import BehaviorColumn from './BehaviorColumn';

const BEHAVIOR_GRID_COLUMNS = {
  xs: '1fr',
  md: '1fr 1fr 1fr',
} as const;

interface BehaviorInsightsRowProps {
  row: BehaviorInsightColumn[];
  rowIndex: number;
  expanded: boolean;
  onToggle: () => void;
  insightsFilters: InsightsFilters;
}

export default function BehaviorInsightsRow({
  row,
  rowIndex,
  expanded,
  onToggle,
  insightsFilters,
}: BehaviorInsightsRowProps) {
  const canExpand = isBehaviorRowExpandable(row);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
      {canExpand && (
        <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
          <IconButton
            size="small"
            aria-label={expanded ? 'Collapse row' : 'Expand row'}
            aria-expanded={expanded}
            onClick={onToggle}
            sx={{ color: 'text.secondary' }}
          >
            <ExpandMoreIcon
              sx={{
                transition: 'transform 0.2s ease',
                transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
              }}
            />
          </IconButton>
        </Box>
      )}

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: BEHAVIOR_GRID_COLUMNS,
          gap: 1.25,
          alignItems: 'stretch',
        }}
        data-insights-row={rowIndex}
      >
        {row.map(column => (
          <BehaviorColumn
            key={column.id}
            column={column}
            insightsFilters={insightsFilters}
            expanded={expanded}
          />
        ))}
      </Box>
    </Box>
  );
}
