'use client';

import * as React from 'react';
import NextLink from 'next/link';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Link from '@mui/material/Link';
import Skeleton from '@mui/material/Skeleton';
import Typography from '@mui/material/Typography';
import type { UUID } from 'crypto';
import EditableSectionCard from '@/components/common/EditableSection';
import { useNotifications } from '@/components/common/NotificationContext';
import { useMetricTargetOptions } from '@/hooks/useLookups';
import { tracesHrefForTarget } from '@/app/(protected)/traces/components/target-filters';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type {
  MetricDetail,
  MetricTargetChoice,
} from '@/utils/api-client/interfaces/metric';
import { getApiErrorMessage } from '@/utils/error-utils';
import {
  draftFromTarget,
  draftProblem,
  targetFromDraft,
  targetKey,
  type TargetDraft,
} from '@/utils/metric-target-draft';
import {
  formatMetricTarget,
  getMetricTarget,
  getMetricTargetIcon,
  METRIC_TARGET,
  offeredTargetsWithCustom,
} from '@/utils/metric-targets';
import MetricTargetBuilder from './MetricTargetBuilder';
import TargetSummaryText from './TargetSummaryText';

const NO_TARGETS: MetricTargetChoice[] = [];

interface MetricTargetSectionProps {
  metric: MetricDetail;
  /** The caller may update the metric. */
  editable: boolean;
  /** Called with the metric as stored after a save. */
  onSaved: (metric: MetricDetail) => void;
}

/** "Target updated." plus what the save noticed, such as an unknown attribute key. */
export function savedTargetMessage(warnings: string[] | undefined): string {
  return warnings?.length
    ? `Target updated. ${warnings.join(' ')}`
    : 'Target updated';
}

/**
 * The metric's Target section: what it judges, in the API's words, linked to
 * the spans it picks; in edit mode, the target builder. The target says where
 * a metric is applied, not what it is, so it stays editable on framework
 * metrics; the update sends only the config.
 */
export default function MetricTargetSection({
  metric,
  editable,
  onSaved,
}: MetricTargetSectionProps) {
  const notifications = useNotifications();
  const { data: options, isPending } = useMetricTargetOptions();
  const allTargets = options?.targets ?? NO_TARGETS;
  const specialFields = options?.special_fields;
  const operators = options?.operators;
  const choices = React.useMemo(
    () =>
      offeredTargetsWithCustom(allTargets, {
        supported: metric.supported_targets,
      }),
    [allTargets, metric.supported_targets]
  );
  const stored = getMetricTarget(metric);
  const storedKey = targetKey(stored);
  // Keyed on what the target means, so the draft's row ids stay put between renders.
  const initialDraft = React.useMemo(
    () =>
      draftFromTarget(
        stored,
        choices[0]?.on ?? METRIC_TARGET.TURN,
        specialFields
      ),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- storedKey stands for stored
    [storedKey, choices, specialFields]
  );
  const [warnings, setWarnings] = React.useState<string[]>([]);
  const [showErrors, setShowErrors] = React.useState(false);

  const handleSave = React.useCallback(
    async (draft: TargetDraft) => {
      const problem = draftProblem(draft, allTargets, operators ?? []);
      if (problem) {
        setShowErrors(true);
        notifications.show(problem, { severity: 'error' });
        return false;
      }
      const metricsClient = new ApiClientFactory().getMetricsClient();
      try {
        // A PUT replaces the whole config, so the class settings go back too.
        const saved = await metricsClient.updateMetric(metric.id as UUID, {
          config: {
            ...(metric.config ?? {}),
            target: targetFromDraft(draft, allTargets, operators ?? []),
          },
        });
        const updated = await metricsClient.getMetric(metric.id as UUID);
        setWarnings(saved?.warnings ?? []);
        setShowErrors(false);
        onSaved(updated);
        notifications.show(savedTargetMessage(saved?.warnings), {
          severity: saved?.warnings?.length ? 'warning' : 'success',
          autoHideDuration: 4000,
        });
        return true;
      } catch (error) {
        notifications.show(
          getApiErrorMessage(error, 'Failed to update target'),
          { severity: 'error' }
        );
        return false;
      }
    },
    [allTargets, operators, metric, notifications, onSaved]
  );

  const handleEditingChange = React.useCallback((editing: boolean) => {
    if (!editing) setShowErrors(false);
  }, []);

  const view = () => {
    if (stored && isPending) {
      // The label comes with the targets; the raw value would flash first.
      return (
        <Skeleton
          variant="rounded"
          sx={{ width: theme => theme.spacing(15) }}
          aria-label="Loading target"
        />
      );
    }
    if (!stored) {
      return (
        <Typography variant="body1" color="text.secondary">
          No target set
        </Typography>
      );
    }
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
        <Box
          sx={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 1.5,
            alignItems: 'center',
          }}
        >
          <Chip
            icon={getMetricTargetIcon(
              stored.on,
              allTargets,
              'small',
              stored.where
            )}
            label={formatMetricTarget(stored, [...allTargets, ...choices])}
            color="primary"
            size="small"
          />
          <Link
            component={NextLink}
            href={tracesHrefForTarget(stored, metric.id)}
            underline="hover"
            variant="body2"
          >
            Show the spans it judges
          </Link>
        </Box>
        {metric.target_summary && (
          <Typography variant="body1" data-testid="metric-target-summary">
            Judges <TargetSummaryText summary={metric.target_summary} />.
          </Typography>
        )}
        {warnings.length > 0 && (
          <Alert severity="warning" onClose={() => setWarnings([])}>
            {warnings.join(' ')}
          </Alert>
        )}
      </Box>
    );
  };

  return (
    <EditableSectionCard
      editable={editable && choices.length > 0}
      title="Target"
      subtitle="The part of the trace this metric looks at"
      initialValue={initialDraft}
      onSave={handleSave}
      onEditingChange={handleEditingChange}
      isDirty={(draft, initial) =>
        targetKey(targetFromDraft(draft, allTargets, operators ?? [])) !==
          targetKey(targetFromDraft(initial, allTargets, operators ?? [])) ||
        draftProblem(draft, allTargets, operators ?? []) !== null
      }
    >
      {({ draft, setDraft, isEditing }) =>
        isEditing ? (
          <MetricTargetBuilder
            choices={choices}
            value={draft}
            onChange={setDraft}
            savedTarget={stored}
            savedSummary={metric.target_summary}
            showErrors={showErrors}
          />
        ) : (
          view()
        )
      }
    </EditableSectionCard>
  );
}
