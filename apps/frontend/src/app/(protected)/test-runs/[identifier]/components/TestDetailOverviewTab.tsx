'use client';

import React, { useMemo } from 'react';
import { Box, Typography, Paper, Chip, useTheme } from '@mui/material';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import TestResultTags from './TestResultTags';
import StatusChip from '@/components/common/StatusChip';
import {
  getTestResultStatus,
  getTestResultLabel,
} from '@/utils/testResultStatus';

interface TestDetailOverviewTabProps {
  test: TestResultDetail;
  prompts: Record<string, { content: string; name?: string }>;
  sessionToken: string;
  onTestResultUpdate: (updatedTest: TestResultDetail) => void;
}

export default function TestDetailOverviewTab({
  test,
  prompts,
  sessionToken,
  onTestResultUpdate,
}: TestDetailOverviewTabProps) {
  const theme = useTheme();

  const promptContent =
    test.prompt_id && prompts[test.prompt_id]
      ? prompts[test.prompt_id].content
      : 'No prompt available';

  const responseContent = test.test_output?.output || 'No response available';

  // Get the test result status (Pass, Fail, or Error)
  const testStatus = useMemo(() => getTestResultStatus(test), [test]);
  const testLabel = useMemo(() => getTestResultLabel(test), [test]);

  return (
    <Box sx={{ p: 3 }}>
      {/* Overall Status */}
      <Box sx={{ mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
          <Typography variant="h6" fontWeight={600}>
            Test Result
          </Typography>
          <StatusChip
            status={testStatus}
            label={testLabel}
            size="medium"
            variant="filled"
            sx={{ fontWeight: 600 }}
          />
        </Box>
      </Box>

      {/* Prompt Section */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="subtitle2" fontWeight={600} gutterBottom>
          Prompt
        </Typography>
        <Paper
          variant="outlined"
          sx={{
            p: 2,
            backgroundColor: theme.palette.background.default,
            maxHeight: 200,
            overflow: 'auto',
          }}
        >
          <Typography
            variant="body2"
            sx={{
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              fontFamily: 'monospace',
            }}
          >
            {promptContent}
          </Typography>
        </Paper>
      </Box>

      {/* Response Section */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="subtitle2" fontWeight={600} gutterBottom>
          Response
        </Typography>
        <Paper
          variant="outlined"
          sx={{
            p: 2,
            backgroundColor: theme.palette.background.default,
            maxHeight: 200,
            overflow: 'auto',
          }}
        >
          <Typography
            variant="body2"
            sx={{
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              fontFamily: 'monospace',
            }}
          >
            {responseContent}
          </Typography>
        </Paper>
      </Box>

      {/* Tags Section */}
      <Box sx={{ mb: 3 }}>
        <TestResultTags
          sessionToken={sessionToken}
          testResult={test}
          onUpdate={onTestResultUpdate}
        />
      </Box>
    </Box>
  );
}
