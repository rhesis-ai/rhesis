'use client';

import React from 'react';
import { Alert, Box, CircularProgress, Typography } from '@mui/material';
import { InsightsFilters } from '../types';
import { BehaviorInsightsData } from '../hooks/useBehaviorInsightsData';
import { BehaviorInsightColumn } from '../utils/behavior-insights-utils';
import InsightsSummaryBar from './InsightsSummaryBar';
import BehaviorColumn from './BehaviorColumn';
import BehaviorInsightsRow from './BehaviorInsightsRow';

interface BehaviorInsightsViewProps {
  filters: InsightsFilters;
  insights: Pick<
    BehaviorInsightsData,
    | 'summary'
    | 'columns'
    | 'loading'
    | 'error'
    | 'noRuns'
    | 'failedTestCaseCount'
  >;
  searchQuery?: string;
  endpointName?: string;
  endpointsLoading?: boolean;
  columnRows: BehaviorInsightColumn[][];
  expandedRows: Set<number>;
  onRowToggle: (rowIndex: number) => void;
}

const BEHAVIOR_GRID_COLUMNS = {
  xs: '1fr',
  md: '1fr 1fr 1fr',
} as const;

export default function BehaviorInsightsView({
  filters,
  insights,
  searchQuery = '',
  endpointName,
  endpointsLoading = false,
  columnRows,
  expandedRows,
  onRowToggle,
}: BehaviorInsightsViewProps) {
  const { summary, loading, error } = insights;

  const isLoading = endpointsLoading || loading;
  const hasVisibleColumns = columnRows.some(row => row.length > 0);

  if (!filters.endpointId) {
    if (endpointsLoading) {
      return (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
          <CircularProgress />
        </Box>
      );
    }

    return (
      <Box sx={{ py: 6, textAlign: 'center' }}>
        <Typography variant="body2" color="text.secondary">
          Select an endpoint in Filters to view behavior insights.
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <InsightsSummaryBar
        summary={summary}
        endpointName={endpointName}
        loading={isLoading}
        failedTestCaseCount={insights.failedTestCaseCount}
      />

      {error && <Alert severity="error">{error}</Alert>}

      {isLoading ? (
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: BEHAVIOR_GRID_COLUMNS,
            gap: 1.25,
            alignItems: 'stretch',
          }}
        >
          {[1, 2, 3, 4, 5, 6].map(i => (
            <BehaviorColumn
              key={i}
              insightsFilters={filters}
              column={{
                id: String(i),
                name: '',
                overall: { total: 0, passed: 0, failed: 0, pass_rate: 0 },
                metrics: [],
                topics: [],
              }}
              loading
            />
          ))}
        </Box>
      ) : hasVisibleColumns ? (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          {columnRows.map((row, rowIndex) => (
            <BehaviorInsightsRow
              key={row.map(column => column.id).join('-') || rowIndex}
              row={row}
              rowIndex={rowIndex}
              expanded={expandedRows.has(rowIndex)}
              onToggle={() => onRowToggle(rowIndex)}
              insightsFilters={filters}
            />
          ))}
        </Box>
      ) : (
        !isLoading &&
        !error && (
          <Typography variant="body2" color="text.secondary" sx={{ py: 4 }}>
            {searchQuery.trim()
              ? 'No behaviors match your search.'
              : 'No behavior data available for the selected filters.'}
          </Typography>
        )
      )}
    </Box>
  );
}
