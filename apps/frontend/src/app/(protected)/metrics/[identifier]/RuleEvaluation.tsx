'use client';

import React from 'react';
import { Typography } from '@mui/material';
import EditableSectionCard from '@/components/common/EditableSection';
import { useNotifications } from '@/components/common/NotificationContext';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type {
  MetricDetail,
  MetricTargetChoice,
} from '@/utils/api-client/interfaces/metric';
import {
  describeRule,
  ruleConfig,
  ruleDraftError,
  ruleDraftFromConfig,
  type RuleDraft,
} from '@/utils/metric-rules';
import { getMetricTarget } from '@/utils/metric-targets';
import RuleFields, { RuleSummary } from '../components/RuleFields';
import InfoRow from './MetricInfoRow';

/**
 * The Evaluation Process card for a rule: what it checks, in place of a prompt,
 * steps and judge model it doesn't have. Its target has its own card.
 */
export default function RuleEvaluation({
  metric,
  editable,
  spanKinds,
  onSaved,
}: {
  metric: MetricDetail;
  editable: boolean;
  spanKinds: MetricTargetChoice[];
  onSaved: (metric: MetricDetail) => void;
}) {
  const notifications = useNotifications();
  const stored = React.useMemo(
    () => ruleDraftFromConfig(metric.class_name, metric.config),
    [metric.class_name, metric.config]
  );

  const handleSave = React.useCallback(
    async (draft: RuleDraft) => {
      const error = ruleDraftError(draft);
      if (error) {
        notifications.show(error, { severity: 'error' });
        return false;
      }
      const target = getMetricTarget(metric);
      const metricsClient = new ApiClientFactory().getMetricsClient();
      try {
        // A PUT replaces the whole config, so the target goes back with the rule.
        await metricsClient.updateMetric(metric.id, {
          evaluation_prompt: describeRule(draft),
          config: { ...ruleConfig(draft), ...(target && { target }) },
        });
        const updated = await metricsClient.getMetric(metric.id);
        onSaved(updated as MetricDetail);
        notifications.show('Rule updated', {
          severity: 'success',
          autoHideDuration: 4000,
        });
        return true;
      } catch (error) {
        notifications.show(
          error instanceof Error ? error.message : 'Failed to update rule',
          { severity: 'error' }
        );
        return false;
      }
    },
    [metric, notifications, onSaved]
  );

  return (
    <EditableSectionCard
      editable={editable}
      title="Evaluation Process"
      subtitle="A rule: no model, it passes or fails, and is not applicable when the trace doesn't have the value"
      initialValue={stored}
      onSave={handleSave}
    >
      {({ draft, setDraft, isEditing }) =>
        isEditing ? (
          <RuleFields
            draft={draft}
            onChange={setDraft}
            spanKinds={spanKinds}
            showErrors
          />
        ) : (
          <>
            <InfoRow label="Passes when">
              <RuleSummary draft={stored} />
            </InfoRow>
            {metric.class_name && (
              <InfoRow label="Implementation">
                <Typography
                  sx={theme => ({
                    fontFamily: theme.typography.fontFamilyCode,
                  })}
                >
                  {metric.class_name}
                </Typography>
              </InfoRow>
            )}
          </>
        )
      }
    </EditableSectionCard>
  );
}
