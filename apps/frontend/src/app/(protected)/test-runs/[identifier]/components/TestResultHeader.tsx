'use client';

import React, { useMemo } from 'react';
import {
  Alert,
  AlertTitle,
  Box,
  Chip,
  Link,
  Typography,
  useTheme,
} from '@mui/material';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import StatusChip from '@/components/common/StatusChip';
import { getEffectiveTestResultStatus } from '@/utils/test-result-status';
import { getEndpointFailure } from '@/utils/endpoint-failure';
import { STATUS_LABEL } from '@/constants/outcomes';
import { buildResultChecks, checksSummary } from '@/utils/result-checks';
import { BORDER_RADIUS } from '@/styles/theme-constants';

/**
 * One line above the drawer's tabs: the verdict, tags and a link to the test. The test's
 * own text lives where it explains something: the simulated user opens the conversation,
 * goal and restrictions head the evaluation.
 */
export default function TestResultHeader({ test }: { test: TestResultDetail }) {
  const theme = useTheme();
  const checkGroups = useMemo(
    () =>
      buildResultChecks({
        metrics: test.test_metrics?.metrics,
        goalEvaluation: test.test_output?.goal_evaluation,
      }),
    [test]
  );
  const hasChecks = checkGroups.some(g => g.checks.length > 0);
  const status = getEffectiveTestResultStatus(test);
  const testId = test.test?.id ?? test.test_id;
  const endpointFailure = getEndpointFailure(test.test_output);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5, mb: 2 }}>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 1.5,
          px: 2,
          py: 1.25,
          borderRadius: BORDER_RADIUS.md,
          bgcolor: 'action.hover',
        }}
      >
        <StatusChip
          status={status}
          label={STATUS_LABEL[status]}
          size="small"
          variant="filled"
        />
        {hasChecks && (
          <Typography variant="body2" color="text.secondary">
            {checksSummary(checkGroups)}
          </Typography>
        )}
        <Box sx={{ flexGrow: 1 }} />
        {test.tags?.map(tag => (
          <Chip
            key={tag.id}
            label={tag.name}
            size="small"
            variant="outlined"
            sx={{ bgcolor: 'background.paper' }}
          />
        ))}
        {testId && (
          <Link
            href={`/tests/${testId}`}
            target="_blank"
            rel="noopener noreferrer"
            underline="hover"
            variant="body2"
            sx={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 0.5,
              fontWeight: 500,
            }}
          >
            Open test
            <OpenInNewIcon sx={{ fontSize: theme.spacing(2) }} />
          </Link>
        )}
      </Box>

      {endpointFailure && status === 'Error' && (
        // Explains an Error status the chip alone cannot: the target rejected or never
        // answered the call. Gated on the status, so an overridden result loses it.
        <Alert
          severity="warning"
          icon={<ErrorOutlineIcon />}
          sx={{ borderRadius: BORDER_RADIUS.md }}
        >
          <AlertTitle>
            {endpointFailure.statusCode !== undefined
              ? `Target endpoint returned HTTP ${endpointFailure.statusCode}`
              : 'Target endpoint did not return a response'}
            {endpointFailure.reason ? ` (${endpointFailure.reason})` : ''}
          </AlertTitle>
          The test could not be scored, because the endpoint never produced an
          answer to evaluate.
        </Alert>
      )}
    </Box>
  );
}
