import React from 'react';
import EntityCard, {
  skeletonCardKeys,
  type EntityCardFact,
  type EntityCardRelation,
} from '@/components/common/EntityCard';
import { RequirementsIcon, TuneIcon } from '@/components/icons';
import { METRIC_TYPES, METRIC_TYPE_LABELS } from '@/constants/metric-types';
import type {
  MetricTarget,
  MetricTargetChoice,
} from '@/utils/api-client/interfaces/metric';
import MetricTargetLine from './MetricTargetLine';

interface MetricCardProps {
  type?: 'custom-prompt' | 'api-call' | 'custom-code' | 'grading';
  title: string;
  description: string;
  backend?: string;
  metricType?: string;
  scoreType?: string;
  /** What the metric judges, linked to its spans. */
  target?: MetricTarget;
  /** The metric's `target_summary_short`, shown under its name; no line without it. */
  targetSummary?: string | null;
  /** The metric's `target_summary`, for the tooltip. */
  targetSummaryFull?: string | null;
  /** `GET /metrics/targets`, for the target's icon. */
  targetChoices?: MetricTargetChoice[];
  metricId?: string;
  usedIn?: string[];
  /** Custom metrics only; omitted for metrics that can't be tuned. */
  tuningCases?: number;
  showUsage?: boolean;
  onDelete?: () => void;
  onClick?: () => void;
}

const capitalize = (value: string) =>
  value.charAt(0).toUpperCase() + value.slice(1).toLowerCase();

/** Requirement icon + count, like the requirement card's relations; names in the tooltip. */
export function usedInRelation(usedIn: string[] = []): EntityCardRelation {
  const count = usedIn.length;
  const label = count === 1 ? 'requirement' : 'requirements';
  return {
    key: 'used-in',
    label,
    count,
    icon: <RequirementsIcon />,
    tooltip:
      count > 0 ? `${count} ${label}: ${usedIn.join(', ')}` : `0 ${label}`,
  };
}

/** Tuning icon + count, same style as the requirements relation. */
export function tuningCasesRelation(count: number): EntityCardRelation {
  return {
    key: 'tuning-cases',
    label: count === 1 ? 'tuning case' : 'tuning cases',
    count,
    icon: <TuneIcon />,
  };
}

export default function MetricCard({
  title,
  description,
  backend,
  metricType,
  scoreType,
  target,
  targetSummary,
  targetSummaryFull,
  targetChoices,
  metricId,
  usedIn,
  tuningCases,
  showUsage = false,
  onDelete,
  onClick,
}: MetricCardProps) {
  const facts: EntityCardFact[] = [];
  // A rule always scores 1 or 0, so what it is says more than its score type.
  if (metricType === METRIC_TYPES.RULE) {
    facts.push({
      key: 'metric-type',
      kind: 'type',
      label: METRIC_TYPE_LABELS[METRIC_TYPES.RULE],
    });
  } else if (scoreType) {
    facts.push({
      key: 'score-type',
      kind: 'type',
      label: capitalize(scoreType),
    });
  }

  return (
    <EntityCard
      title={title}
      subtitle={
        target &&
        targetSummary && (
          <MetricTargetLine
            target={target}
            summary={targetSummary}
            fullSummary={targetSummaryFull}
            choices={targetChoices}
            metricId={metricId}
          />
        )
      }
      description={description}
      context={backend ? capitalize(backend) : undefined}
      facts={facts}
      relations={
        showUsage
          ? [
              usedInRelation(usedIn),
              ...(tuningCases === undefined
                ? []
                : [tuningCasesRelation(tuningCases)]),
            ]
          : []
      }
      onDelete={onDelete}
      onClick={onClick}
    />
  );
}

const PLACEHOLDER_TARGET_CHOICES: MetricTargetChoice[] = [
  { on: 'turn', label: 'Each turn', description: '', per_span: false },
];

/** A loading view's cards: the real card in skeleton mode, with typical values. */
export function MetricCardPlaceholders() {
  return (
    <>
      {skeletonCardKeys.map(key => (
        <MetricCard
          key={key}
          title="Answer relevancy"
          description=""
          backend="rhesis"
          scoreType="numeric"
          target={{ on: 'turn' }}
          targetSummary="each turn"
          targetChoices={PLACEHOLDER_TARGET_CHOICES}
          usedIn={[]}
          showUsage
        />
      ))}
    </>
  );
}
