'use client';

import React from 'react';
import { Alert, AlertTitle, Box } from '@mui/material';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import { getEffectiveTestResultStatus } from '@/utils/test-result-status';
import { getEndpointFailure } from '@/utils/endpoint-failure';
import { BORDER_RADIUS } from '@/styles/theme-constants';

/**
 * Above the drawer's tabs, only when the endpoint never answered: it explains an Error
 * status the tabs alone cannot. The verdict lives in the conversation and evaluation,
 * the link to the test beside the drawer's Close button.
 */
export default function TestResultHeader({ test }: { test: TestResultDetail }) {
  const status = getEffectiveTestResultStatus(test);
  const endpointFailure = getEndpointFailure(test.test_output);

  // Gated on the status, so an overridden result loses it.
  if (!endpointFailure || status !== 'Error') return null;

  return (
    <Box sx={{ mb: 2 }}>
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
    </Box>
  );
}
