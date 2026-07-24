'use client';

import React, { useCallback, useState } from 'react';
import { Fab } from '@/components/common/Fab';
import { Can } from '@/components/common/Can';
import { useNotifications } from '@/components/common/NotificationContext';
import { Capability } from '@/constants/capabilities';
import { EngineeringIcon } from '@/components/icons';
import { createAndOpenArchitectSession } from '@/utils/architect-handoff';
import type { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import {
  buildTestRunSummarizePrompt,
  buildTestRunSummarizeSessionTitle,
} from '../utils/test-run-summarize-prompt';

interface TestRunSummarizeFabProps {
  testRun: TestRunDetail;
}

export default function TestRunSummarizeFab({
  testRun,
}: TestRunSummarizeFabProps) {
  const [creating, setCreating] = useState(false);
  const { show: showNotification } = useNotifications();

  const isDisabled = creating || !testRun.id;

  const handleClick = useCallback(async () => {
    if (isDisabled) return;
    setCreating(true);
    try {
      const testRunName = testRun.name || 'Test Run';
      const endpointName = testRun.test_configuration?.endpoint?.name;
      const testSetName = testRun.test_configuration?.test_set?.name;
      const title = buildTestRunSummarizeSessionTitle({ testRunName });
      const initialMessage = buildTestRunSummarizePrompt({
        testRunId: String(testRun.id),
        testRunName,
        endpointName,
        testSetName,
      });
      await createAndOpenArchitectSession({
        title,
        initialMessage,
      });
    } catch (error) {
      console.error('Failed to open test run summary in Architect:', error);
      showNotification('Could not open Architect summary. Please try again.', {
        severity: 'error',
      });
    } finally {
      setCreating(false);
    }
  }, [isDisabled, showNotification, testRun]);

  return (
    <Can capability={Capability.Architect.CREATE}>
      <Fab
        icon={<EngineeringIcon />}
        tooltip="Summarize test run"
        aria-label="Summarize test run"
        onClick={handleClick}
        disabled={isDisabled}
        loading={creating}
      />
    </Can>
  );
}
