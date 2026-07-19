'use client';

import React, { useCallback, useState } from 'react';
import { Fab } from '@/components/common/Fab';
import { Can } from '@/components/common/Can';
import { useNotifications } from '@/components/common/NotificationContext';
import { Capability } from '@/constants/capabilities';
import { EngineeringIcon } from '@/components/icons';
import { createAndOpenArchitectSession } from '@/utils/architect-handoff';
import { InsightsFilters } from '../types';
import { resolveInsightsQueryTestRunIds } from '../utils/behavior-insights-utils';
import {
  buildInsightsSummarizePrompt,
  buildInsightsSummarizeSessionTitle,
  capArchitectInsightsTestRunIds,
} from '../utils/insights-summarize-prompt';

interface InsightsSummarizeFabProps {
  sessionToken: string;
  filters: InsightsFilters;
  endpointName?: string;
  /** Behavior names currently visible (multi-select ∩ search). */
  visibleBehaviorNames: string[];
  loading?: boolean;
  disabled?: boolean;
}

export default function InsightsSummarizeFab({
  sessionToken,
  filters,
  endpointName = '',
  visibleBehaviorNames,
  loading = false,
  disabled = false,
}: InsightsSummarizeFabProps) {
  const [creating, setCreating] = useState(false);
  const { show: showNotification } = useNotifications();

  // Enabled regardless of failedCount (including 0)
  const isDisabled =
    disabled || loading || creating || !filters.endpointId || !sessionToken;

  const handleClick = useCallback(async () => {
    if (isDisabled) return;
    setCreating(true);
    try {
      const resolvedIds = await resolveInsightsQueryTestRunIds(
        sessionToken,
        filters
      );
      const { ids, truncated, totalMatched } =
        capArchitectInsightsTestRunIds(resolvedIds);
      const title = buildInsightsSummarizeSessionTitle({
        endpointName,
        filters,
      });
      const initialMessage = buildInsightsSummarizePrompt({
        endpointName,
        filters,
        visibleBehaviorNames,
        testRunIds: ids,
        truncated,
        totalMatched,
      });
      await createAndOpenArchitectSession({
        sessionToken,
        title,
        initialMessage,
      });
    } catch (error) {
      console.error('Failed to open Insights summary in Architect:', error);
      showNotification('Could not open Architect summary. Please try again.', {
        severity: 'error',
      });
    } finally {
      setCreating(false);
    }
  }, [
    endpointName,
    filters,
    isDisabled,
    sessionToken,
    showNotification,
    visibleBehaviorNames,
  ]);

  return (
    <Can capability={Capability.Architect.CREATE}>
      <Fab
        icon={<EngineeringIcon />}
        tooltip="Summarize insights"
        aria-label="Summarize insights"
        onClick={handleClick}
        disabled={isDisabled}
        loading={creating}
      />
    </Can>
  );
}
