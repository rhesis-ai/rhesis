'use client';

import React, { useMemo } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  CircularProgress,
  Alert,
} from '@mui/material';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import TestExecutionHistoryTable from '@/components/tests/TestExecutionHistoryTable';
import { useTestExecutionHistory } from '@/components/tests/useTestExecutionHistory';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme-constants';

interface TestDetailHistoryTabProps {
  test: TestResultDetail;
  testRunId: string;
  sessionToken: string;
}

type StatColor = 'primary' | 'success' | 'error';

export default function TestDetailHistoryTab({
  test,
  testRunId,
  sessionToken,
}: TestDetailHistoryTabProps) {
  const { rows, loading, error } = useTestExecutionHistory({
    testId: test.test_id,
    sessionToken,
  });

  const stats = useMemo(() => {
    const passedCount = rows.filter(h => h.passed).length;
    const passRate =
      rows.length > 0 ? (passedCount / rows.length) * 100 : 0;

    return [
      {
        label: 'Total Executions',
        value: rows.length,
        color: 'primary' as StatColor,
      },
      {
        label: 'Pass Rate',
        value: `${passRate.toFixed(1)}%`,
        color: (passRate >= 80 ? 'success' : 'error') as StatColor,
      },
      {
        label: 'Passed',
        value: passedCount,
        color: 'success' as StatColor,
      },
      {
        label: 'Failed',
        value: rows.filter(h => !h.passed).length,
        color: 'error' as StatColor,
      },
    ];
  }, [rows]);

  if (loading) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          p: 4,
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">{error}</Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      {rows.length > 0 && (
        <Box sx={{ display: 'flex', gap: 3, mb: 3 }}>
          {stats.map(stat => (
            <Card
              key={stat.label}
              sx={{
                flex: 1,
                bgcolor: 'grey.100',
                borderRadius: BORDER_RADIUS.sm,
                boxShadow: ELEVATION.xs,
              }}
            >
              <CardContent
                sx={{
                  p: 3,
                  height: 140,
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  '&:last-child': { pb: 3 },
                }}
              >
                <Typography variant="caption" color="text.primary">
                  {stat.label}
                </Typography>
                <Typography
                  variant="h3"
                  sx={{
                    fontWeight: 700,
                    color:
                      stat.color === 'success'
                        ? 'success.main'
                        : stat.color === 'error'
                          ? 'error.main'
                          : 'text.primary',
                  }}
                >
                  {stat.value}
                </Typography>
              </CardContent>
            </Card>
          ))}
        </Box>
      )}

      {rows.length === 0 ? (
        <Box
          sx={{
            bgcolor: 'background.paper',
            borderRadius: BORDER_RADIUS.md,
            border: 1,
            borderColor: 'divider',
            boxShadow: ELEVATION.xs,
            p: 3,
            textAlign: 'center',
          }}
        >
          <Typography variant="body2" color="text.secondary">
            No historical data available for this test
          </Typography>
        </Box>
      ) : (
        <TestExecutionHistoryTable
          rows={rows}
          highlightTestRunId={testRunId}
        />
      )}
    </Box>
  );
}
