'use client';

import React from 'react';
import { Box, Typography, CircularProgress, Alert } from '@mui/material';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import TestExecutionHistoryTable from '@/components/tests/TestExecutionHistoryTable';
import { useTestExecutionHistory } from '@/components/tests/useTestExecutionHistory';

interface TestDetailHistoryTabProps {
  test: TestResultDetail;
  testRunId: string;
  sessionToken: string;
}

export default function TestDetailHistoryTab({
  test,
  testRunId,
  sessionToken,
}: TestDetailHistoryTabProps) {
  const { rows, loading, error } = useTestExecutionHistory({
    testId: test.test_id,
    sessionToken,
  });

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
        <Box sx={{ display: 'flex', gap: '26px', mb: 3 }}>
          {[
            {
              label: 'Total Executions',
              value: rows.length,
              color: '#1a1c20',
            },
            {
              label: 'Pass Rate',
              value: `${((rows.filter(h => h.passed).length / rows.length) * 100).toFixed(1)}%`,
              color:
                rows.filter(h => h.passed).length / rows.length >= 0.8
                  ? '#38ad87'
                  : '#de3355',
            },
            {
              label: 'Passed',
              value: rows.filter(h => h.passed).length,
              color: '#38ad87',
            },
            {
              label: 'Failed',
              value: rows.filter(h => !h.passed).length,
              color: '#de3355',
            },
          ].map(stat => (
            <Box
              key={stat.label}
              sx={{
                flex: 1,
                bgcolor: '#f3f4f6',
                borderRadius: '10px',
                boxShadow: '0px 3px 5px rgba(0,0,0,0.09)',
                p: '30px',
                height: '140px',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
              }}
            >
              <Typography
                sx={{
                  fontSize: 12,
                  lineHeight: '18px',
                  color: '#1a1c20',
                }}
              >
                {stat.label}
              </Typography>
              <Typography
                sx={{
                  fontSize: 36,
                  fontWeight: 700,
                  lineHeight: 1,
                  color: stat.color,
                }}
              >
                {stat.value}
              </Typography>
            </Box>
          ))}
        </Box>
      )}

      {rows.length === 0 ? (
        <Box
          sx={{
            bgcolor: 'background.paper',
            borderRadius: '12px',
            border: '1px solid #cdd2da',
            boxShadow: '0px 2px 4px rgba(84,90,101,0.25)',
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
          testId={test.test_id}
          highlightTestRunId={testRunId}
        />
      )}
    </Box>
  );
}
