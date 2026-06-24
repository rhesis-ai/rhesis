'use client';

import React from 'react';
import Link from 'next/link';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Typography,
} from '@mui/material';
import { InsightsFilters } from '../types';
import { useBehaviorInsightsData } from '../hooks/useBehaviorInsightsData';
import InsightsSummaryBar from './InsightsSummaryBar';
import BehaviorColumn from './BehaviorColumn';

interface BehaviorInsightsViewProps {
  sessionToken: string;
  filters: InsightsFilters;
  endpointName?: string;
  endpointsLoading?: boolean;
  noEndpoints?: boolean;
}

export default function BehaviorInsightsView({
  sessionToken,
  filters,
  endpointName,
  endpointsLoading = false,
  noEndpoints = false,
}: BehaviorInsightsViewProps) {
  const { summary, columns, loading, error, noRuns } = useBehaviorInsightsData(
    sessionToken,
    filters
  );

  const showSkeleton = endpointsLoading || (loading && !summary);

  if (noEndpoints) {
    return (
      <Box sx={{ py: 6, textAlign: 'center' }}>
        <Typography variant="h6" gutterBottom>
          No endpoints in this project
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Create an endpoint to view behavior insights for your AI application.
        </Typography>
        <Button component={Link} href="/endpoints" variant="contained">
          Go to Endpoints
        </Button>
      </Box>
    );
  }

  if (!filters.endpointId && !endpointsLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <InsightsSummaryBar
        summary={summary}
        endpointName={endpointName}
        loading={showSkeleton}
      />

      {error && <Alert severity="error">{error}</Alert>}

      {noRuns && !loading && !error && (
        <Alert severity="info">
          No test runs found for this endpoint in the selected time range.
        </Alert>
      )}

      {showSkeleton && columns.length === 0 ? (
        <Box
          sx={{
            display: 'flex',
            gap: 2,
            overflowX: 'auto',
            pb: 1,
          }}
        >
          {[1, 2, 3].map(i => (
            <BehaviorColumn
              key={i}
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
      ) : columns.length > 0 ? (
        <Box
          sx={{
            display: 'flex',
            gap: 2,
            overflowX: 'auto',
            pb: 1,
            alignItems: 'stretch',
          }}
        >
          {columns.map(column => (
            <BehaviorColumn key={column.id} column={column} />
          ))}
        </Box>
      ) : (
        !loading &&
        !noRuns &&
        !error && (
          <Typography variant="body2" color="text.secondary" sx={{ py: 4 }}>
            No behavior data available for the selected filters.
          </Typography>
        )
      )}
    </Box>
  );
}
