'use client';

import React from 'react';
import { Box, IconButton } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { InsightsFilters } from '../types';
import {
  RequirementInsightColumn,
  isRequirementRowExpandable,
} from '../utils/requirement-insights-utils';
import RequirementColumn from './RequirementColumn';

const REQUIREMENT_GRID_COLUMNS = {
  xs: '1fr',
  md: '1fr 1fr 1fr',
} as const;

interface RequirementInsightsRowProps {
  row: RequirementInsightColumn[];
  rowIndex: number;
  expanded: boolean;
  onToggle: () => void;
  insightsFilters: InsightsFilters;
}

export default function RequirementInsightsRow({
  row,
  rowIndex,
  expanded,
  onToggle,
  insightsFilters,
}: RequirementInsightsRowProps) {
  const canExpand = isRequirementRowExpandable(row);

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
          gridTemplateColumns: REQUIREMENT_GRID_COLUMNS,
          gap: 1.25,
          alignItems: 'stretch',
        }}
        data-insights-row={rowIndex}
      >
        {row.map(column => (
          <RequirementColumn
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
